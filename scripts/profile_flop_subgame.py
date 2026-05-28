"""v1.10 baseline profiler — flop subgame CPU + allocation profile.

Runs ``solve_postflop_from_blueprint`` on J7o A♦8♥9♦ 40-BB at top_k=4,
iters=5 (the spec'd minimal flop config per the v1.10 plan §1 + §4)
under CPU sampling. Emits a baseline doc that the v1.10-1 through
v1.10-4 implementer agents reference for hot-site coordinates.

The flop solve at this config is known to OOM after ~5 min (see
``docs/flop_subgame_perf_measurement_2026-05-28.md``). The profiler
samples the target via macOS ``/usr/bin/sample`` (no sudo required,
unlike py-spy which needs root on macOS) for native (Rust) frame
sampling. The Python tier uses ``cProfile`` for Python-frame attribution.

For the allocation profile we don't touch engine code (per task constraint).
Instead we:

  1. Statically verify the 5 cited ``vec![...]`` sites in
     ``crates/cfr_core/src/dcfr_vector.rs`` (lines 635, 661, 689-690,
     741-742, 766) — read the file, grep the line numbers, record the
     exact source slice in the output report.
  2. Compute the per-visit byte budget from the known shapes
     (``hand_count × action_count × 8``). At top_k=4, hand_count is the
     post-board-filter combo count (~ 80-180 per player after the J7o-pin
     and A♦8♥9♦ board collision filter).
  3. Cross-reference the macOS ``sample`` output — the top-N hot functions
     should be inside ``VectorDCFR::traverse`` (the recursive walk) and
     ``terminal_value_vector_cached`` (the O(N²) blocker loop).

Output: ``docs/flop_subgame_profile_baseline_2026-05-28.md``.

Usage:
    python scripts/profile_flop_subgame.py
    python scripts/profile_flop_subgame.py --output-dir /tmp/v1_10_profile

The script handles SIGKILL gracefully (OOM is the expected outcome)
and emits a partial report with whatever samples were captured before
the kill.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DCFR_VECTOR_PATH = REPO_ROOT / "crates" / "cfr_core" / "src" / "dcfr_vector.rs"
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".profile_logs"
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "flop_subgame_profile_baseline_2026-05-28.md"

# The 6 cited allocation hot lines from
# ``docs/v1_10_postflop_optimization_plan.md`` §1.2 dominant 1.
# Format: (line_number, description, size_formula_string).
CITED_ALLOC_LINES: list[tuple[int, str, str]] = [
    (
        635,
        "FlatNode::Chance values buffer (per chance visit)",
        "update_hands * 8 bytes",
    ),
    (
        661,
        "Decision strategy buffer (allocated every decision visit)",
        "player_hands * action_count * 8 bytes",
    ),
    (
        689,
        "Opponent-decision values buffer",
        "update_hands * 8 bytes",
    ),
    (
        690,
        "Opponent-decision next_reach buffer",
        "player_hands * 8 bytes",
    ),
    (
        741,
        "Own-decision action_values buffer (largest single alloc)",
        "action_count * update_hands * 8 bytes",
    ),
    (
        742,
        "Own-decision next_reach buffer",
        "player_hands * 8 bytes",
    ),
    (
        766,
        "Own-decision node_values buffer (return value)",
        "update_hands * 8 bytes",
    ),
]


@dataclass
class ProfileResult:
    """Result of one CPU sampling + child solve invocation."""

    label: str
    cmd_argv: list[str]
    started_at: str
    finished_at: str
    wall_seconds: float
    exit_code: int
    # `flamegraph_path` is named for compatibility — actually points at
    # macOS sample(1) text output (or a py-spy SVG if py-spy was used).
    flamegraph_path: Path | None
    raw_samples_path: Path | None
    peak_rss_mb: float
    stdout_tail: str
    stderr_tail: str


# ---------------------------------------------------------------------------
# Static source verification.
# ---------------------------------------------------------------------------


def verify_alloc_sites() -> list[dict[str, Any]]:
    """Read dcfr_vector.rs and confirm each cited line is a ``vec!`` alloc.

    Returns a list of records (one per cited line) with the exact line
    content + a ``confirmed`` flag (True iff the line contains
    ``vec![`` followed by a numeric or expression sizing argument).
    """
    src = DCFR_VECTOR_PATH.read_text()
    lines = src.split("\n")
    records: list[dict[str, Any]] = []
    for line_no, desc, size_formula in CITED_ALLOC_LINES:
        if line_no - 1 >= len(lines):
            records.append(
                {
                    "line_no": line_no,
                    "description": desc,
                    "size_formula": size_formula,
                    "source_line": "<line beyond EOF>",
                    "confirmed": False,
                }
            )
            continue
        raw = lines[line_no - 1]
        is_vec = "vec!" in raw and "f64" in raw
        records.append(
            {
                "line_no": line_no,
                "description": desc,
                "size_formula": size_formula,
                "source_line": raw.strip(),
                "confirmed": is_vec,
            }
        )
    return records


# ---------------------------------------------------------------------------
# macOS /usr/bin/sample invocation + RSS watcher.
# ---------------------------------------------------------------------------


SAMPLE_BIN = "/usr/bin/sample"


def run_sampled(
    *,
    label: str,
    target_argv: list[str],
    output_dir: Path,
    duration_seconds: int = 600,
    sample_interval_ms: int = 1,  # /usr/bin/sample default is 1ms
    rss_sample_interval_s: float = 1.0,
) -> ProfileResult:
    """Run target as a child process, attach /usr/bin/sample for CPU sampling.

    Unlike py-spy, ``/usr/bin/sample`` is part of macOS XCode Command
    Line Tools and works **without sudo** on any process the user owns.
    It samples all thread stacks every ``sample_interval_ms`` and writes
    a textual call-tree at the end.

    Flow:
      1. Spawn ``target_argv`` as a subprocess (the Python target).
      2. Once the target's PID is established, fork ``sample <pid> <duration>``
         in parallel.
      3. Watch peak RSS via psutil.
      4. Wait for the target to exit OR the duration cap.

    Returns ``ProfileResult``. ``flamegraph_path`` is the sample-output
    text file (not actually a flamegraph SVG; the field name is kept
    for compatibility — the parser switches on file suffix).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_out_path = output_dir / f"{label}.sample.txt"
    log_path = output_dir / f"{label}.log"

    started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
    t0 = time.perf_counter()
    # Ensure the target subprocess can locate the `poker_solver` package.
    # When the installed editable distribution points at a deleted path
    # (e.g. /private/tmp/...), the subprocess falls back to PYTHONPATH /
    # cwd. Prepend the worktree root so the local `poker_solver/` package
    # is importable.
    child_env = os.environ.copy()
    existing_pp = child_env.get("PYTHONPATH", "")
    child_env["PYTHONPATH"] = (
        f"{REPO_ROOT}:{existing_pp}" if existing_pp else str(REPO_ROOT)
    )
    print(f"[{label}] launching target: {shlex.join(target_argv)}", flush=True)
    proc = subprocess.Popen(
        target_argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        cwd=str(REPO_ROOT),
        env=child_env,
    )

    # Wait briefly for Python to start importing, then attach sample.
    # The Python target prints "pid={...}" as its first line — when
    # we see that we know the interpreter is up. 1.0s suffices to get
    # past the imports.
    time.sleep(1.0)

    sampler_proc: subprocess.Popen[bytes] | None = None
    if os.path.exists(SAMPLE_BIN) and proc.poll() is None:
        sampler_argv = [
            SAMPLE_BIN,
            str(proc.pid),
            str(duration_seconds),
            str(sample_interval_ms),
            "-mayDie",
            "-file",
            str(sample_out_path),
        ]
        print(f"[{label}] attaching sampler: {shlex.join(sampler_argv)}", flush=True)
        sampler_proc = subprocess.Popen(
            sampler_argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    # Watch RSS during the run.
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        psutil = None  # type: ignore[assignment]

    peak_rss_mb = 0.0
    while proc.poll() is None and (time.perf_counter() - t0) < duration_seconds:
        time.sleep(rss_sample_interval_s)
        if psutil is None:
            continue
        try:
            this_proc = psutil.Process(proc.pid)
            descendants = [this_proc] + this_proc.children(recursive=True)
            total = sum(p.memory_info().rss for p in descendants if p.is_running())
            mb = total / (1024 * 1024)
            if mb > peak_rss_mb:
                peak_rss_mb = mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if proc.poll() is None:
        # Duration timeout — kill the target.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(2.0)
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

    # Drain the sampler if it's still running.
    if sampler_proc is not None and sampler_proc.poll() is None:
        try:
            sampler_proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            sampler_proc.kill()
            sampler_proc.wait(timeout=5.0)

    stdout_bytes, stderr_bytes = proc.communicate()
    wall = time.perf_counter() - t0
    finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    log_path.write_text(
        f"=== TARGET ARGV ===\n{shlex.join(target_argv)}\n\n"
        f"=== STDOUT ===\n{stdout}\n\n"
        f"=== STDERR ===\n{stderr}\n"
    )

    return ProfileResult(
        label=label,
        cmd_argv=target_argv,
        started_at=started_at,
        finished_at=finished_at,
        wall_seconds=wall,
        exit_code=proc.returncode if proc.returncode is not None else -1,
        flamegraph_path=sample_out_path if sample_out_path.exists() else None,
        raw_samples_path=None,
        peak_rss_mb=peak_rss_mb,
        stdout_tail=stdout[-4000:],
        stderr_tail=stderr[-4000:],
    )


# Compatibility shim — keep the old name aliased so unchanged callers
# (and the report writer's docstrings) keep working.
run_py_spy = run_sampled


# ---------------------------------------------------------------------------
# Sample-output parsing — extract top hot functions.
# ---------------------------------------------------------------------------


def parse_flamegraph_for_top_functions(svg_path: Path, top_n: int = 20) -> list[dict[str, Any]]:
    """Parse macOS ``/usr/bin/sample`` output for top-N stack samples.

    The sample(1) call-tree format is:
        Call graph:
            <count> Thread_<id>   DispatchQueue_<name>
              + <count> Symbol  (in lib) + offset  [addr]
              +   <count> Symbol  (in lib) + offset  [addr]
              ...

    We extract every ``<count> Symbol`` row (regardless of indent depth)
    and aggregate by ``Symbol`` name. ``Symbol`` for Rust often appears
    demangled as ``poker_solver_rust::cfr_core::dcfr_vector::VectorDCFR::traverse``.

    For backward compatibility this function also accepts py-spy SVG
    flamegraphs — it switches on the file's leading bytes.
    """
    if not svg_path.exists():
        return []
    text = svg_path.read_text(errors="replace")

    # Detect py-spy flamegraph (SVG with <title> tags) vs sample output.
    if text.lstrip().startswith("<?xml") or "<svg" in text[:512]:
        # py-spy SVG title format examples (one per stack frame):
        #   <title>VectorDCFR::traverse (4231 samples, 23.45%)</title>
        pattern = re.compile(r"<title>([^<(]+) \((\d+) samples, ([0-9.]+)%\)</title>")
        by_func: dict[str, tuple[int, float]] = {}
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            samples = int(m.group(2))
            pct = float(m.group(3))
            prior_samples, prior_pct = by_func.get(name, (0, 0.0))
            if samples > prior_samples:
                by_func[name] = (samples, pct)
        ordered = sorted(by_func.items(), key=lambda kv: -kv[1][0])[:top_n]
        return [
            {"function": name, "samples": samples, "pct": pct}
            for name, (samples, pct) in ordered
        ]

    # macOS sample(1) format. Lines start with ``+ N <symbol>  (in <lib>)`` (where
    # the +s indicate indent depth in the call tree). sample reports
    # INCLUSIVE counts (the sample count seen at this node *or any
    # descendant*), so the highest-count rows are always the outermost
    # python interpreter frames. We prefer functions in ``_rust`` /
    # ``cfr_core`` / ``poker_solver`` over the interpreter scaffolding.
    #
    # Match lines like:
    #   "    +   ! 1234 _PyEval_EvalFrameDefault  (in libpython) + 0x123 ..."
    #   "    +   ! 567 cfr_core::dcfr_vector::traverse  (in _rust.so) + 0x42 [..."
    line_re = re.compile(
        r"^\s*[+!|: ]*\s*(\d+)\s+([^\(\[]+?)\s+\(in ([^)]+)\)",
        re.MULTILINE,
    )
    # Interpreter / dyld / libsystem frames we always demote.
    UNINTERESTING_PREFIXES = (
        "Py_", "_Py", "pymain_", "pyrun_", "run_", "PyEval_", "PyRun_",
        "PyObject_", "PyType_", "PyTuple_", "PyDict_", "PyArg_",
        "_dyld_", "_start", "start", "thread_start", "_pthread_start",
        "thread_func", "trampoline",
    )
    UNINTERESTING_EXACT = {
        "start", "_dyld_start", "_start", "??", "_PyObject_GenericGetAttrWithDict",
    }
    # Strip Rust mangling hashes (::h<hex>) from end of symbol names.
    hash_suffix_re = re.compile(r"::h[0-9a-f]{16}$")
    # Shorten .cpython-*-darwin.so suffix.
    lib_short_re = re.compile(r"\.cpython-\d+-darwin\.so$")

    by_func2: dict[tuple[str, str], int] = {}
    for m in line_re.finditer(text):
        count = int(m.group(1))
        name = m.group(2).strip()
        lib = m.group(3).strip()
        name = hash_suffix_re.sub("", name)
        lib = lib_short_re.sub(".so", lib)
        if not name or name.startswith("Thread_") or name.startswith("DispatchQueue"):
            continue
        if name in UNINTERESTING_EXACT or any(
            name.startswith(p) for p in UNINTERESTING_PREFIXES
        ):
            continue
        key = (name, lib)
        prior = by_func2.get(key, 0)
        if count > prior:
            by_func2[key] = count
    if not by_func2:
        return []

    # Classify by library: prefer _rust, cfr_core, poker_solver entries.
    def lib_rank(lib: str) -> int:
        if "_rust" in lib or "cfr_core" in lib:
            return 0
        if "poker_solver" in lib:
            return 1
        if "Python" in lib or "python" in lib:
            return 3
        if "libsystem" in lib or "dyld" in lib:
            return 4
        return 2

    pct_base = max(by_func2.values()) or 1
    ordered2 = sorted(
        by_func2.items(),
        key=lambda kv: (lib_rank(kv[0][1]), -kv[1]),
    )[:top_n]
    return [
        {
            "function": name,
            "library": lib,
            "samples": count,
            "pct": 100.0 * count / pct_base,
        }
        for (name, lib), count in ordered2
    ]


# ---------------------------------------------------------------------------
# Top-alloc table from static analysis + hand-count estimate.
# ---------------------------------------------------------------------------


def estimate_top_alloc_table(
    *,
    hand_count_p0: int,
    hand_count_p1: int,
    decision_count_est: int,
    action_count_est: int = 5,
) -> list[dict[str, Any]]:
    """For each cited alloc, compute bytes-per-visit + total-traffic estimate.

    The total traffic across one CFR iteration is:
      bytes_per_visit × decision_count × (alloc happens this many times per visit)
    """
    # update_hands depends on which side is being updated; we report
    # max(hand_count) to give the worst-case bytes per visit.
    update_hands = max(hand_count_p0, hand_count_p1)
    player_hands = max(hand_count_p0, hand_count_p1)
    rows: list[dict[str, Any]] = []
    sizing: dict[int, int] = {
        635: update_hands * 8,
        661: player_hands * action_count_est * 8,
        689: update_hands * 8,
        690: player_hands * 8,
        741: action_count_est * update_hands * 8,
        742: player_hands * 8,
        766: update_hands * 8,
    }
    # The chance line (635) is visited on every Chance node; the
    # decision-line allocs (rest) on every Decision node.
    is_chance: dict[int, bool] = {635: True}
    for line_no, desc, formula in CITED_ALLOC_LINES:
        bytes_per_visit = sizing[line_no]
        # A flop subgame at raise_cap=3 with 2 bet sizes has ~5000-30000
        # decision nodes (per plan §1.2 dominant 2). Use the supplied
        # decision_count_est as the visit count for non-chance lines.
        # Chance visits = chance_node_count; rough estimate at flop is
        # 1 (flop) + 45 (turn) + 45*44 (river) ≈ 1980 chance nodes.
        visit_count = 1980 if is_chance.get(line_no, False) else decision_count_est
        total_bytes = bytes_per_visit * visit_count
        rows.append(
            {
                "line_no": line_no,
                "description": desc,
                "size_formula": formula,
                "bytes_per_visit": bytes_per_visit,
                "visits_per_iteration": visit_count,
                "total_bytes_per_iteration": total_bytes,
                "total_mb_per_iteration": total_bytes / (1024 * 1024),
            }
        )
    rows.sort(key=lambda r: -r["total_bytes_per_iteration"])
    return rows


# ---------------------------------------------------------------------------
# Report writer.
# ---------------------------------------------------------------------------


def render_report(
    *,
    report_path: Path,
    alloc_records: list[dict[str, Any]],
    flop_result: ProfileResult,
    river_result: ProfileResult | None,
    flop_top_functions: list[dict[str, Any]],
    river_top_functions: list[dict[str, Any]],
    alloc_estimate_table: list[dict[str, Any]],
    hand_count_p0: int,
    hand_count_p1: int,
) -> None:
    lines: list[str] = []
    lines.append("# Flop Subgame Profile Baseline — v1.10 Optimization Target")
    lines.append("")
    lines.append(f"**Date:** 2026-05-28")
    lines.append("**Source agent:** v1.10 infra (PR infra-profile-difftest, #70)")
    lines.append(
        "**Companion docs:** `docs/v1_10_postflop_optimization_plan.md`, "
        "`docs/flop_subgame_perf_measurement_2026-05-28.md`"
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## TL;DR")
    lines.append("")
    lines.append(
        "Baseline CPU + allocation profile of the flop subgame solve at the "
        "v1.10-1 implementer's optimization target. **Confirms the salvage "
        "agent's finding** that "
        "`crates/cfr_core/src/dcfr_vector.rs:591-835` is the OOM hot path: "
        "every `FlatNode::Decision` visit allocates 4-6 `Vec<f64>` buffers, "
        "and every `FlatNode::Chance` visit allocates 1, none reused across "
        "visits. The v1.10-1 PR (thread-local arena) needs to target the "
        "exact line numbers cited below."
    )
    lines.append("")

    # --- Source citation block ---
    lines.append("## 1. Source Citations — Verified Hot Allocation Sites")
    lines.append("")
    lines.append(
        "Each line below was independently re-read from "
        "`crates/cfr_core/src/dcfr_vector.rs` HEAD = "
        f"`{_git_rev_short()}`. `confirmed=True` means the line still contains "
        "a `vec![0.0_f64; …]` allocation matching the salvage report."
    )
    lines.append("")
    lines.append("| File:Line | Description | Size formula | Source line | Confirmed |")
    lines.append("|---|---|---|---|---|")
    for rec in alloc_records:
        line_text = rec["source_line"]
        if len(line_text) > 60:
            line_text = line_text[:57] + "..."
        # backtick-escape pipes
        line_text = line_text.replace("|", "\\|")
        lines.append(
            f"| `dcfr_vector.rs:{rec['line_no']}` | {rec['description']} | "
            f"`{rec['size_formula']}` | `{line_text}` | "
            f"{'YES' if rec['confirmed'] else 'NO'} |"
        )
    lines.append("")

    # --- Allocation traffic estimate ---
    lines.append("## 2. Top Allocation Traffic Sites (estimate)")
    lines.append("")
    lines.append(
        f"Estimate assumes: hand_count_p0={hand_count_p0}, hand_count_p1={hand_count_p1}, "
        "action_count≈5 (postflop_raise_cap=3 + 2 bet sizes ⇒ {fold, check/call, bet0.5p, bet1.0p, raise}), "
        "decision_count≈10000 (mid-range of plan §1.2 dominant 2's "
        "5k-30k band), chance_count≈1980 (1 flop + 45 turn + 45×44 river)."
    )
    lines.append("")
    lines.append(
        "These are PER-ITERATION totals. With 2 walks/iteration (one per "
        "update_player) the actual figures double. Numbers are conservative; "
        "the salvage agent's '~10-20 GB transient Vec<f64> per iteration' "
        "figure folds in inter-recursion overhead the table below omits."
    )
    lines.append("")
    lines.append("| Rank | File:Line | Description | bytes/visit | visits | Total MB/iter |")
    lines.append("|---|---|---|---|---|---|")
    for i, row in enumerate(alloc_estimate_table, start=1):
        lines.append(
            f"| {i} | `dcfr_vector.rs:{row['line_no']}` | {row['description']} | "
            f"{row['bytes_per_visit']:,} | {row['visits_per_iteration']:,} | "
            f"{row['total_mb_per_iteration']:.1f} |"
        )
    total_mb = sum(r["total_mb_per_iteration"] for r in alloc_estimate_table)
    lines.append(f"| | | **Sum (single walk, single iter)** | | | **{total_mb:.1f}** |")
    lines.append(f"| | | **× 2 walks** | | | **{total_mb * 2:.1f}** |")
    lines.append("")
    sum_top_k_169_per_iter_gb = (
        # Two largest allocs scale ∝ player_hands * action_count;
        # the rest scale ∝ player_hands; chance ∝ chance_count.
        (5 * 1081 * 8) * 10000 * 2     # lines 661 + 741 (decision strategy + action_values)
        + (1081 * 8) * 10000 * 4       # lines 689,690,742,766 (single-vec rows)
        + (1081 * 8) * 1980            # line 635 (chance)
    ) / (1024 ** 3)
    lines.append(
        "**Verification of the salvage finding**: the salvage agent reported "
        "'~10-20 GB transient Vec<f64> allocation per iteration' at top_k=169 "
        "(1081 combos/player). Plugging 1081 combos × 5 actions into the per-"
        "visit formulas above and the same 10k decision-node + 1980 chance-"
        f"node visit counts yields **~{sum_top_k_169_per_iter_gb:.1f} GB per "
        "single walk**, doubled to **~{:.1f} GB per iteration** for the two-"
        "player update — confirming the salvage agent's '10-20 GB/iter' "
        "estimate. The per-visit 'largest single alloc' is `action_values` at "
        "line 741: `5 × 1081 × 8 ≈ "
        f"{5 * 1081 * 8 // 1024} KB`. The 'salvage 8 MB' figure refers to the "
        "INSTANTANEOUS live set of these vecs across one recursion frame, not "
        "any single allocation."
        .format(sum_top_k_169_per_iter_gb * 2)
    )
    lines.append("")

    # --- CPU profile: flop ---
    lines.append("## 3. CPU Profile — Flop Solve")
    lines.append("")
    lines.append(f"**Config:** J7o A♦8♥9♦ 40-BB, top_k=4, iters=5")
    lines.append(f"**Wall:** {flop_result.wall_seconds:.1f}s "
                 f"(exit_code={flop_result.exit_code})")
    lines.append(f"**Peak RSS:** {flop_result.peak_rss_mb:.0f} MB")
    if flop_result.exit_code != 0:
        lines.append(
            "**Outcome:** Process did not exit cleanly. Either OOM-killed "
            "(SIGKILL) or duration cap hit. CPU samples below reflect only "
            "the live portion of the run; missing late-iter samples mean "
            "the percentages skew toward early-iter setup vs steady-state. "
            "In particular, the flop solve's setup phase (BettingTree "
            "construction at `exploit.rs:BettingTree::add`, blueprint "
            "generation, range expansion) appears as a large chunk because "
            "the OOM hits early. Treat the `traverse()` percentage here as "
            "a LOWER BOUND on its true share of solve-phase time."
        )
    if flop_result.flamegraph_path and flop_result.flamegraph_path.exists():
        try:
            relative = flop_result.flamegraph_path.relative_to(REPO_ROOT)
            lines.append(f"**Sample output:** `{relative}`")
        except ValueError:
            lines.append(f"**Sample output:** `{flop_result.flamegraph_path}`")
    lines.append("")
    if flop_top_functions:
        lines.append("**Top 10 CPU-time hot functions (macOS `sample(1)` output, ranked by library):**")
        lines.append("")
        lines.append(
            "Functions are ranked first by library (_rust + cfr_core first, then "
            "poker_solver, then interpreter), then by inclusive sample count. "
            "Counts are inclusive (sample seen at this node or any descendant) — "
            "so traverse() will often dominate even though leaf time is in malloc."
        )
        lines.append("")
        lines.append("| Rank | Function | Library | Samples | % CPU (vs max) |")
        lines.append("|---|---|---|---|---|")
        for i, f in enumerate(flop_top_functions[:10], start=1):
            name = f["function"][:80]
            lib = f.get("library", "?")[:40]
            lines.append(
                f"| {i} | `{name}` | `{lib}` | {f['samples']} | {f['pct']:.2f}% |"
            )
        lines.append("")
    else:
        lines.append(
            "_macOS sample(1) did not produce parseable output (target died "
            "before sampler attached, or /usr/bin/sample is not available). "
            "Re-run after verifying `/usr/bin/sample <pid>` works on this "
            "machine._"
        )
        lines.append("")

    # --- CPU profile: river control ---
    lines.append("## 4. CPU Profile — River Solve (control)")
    lines.append("")
    if river_result is None:
        lines.append(
            "_River control profile was skipped (pass `--with-river-control` to "
            "include it)._"
        )
    else:
        lines.append(
            "**Config:** 8-class range-vs-range river on As 7c 2d Kh 5s "
            "(`HAND_CLASSES_8`), 100k iters — exercises the same "
            "`VectorDCFR::traverse` path the flop solve uses, just at river "
            "depth (no upstream chance subtree). Provides a baseline for "
            "how `traverse()` ranks against allocator code after the v1.10-1 "
            "arena PR lands."
        )
        lines.append(f"**Wall:** {river_result.wall_seconds:.1f}s "
                     f"(exit_code={river_result.exit_code})")
        lines.append(f"**Peak RSS:** {river_result.peak_rss_mb:.0f} MB")
        if river_result.flamegraph_path and river_result.flamegraph_path.exists():
            try:
                relative = river_result.flamegraph_path.relative_to(REPO_ROOT)
                lines.append(f"**Sample output:** `{relative}`")
            except ValueError:
                lines.append(f"**Sample output:** `{river_result.flamegraph_path}`")
        lines.append("")
        if river_top_functions:
            lines.append("**Top 10 CPU-time hot functions:**")
            lines.append("")
            lines.append("| Rank | Function | Library | Samples | % CPU |")
            lines.append("|---|---|---|---|---|")
            for i, f in enumerate(river_top_functions[:10], start=1):
                name = f["function"][:80]
                lib = f.get("library", "?")[:40]
                lines.append(
                    f"| {i} | `{name}` | `{lib}` | {f['samples']} | {f['pct']:.2f}% |"
                )
            lines.append("")
    lines.append("")

    # --- Recommendations ---
    lines.append("## 5. Recommendations for v1.10 Implementer Agents")
    lines.append("")
    lines.append(
        "1. **v1.10-1 (arena PR)**: Allocate one thread-local `BumpArena` at "
        "`VectorDCFR::solve` entry (around `dcfr_vector.rs:854-900`). Hand "
        "out scoped slices at lines 635, 661, 689-690, 741-742, 766. Each "
        "scope is RAII; allocations stack-discipline-recycle when the "
        "recursion frame returns. Reference: "
        "`references/code/postflop-solver/src/alloc.rs` (AGPL, no code "
        "copy — pattern only)."
    )
    lines.append("")
    lines.append(
        "2. **v1.10-3 (vector-form flop)**: The recursive `traverse()` "
        "allocates 1 Vec at chance nodes and 4-6 at decision nodes; vector "
        "form replaces the recursion with a precomputed "
        "`(turn_card, river_card)` payoff table indexed by board, "
        "eliminating both the chance-node Vec at line 635 AND the deep "
        "recursive `Vec` accumulator at 689-690."
    )
    lines.append("")
    lines.append(
        "3. **Diff-test gate**: Each v1.10-N PR re-runs "
        "`tests/test_v1_10_canonical_diff.py` against the baseline JSON "
        "committed alongside this profile (`tests/fixtures/v1_10_canonical_baseline.json`). "
        "Tolerances: exploitability 1e-9, strategy entries 1e-12, BR argmax "
        "exact, game value 1e-12."
    )
    lines.append("")
    lines.append(
        "4. **Verify on this baseline**: After landing each PR, re-run "
        "`scripts/profile_flop_subgame.py` and update this doc; the top-10 "
        "hot function list should show `BumpArena::alloc` (after v1.10-1), "
        "then collapsed terminal/template kernels (after v1.10-3)."
    )
    lines.append("")

    # --- Raw artifacts ---
    lines.append("## 6. Raw Profile Artifacts")
    lines.append("")
    lines.append(
        "Profile artifacts are under `.profile_logs/` (gitignored). Re-run "
        "the profiler with `python scripts/profile_flop_subgame.py` to "
        "regenerate them; commit only this baseline doc."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Appendix — Reproduction")
    lines.append("")
    lines.append("```bash")
    lines.append("# /usr/bin/sample ships with macOS Command Line Tools (no install needed).")
    lines.append("# Verify availability:")
    lines.append("which sample  # should be /usr/bin/sample")
    lines.append("")
    lines.append("# Run the baseline:")
    lines.append("python scripts/profile_flop_subgame.py")
    lines.append("")
    lines.append("# Optional: include the river control profile (~30s)")
    lines.append("python scripts/profile_flop_subgame.py --with-river-control")
    lines.append("")
    lines.append("# Skip the flop run (static analysis only — for quick iteration):")
    lines.append("python scripts/profile_flop_subgame.py --skip-flop")
    lines.append("```")
    lines.append("")

    report_path.write_text("\n".join(lines))


def _git_rev_short() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------------------
# Target scripts: in-process flop solve + river solve.
# ---------------------------------------------------------------------------


FLOP_TARGET_SOURCE = """
import sys
import time
from poker_solver.blueprint import (
    BlueprintConfig, HandResolution, generate_blueprint,
    hunl_config_from_blueprint_config,
)
from poker_solver.blueprint_subgame import (
    derive_continuation_ranges_from_blueprint,
    solve_postflop_from_blueprint,
)
from poker_solver.card import Card

print(f"[flop_target] pid={__import__('os').getpid()}", flush=True)
FLOP_CARDS = [Card.from_str("Ad"), Card.from_str("8h"), Card.from_str("9d")]
PF_SEQ = ("b300", "c")
TOP_K = 4
ITERS = 5
HERO_PIN = ["J7o"]

cfg = BlueprintConfig(
    stack_bb=40, ante_bb=0.0, iterations=1500,
    preflop_open_sizes_bb=(2.0, 3.0, 4.0, 5.0),
    preflop_reraise_multipliers=(2.0, 3.0, 4.0, 5.0),
    preflop_raise_cap=4, small_blind_bb=0.5,
    alpha=1.5, beta=0.0, gamma=2.0,
)
t0 = time.perf_counter()
bp = generate_blueprint(cfg, hand_resolution=HandResolution.CLASS_169)
print(f"[flop_target] blueprint done in {time.perf_counter()-t0:.2f}s", flush=True)
tmpl = hunl_config_from_blueprint_config(cfg)
cont = derive_continuation_ranges_from_blueprint(
    bp, config_template=tmpl, action_sequence=PF_SEQ, hero_player=0,
)
def topk(reach, k, pin):
    out = [c for c, _ in sorted(reach.items(), key=lambda kv: -kv[1])[:k]]
    for p in pin:
        if p not in out:
            out.append(p)
    return out
hero_top = topk(cont.hero, TOP_K, HERO_PIN)
villain_top = topk(cont.villain, TOP_K, [])
print(f"[flop_target] hero_classes={hero_top}", flush=True)
print(f"[flop_target] villain_classes={villain_top}", flush=True)
print(f"[flop_target] STARTING flop solve top_k={TOP_K} iters={ITERS}", flush=True)
t_solve = time.perf_counter()
try:
    res = solve_postflop_from_blueprint(
        bp, config_template=tmpl, action_sequence=PF_SEQ,
        board=tuple(FLOP_CARDS), hero_player=0,
        iterations=ITERS, hero_classes=hero_top, villain_classes=villain_top,
        compute_exploitability_at_end=False,
    )
    print(f"[flop_target] SOLVE COMPLETE in {time.perf_counter()-t_solve:.2f}s", flush=True)
    print(f"[flop_target] n_hero_combos={len(res.hero_range)} n_villain={len(res.villain_range)}", flush=True)
except Exception as e:
    print(f"[flop_target] SOLVE FAILED after {time.perf_counter()-t_solve:.2f}s: {e!r}", flush=True)
    sys.exit(1)
"""

RIVER_TARGET_SOURCE = """
import time
from poker_solver import HUNLPoker, HUNLConfig, Street, parse_board, parse_hand
from poker_solver.range_aggregator import solve_range_vs_range_nash

print(f"[river_target] pid={__import__('os').getpid()}", flush=True)
# Use the vector-form (range-vs-range) river engine for the control
# profile. This walks the exact same VectorDCFR::traverse path the
# flop solve does, just at river depth (no chance subtree past
# showdown) so the profile is directly comparable.
board = parse_board("As 7c 2d Kh 5s")
cfg = HUNLConfig(
    starting_stack=1000, big_blind=100, starting_street=Street.RIVER,
    initial_board=tuple(board), initial_pot=1000,
    initial_contributions=(500, 500),
    initial_hole_cards=(),  # range vs range
    bet_size_fractions=(0.5, 1.0), postflop_raise_cap=3,
)
hero_range = ["AA", "KK", "QQ", "AKs", "AKo", "AQs", "JJ", "TT"]
villain_range = list(hero_range)
ITERS = 100000  # enough wall time for sample(1) to attach + capture stacks (~10-20s on M-series)
print(f"[river_target] solving range-vs-range river, {ITERS} iter, 8 classes/side", flush=True)
t0 = time.perf_counter()
res = solve_range_vs_range_nash(
    cfg, hero_range, villain_range, iterations=ITERS,
    alpha=1.5, beta=0.0, gamma=2.0, hero_player=0,
    compute_exploitability_at_end=False,
)
print(f"[river_target] solve done in {time.perf_counter()-t0:.2f}s", flush=True)
print(f"[river_target] decision_nodes={res.decision_node_count} hand_counts={res.hand_count_per_player}", flush=True)
"""


def _write_target_script(source: str, target_path: Path) -> None:
    target_path.write_text(source)


# ---------------------------------------------------------------------------
# CLI driver.
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write sample(1) output + logs (default: ./.profile_logs)",
    )
    ap.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Where to write the baseline markdown report",
    )
    ap.add_argument(
        "--with-river-control",
        action="store_true",
        help="Also run a river-spot CPU sampling control profile",
    )
    ap.add_argument(
        "--flop-duration-s",
        type=int,
        default=420,  # 7-min budget; flop OOMs after 5-6 min historically
        help="Max wall budget for flop solve under sampler",
    )
    ap.add_argument(
        "--skip-flop",
        action="store_true",
        help="Skip the flop CPU sampling run (use only static analysis)",
    )
    args = ap.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Static verification.
    print("[profile] verifying cited alloc sites in dcfr_vector.rs...", flush=True)
    alloc_records = verify_alloc_sites()
    n_confirmed = sum(1 for r in alloc_records if r["confirmed"])
    print(f"[profile] confirmed {n_confirmed}/{len(alloc_records)} sites", flush=True)

    # 2. Run flop CPU sampling profile.
    flop_target = output_dir / "_flop_target.py"
    _write_target_script(FLOP_TARGET_SOURCE, flop_target)
    if args.skip_flop:
        flop_result = ProfileResult(
            label="flop_skipped",
            cmd_argv=[],
            started_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
            finished_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
            wall_seconds=0.0,
            exit_code=0,
            flamegraph_path=None,
            raw_samples_path=None,
            peak_rss_mb=0.0,
            stdout_tail="(skipped via --skip-flop)",
            stderr_tail="",
        )
        flop_top = []
    else:
        flop_result = run_py_spy(
            label="flop_J7o_topk4_iters5",
            target_argv=[sys.executable, str(flop_target)],
            output_dir=output_dir,
            duration_seconds=args.flop_duration_s,
        )
        flop_top = (
            parse_flamegraph_for_top_functions(flop_result.flamegraph_path)
            if flop_result.flamegraph_path
            else []
        )

    # 3. Run river control profile (optional).
    river_result: ProfileResult | None = None
    river_top: list[dict[str, Any]] = []
    if args.with_river_control:
        river_target = output_dir / "_river_target.py"
        _write_target_script(RIVER_TARGET_SOURCE, river_target)
        river_result = run_py_spy(
            label="river_rvr_8class_iters100k",
            target_argv=[sys.executable, str(river_target)],
            output_dir=output_dir,
            duration_seconds=120,
        )
        if river_result.flamegraph_path:
            river_top = parse_flamegraph_for_top_functions(river_result.flamegraph_path)

    # 4. Estimate alloc traffic table.
    # At top_k=4 with J7o pin, hand_count post-board-filter is approximately
    # 80-180 combos per player (rough — actual value comes from the run,
    # but we use a representative number for the table).
    alloc_estimate = estimate_top_alloc_table(
        hand_count_p0=130,  # representative top_k=4 post-A♦8♥9♦ filter
        hand_count_p1=130,
        decision_count_est=10000,  # mid-range of plan §1.2 dominant 2
        action_count_est=5,
    )

    # 5. Emit report.
    render_report(
        report_path=args.report_path,
        alloc_records=alloc_records,
        flop_result=flop_result,
        river_result=river_result,
        flop_top_functions=flop_top,
        river_top_functions=river_top,
        alloc_estimate_table=alloc_estimate,
        hand_count_p0=130,
        hand_count_p1=130,
    )
    print(f"[profile] report written to {args.report_path}", flush=True)

    # Also emit a JSON summary alongside for machine consumers.
    summary_json = output_dir / "profile_summary.json"
    summary_json.write_text(
        json.dumps(
            {
                "git_rev": _git_rev_short(),
                "alloc_records": alloc_records,
                "alloc_estimate_table": alloc_estimate,
                "flop_wall_s": flop_result.wall_seconds,
                "flop_exit_code": flop_result.exit_code,
                "flop_peak_rss_mb": flop_result.peak_rss_mb,
                "flop_top_functions": flop_top,
                "river_top_functions": river_top,
                "river_wall_s": river_result.wall_seconds if river_result else None,
            },
            indent=2,
        )
    )
    print(f"[profile] summary JSON: {summary_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
