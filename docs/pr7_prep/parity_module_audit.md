# PR 7 audit — `poker_solver/parity/` module + diff harness public API

**Auditor:** sanity-check agent
**Scope (read-only):**
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/__init__.py` (21 LOC)
- `/Users/ashen/Desktop/poker_solver/poker_solver/parity/noambrown_wrapper.py` (1217 LOC) — Agent A
- `/Users/ashen/Desktop/poker_solver/tests/test_river_diff.py` (492 LOC) — Agent B (consumer)
- `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` (158 LOC)

Note: prompt said the wrapper lived in `tests/noambrown_wrapper.py`. It does not. The wrapper file lives **inside the public package** at `poker_solver/parity/noambrown_wrapper.py`. That single placement fact is the dominant finding of this audit.

---

## 1. Public API exposed by `parity/`

`poker_solver/parity/__init__.py` is **pure docstring + `from __future__ import annotations`**. It exports **zero names**: no re-exports, no `__all__`, no version. 21 LOC is entirely a module docstring describing the sub-package convention ("wrappers invoke targets as subprocess", "no source code copied", "each wrapper carries its own license attribution").

The actual public surface — i.e. anything an importer reaches — lives **one level down** in `poker_solver.parity.noambrown_wrapper`. That module ships an explicit `__all__` (lines 1198–1213) of 14 names:

| Kind | Names |
| --- | --- |
| Dataclasses | `RiverSpot`, `BrownInfosetEntry`, `BrownPlayerProfile`, `BrownStrategyDump` |
| Type aliases | `Combo`, `CanonicalToken`, `CanonicalHistory` |
| Entry-point functions | `load_spots`, `find_brown_binary`, `write_brown_config`, `run_brown_solver`, `canonicalize_brown_history`, `canonicalize_our_history`, `our_strategy_to_brown_matrix` |

A 15th name (`HistoryRoot`, `Union[str, CanonicalHistory]`) is defined **after** `__all__` and is **not** in the list; the trailing comment calls it "forward-compat". This is a minor inconsistency — either include it in `__all__` or drop it.

Agent B's test imports exactly **10** of those 14 names: it does not pull `Combo`, `CanonicalToken`, `CanonicalHistory`, or `write_brown_config`. The other ten are reached through the documented dotted path `poker_solver.parity.noambrown_wrapper.X`, not through the sub-package root. There is no `from poker_solver.parity import …` site anywhere in the repo (grep confirmed).

## 2. Production-vs-test separation

The placement is **physically production code, logically test-only**.

Physical: the file lives under `poker_solver/parity/`, which is shipped as part of the installable package (anything under `poker_solver/` is publicly importable as `poker_solver.parity.*`).

Logical: every observable consumer is a test.
- The only import site is `tests/test_river_diff.py:86`.
- The module docstring on `parity/__init__.py` explicitly frames the package as "cross-solver parity / differential-test wrappers" — its stated purpose is the diff harness.
- `noambrown_wrapper`'s own docstring opens with "Wrapper around Noam Brown's river_solver_optimized **for differential testing**".
- The module declares an MIT-licensed external dependency (Noam Brown's repo) and is gated behind the `parity_noambrown` pytest marker (Agent B's Layer A skip).
- No runtime / non-test code paths in `poker_solver/` reference `parity` at all (`__init__.py` does not import it, no other module references it).

So: the module's only present-day users are tests, but it sits inside the shipped package. Importing `poker_solver.parity.noambrown_wrapper` requires `numpy` (already a hard dependency) but does **not** require any external solver to be installed — the subprocess call happens only inside `run_brown_solver`.

## 3. Recommended import path

Two viable shapes, with the trade-off explicit:

**A. Keep current placement (`poker_solver/parity/`)** — preferred.
- Pros: differential wrappers can be reused by `references/` notebooks, CLI parity tooling, future fuzzers, or downstream packages that depend on `poker_solver`. The `parity/` namespace docstring already foreshadows future wrappers (`slumbot_wrapper`, `open_spiel_wrapper`).
- Cons: ships ~1.2K LOC of wrapper code to all consumers even if they never run the parity gate. Mitigated by (a) no extra runtime deps, and (b) the wrapper only `subprocess`-invokes the external binary when called.

**B. Move to `tests/parity/`** — viable if PR 7 wants strict test-only surface.
- Pros: zero production-API contract; deletable without bumping the package version; clearer license-attribution boundary.
- Cons: forecloses reuse from CLI parity tools and from `references/` notebooks; breaks the docstring-stated plan to host `slumbot_wrapper` / `open_spiel_wrapper` next to it.

**Recommendation:** keep under `poker_solver/parity/`. The sub-package is already documented as a long-lived home for diff-test wrappers, and the cost of having unused test infrastructure inside the shipped package is small (no transitive deps added, no runtime side effects on import).

## 4. Public API surface — should `parity.run_noambrown` be in `poker_solver.__all__`?

**No.** Three reasons, in priority order.

1. **Internal-by-convention.** Differential-test wrappers should be discoverable via `poker_solver.parity.<wrapper>` but not promoted to the top-level package surface. Promoting them blurs the boundary between "we solve poker" and "we cross-check against external solvers".
2. **Stability cost.** Anything in top-level `__all__` is a stability contract. Brown's binary CLI is external — its output schema (`game_value_p0`, infoset profile shape) can change between his releases. Re-exporting wrappers at top level signals a stability we don't control.
3. **Non-precedent.** `poker_solver/__init__.py` already does **not** re-export `poker_solver.profiler` symbols beyond `MemoryProbe`/`MemoryReport`/`StreetMemoryEntry`, and does **not** re-export `poker_solver.abstraction.equity_features` beyond `canonicalize_for_suit_iso`. The pattern is "promote a narrow public surface from each sub-package, leave the rest dotted." For `parity/`, the narrow surface is currently *empty* and that is the right starting point.

If a CLI helper (e.g. `poker_solver.cli parity …`) is added later that needs one entry point, **only that entry point** should land in top-level `__all__`, with the rest staying under `poker_solver.parity.noambrown_wrapper.*`.

## 5. License headers on new modules

Both new modules carry license context, but inconsistently:

- `poker_solver/parity/__init__.py` (sub-package root): docstring mentions Brown's MIT license but **carries no `Copyright` or `SPDX-License-Identifier` header**. This is consistent with the rest of the repo's modules (`poker_solver/__init__.py` has none either), so this is not a PR-7 regression — but if PR 7 is the first module to integrate MIT-licensed external code, it is a reasonable moment to introduce an SPDX header.
- `poker_solver/parity/noambrown_wrapper.py` (wrapper itself): docstring explicitly states:
  - The wrapped repo: `noambrown/poker_solver` (https://github.com/noambrown/poker_solver).
  - Its license: "MIT Licensed, Copyright (c) 2025 Noam Brown".
  - That **no source code from that repo is copied** (only public CLI flags + JSON output schema are consumed).
  - The wrapper's own license: "MIT (same as this project)".
  - Pointer to `references/code/noambrown_poker_solver/LICENSE` for the full text.

That is reasonable attribution for a subprocess-only wrapper. No SPDX header (`SPDX-License-Identifier: MIT`) on either file; adding one is optional but consistent with modern Python packaging.

**Verify before commit:** that `references/code/noambrown_poker_solver/LICENSE` actually exists and is the unmodified upstream MIT text. (Not checked here — out of audit scope.)

## 6. Concerns for the PR 7 commit

Priority order, most important first:

1. **`parity/__init__.py` exports nothing.** That is intentional and consistent with the rest of the repo's sub-package pattern, but PR 7's commit message should say so explicitly so future readers don't "helpfully" add re-exports. Recommend a one-line comment in `__init__.py`: `# Intentionally empty: import wrappers via poker_solver.parity.<wrapper>.`
2. **`HistoryRoot` is defined but not in `__all__`.** Line 1217 vs lines 1198–1213. Either add it to `__all__` (if intended as public) or move it above `__all__` with an underscore prefix (if internal). Tiny inconsistency, easy fix.
3. **No `__all__` or version on `parity/__init__.py`.** Adding `__all__: list[str] = []` would make the "intentionally empty" intent enforceable by linters.
4. **License attribution is in a docstring, not a header.** Acceptable but not best-practice for redistribution. Optional follow-up: add `SPDX-License-Identifier: MIT` as the first non-docstring line of both new files. Not blocking.
5. **No risk of accidental top-level export.** Confirmed: `poker_solver/__init__.py` does not import `parity` at all, so a stray `from poker_solver import RiverSpot` will correctly fail.
6. **Production-vs-test ambiguity is documentation-only, not behavioral.** No test-only deps leak into the package; the wrapper imports nothing that a non-test consumer wouldn't already have (`numpy`, stdlib, `poker_solver.card`, `poker_solver.solver`).

No blocking concerns. PR 7 commit can proceed; items 1–4 are polish.

---

## Summary table

| Check | Status | Note |
| --- | --- | --- |
| `parity/__init__.py` exports minimal? | Yes (zero exports) | Docstring-only; 21 LOC |
| Wrapper used by tests only? | Yes | Only import site is `tests/test_river_diff.py` |
| Module belongs in `poker_solver/`? | Yes (with caveat) | Logically test-only but reasonably reusable |
| Should parity be in `poker_solver.__all__`? | No | Internal-by-convention; controls stability surface |
| License attribution present? | Yes (docstring) | Could add SPDX header for rigor |
| Blocking issues for PR 7? | None | Items 1–4 above are polish |
