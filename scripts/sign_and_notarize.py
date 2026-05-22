"""macOS code-signing + Apple notarization for the Poker Solver .app bundle.

Callable both as a CLI (``python scripts/sign_and_notarize.py SUBCMD ...``)
and as a Python API (``from scripts.sign_and_notarize import sign_bundle``).

Subcommands:
    sign-bundle <bundle> --identity NAME --entitlements PATH
        Sign the outer .app bundle.  Hardened Runtime + entitlements.

    sign-inside-out <bundle> --identity NAME --entitlements PATH
        Walk Contents/ and sign every .dylib + .so before signing the
        outer .app.  ``codesign --deep`` is unreliable on PyInstaller
        bundles (spec §6.4); the explicit walk is the load-bearing
        fix.

    notarize <zip_or_dmg> --apple-id EMAIL --team-id ID --password PWD
        Submit to Apple notarization via ``xcrun notarytool submit
        --wait``.  On failure, captures ``notarytool log
        <submission-id>`` JSON to ``dist/notarization_failure.log``.

    staple <target>
        ``xcrun stapler staple <target>``.  Embeds the notarization
        ticket so the .app validates offline.

Troubleshooting:
    1. ``_rust`` import fails inside the bundle:
       PyInstaller missed the maturin-built .so.  Confirm
       ``--add-binary "poker_solver/_rust.cpython-313-darwin.so:poker_solver"``
       was passed (or that the .spec file lists it in `binaries=`).
       This is the spec §12.1 top risk.
    2. ``spctl --assess`` says "rejected":
       Notarization ticket missing.  Re-run staple.
    3. ``codesign --verify`` says "resource fork, Finder info, or
       similar detritus not allowed":
       ``xattr -cr "Poker Solver.app"`` then re-sign.
    4. notarytool says "The executable does not have the hardened
       runtime enabled":
       sign_inside_out missed a .dylib.  Inspect
       ``dist/notarization_failure.log`` for the offending path.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path


class NotarizationError(RuntimeError):
    """Raised when Apple rejects the submission or it times out."""


def _run(
    cmd: list[str], *, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around subprocess.run with consistent text/stderr handling."""
    print(f"+ {' '.join(cmd)}", flush=True)
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def sign_bundle(bundle_path: Path, identity: str, entitlements: Path) -> None:
    """Sign the outer .app bundle with Hardened Runtime.

    Use ``sign_inside_out`` for PyInstaller bundles; this is the
    "outside only" variant for callers that have already signed inner
    binaries (or for non-PyInstaller .apps).
    """
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")
    if not entitlements.exists():
        raise FileNotFoundError(f"Entitlements not found: {entitlements}")

    _run(
        [
            "codesign",
            "--deep",
            "--force",
            "--sign",
            identity,
            "--options",
            "runtime",
            "--entitlements",
            str(entitlements),
            str(bundle_path),
        ]
    )
    # Verify the signature is well-formed.
    _run(
        [
            "codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(bundle_path),
        ]
    )


def sign_inside_out(bundle_path: Path, identity: str, entitlements: Path) -> None:
    """Walk Contents/ and sign every dylib/.so, then sign the outer .app.

    Per spec §6.4: ``codesign --deep`` "claims to walk recursively but
    is unreliable on PyInstaller bundles."  The explicit walk hits
    nested ``Frameworks/`` paths via ``rglob`` and signs each binary
    with ``--options runtime`` so Hardened Runtime applies uniformly.
    """
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")
    if not entitlements.exists():
        raise FileNotFoundError(f"Entitlements not found: {entitlements}")

    contents = bundle_path / "Contents"
    if not contents.exists():
        raise FileNotFoundError(
            f"Bundle has no Contents/ directory: {bundle_path} "
            f"— is this really a .app?"
        )

    # 1. Sign every dynamic library, inside-out.
    binaries_signed = 0
    for so in itertools.chain(
        sorted(contents.rglob("*.dylib")),
        sorted(contents.rglob("*.so")),
    ):
        _run(
            [
                "codesign",
                "--force",
                "--sign",
                identity,
                "--options",
                "runtime",
                "--entitlements",
                str(entitlements),
                str(so),
            ]
        )
        binaries_signed += 1
    print(f"[sign] signed {binaries_signed} inner binaries (.dylib + .so)")

    # 2. Sign the outer .app last.
    _run(
        [
            "codesign",
            "--deep",
            "--force",
            "--sign",
            identity,
            "--options",
            "runtime",
            "--entitlements",
            str(entitlements),
            str(bundle_path),
        ]
    )

    # 3. Verify.
    _run(
        [
            "codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(bundle_path),
        ]
    )
    # spctl assessment (best-effort; will fail until notarized + stapled
    # but the error message confirms the signature is at least valid).
    try:
        _run(
            [
                "spctl",
                "--assess",
                "--type",
                "execute",
                "--verbose",
                str(bundle_path),
            ],
            check=False,
        )
    except FileNotFoundError:
        print("[sign] spctl not available; skipping pre-notarization assess")


def notarize(
    target: Path,
    apple_id: str,
    team_id: str,
    password: str,
    timeout_minutes: int = 60,
) -> dict:
    """Submit target (.zip for .app, or .dmg) to Apple notarization.

    Blocks on ``--wait``.  Returns the notarization result dict parsed
    from notarytool's JSON output.

    On failure, captures ``notarytool log <submission-id>`` JSON to
    ``dist/notarization_failure.log`` for debugging.

    Raises:
        NotarizationError: Apple rejected the submission or it timed out.
    """
    if not target.exists():
        raise FileNotFoundError(f"Notarization target not found: {target}")

    # notarytool requires a .zip or .dmg.  If we were given a raw .app,
    # the caller should have zipped it via ``ditto -c -k --keepParent``.
    if target.suffix not in (".zip", ".dmg"):
        raise ValueError(
            f"notarytool expects .zip or .dmg; got {target.suffix}.  "
            f"Wrap .app with: ditto -c -k --keepParent '{target}' '{target}.zip'"
        )

    result = subprocess.run(
        [
            "xcrun",
            "notarytool",
            "submit",
            str(target),
            "--apple-id",
            apple_id,
            "--team-id",
            team_id,
            "--password",
            password,
            "--wait",
            "--timeout",
            f"{timeout_minutes}m",
            "--output-format",
            "json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    # Parse the JSON output regardless of exit status; we want the
    # submission ID even on failure so we can pull the log.
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"status": "Unknown", "raw_stdout": result.stdout}

    status = payload.get("status", "Unknown")
    submission_id = payload.get("id")

    if status != "Accepted":
        # Capture detailed failure log for the user.
        if submission_id:
            log_path = Path("dist/notarization_failure.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_result = subprocess.run(
                [
                    "xcrun",
                    "notarytool",
                    "log",
                    submission_id,
                    "--apple-id",
                    apple_id,
                    "--team-id",
                    team_id,
                    "--password",
                    password,
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            log_path.write_text(log_result.stdout or log_result.stderr)
            print(f"[notarize] failure log written to {log_path}")
        raise NotarizationError(
            f"Notarization failed (status={status}, id={submission_id}). "
            f"See dist/notarization_failure.log for details."
        )

    print(f"[notarize] accepted (id={submission_id})")
    return payload


def staple(target: Path) -> None:
    """Embed the notarization ticket so the .app validates offline."""
    if not target.exists():
        raise FileNotFoundError(f"Staple target not found: {target}")
    _run(["xcrun", "stapler", "staple", str(target)])
    _run(["xcrun", "stapler", "validate", str(target)])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli_sign_bundle(args: argparse.Namespace) -> int:
    sign_bundle(
        bundle_path=Path(args.bundle),
        identity=args.identity,
        entitlements=Path(args.entitlements),
    )
    return 0


def _cli_sign_inside_out(args: argparse.Namespace) -> int:
    sign_inside_out(
        bundle_path=Path(args.bundle),
        identity=args.identity,
        entitlements=Path(args.entitlements),
    )
    return 0


def _cli_notarize(args: argparse.Namespace) -> int:
    notarize(
        target=Path(args.target),
        apple_id=args.apple_id,
        team_id=args.team_id,
        password=args.password,
        timeout_minutes=args.timeout_minutes,
    )
    return 0


def _cli_staple(args: argparse.Namespace) -> int:
    staple(Path(args.target))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sign_and_notarize",
        description="Code-sign + notarize the Poker Solver macOS bundle.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sign = sub.add_parser("sign-bundle", help="Sign the outer .app bundle")
    p_sign.add_argument("bundle", help="Path to the .app bundle")
    p_sign.add_argument(
        "--identity", required=True, help='e.g. "Developer ID Application: ..."'
    )
    p_sign.add_argument(
        "--entitlements", required=True, help="Path to entitlements.plist"
    )
    p_sign.set_defaults(func=_cli_sign_bundle)

    p_io = sub.add_parser(
        "sign-inside-out",
        help="Sign every inner dylib/.so, then the outer .app (PyInstaller-safe)",
    )
    p_io.add_argument("bundle", help="Path to the .app bundle")
    p_io.add_argument(
        "--identity", required=True, help='e.g. "Developer ID Application: ..."'
    )
    p_io.add_argument(
        "--entitlements", required=True, help="Path to entitlements.plist"
    )
    p_io.set_defaults(func=_cli_sign_inside_out)

    p_not = sub.add_parser(
        "notarize", help="Submit to Apple notarization (blocks on --wait)"
    )
    p_not.add_argument("target", help="Path to .zip or .dmg")
    p_not.add_argument("--apple-id", required=True, help="Apple ID email")
    p_not.add_argument("--team-id", required=True, help="Developer Team ID")
    p_not.add_argument("--password", required=True, help="App-specific password")
    p_not.add_argument(
        "--timeout-minutes",
        type=int,
        default=60,
        help="Wait timeout in minutes (default: 60)",
    )
    p_not.set_defaults(func=_cli_notarize)

    p_sta = sub.add_parser("staple", help="xcrun stapler staple <target>")
    p_sta.add_argument("target", help="Path to .app or .dmg")
    p_sta.set_defaults(func=_cli_staple)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
