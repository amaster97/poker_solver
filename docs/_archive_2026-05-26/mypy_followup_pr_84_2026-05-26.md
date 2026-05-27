# mypy follow-up — PR 84 (post-cleanup PR #43)

**Date:** 2026-05-26
**Branch:** `pr-84-mypy-followup` (worktree at `/Users/ashen/Desktop/poker_solver_worktrees/pr-84-mypy`)
**PR:** https://github.com/amaster97/poker_solver/pull/46
**Scope:** the 7 substantive mypy errors that cleanup PR #43 (lint/clippy/format/deps) left out-of-scope per the brief's stop-rule.

## Before / after counts

| Run | Errors | Files |
|---|---|---|
| Before PR #43 | 10 | 6 (3 import-not-found, 7 substantive in 5 files) |
| After PR #43 (start of this PR) | **7** | 5 (substantive only; imports cleared by `ignore_missing_imports = true`) |
| After this PR | **0** | 0 — `Success: no issues found in 40 source files` |

## Per-error fix summary

### 1. `poker_solver/equity.py:200` — Sequence covariance

**Error:** `Incompatible types in assignment (expression has type "combinations[tuple[Card, ...]]", variable has type "Sequence[Sequence[Card]]")  [assignment]`

**Root cause:** `Sequence` is invariant in its type parameter; both `itertools.combinations` (an iterator) and `[()]: list[tuple[()]]` are not assignable to `Sequence[Sequence[Card]]`.

**Fix:** Switch `runouts` annotation to `Iterable[Sequence[Card]]`. `Iterable` is covariant by design and the loop only iterates `runouts` once, so it's sufficient. Added `Iterable` import from `collections.abc`.

### 2-3. `poker_solver/hunl.py:468-469` — tuple index out of range

**Error:** `Tuple index out of range  [misc]` on both `state.hole_cards[0]` and `state.hole_cards[1]`.

**Root cause:** `HUNLState.hole_cards: tuple[tuple[Card, Card], tuple[Card, Card]] | tuple[()]`. mypy can't index past `[0]` on the empty-tuple variant.

**Fix:** Add `assert len(hole) == 2` in `utility()` after the fold checks. Runtime invariant: a non-folded showdown always has dealt hole cards (chance nodes deal them before the first decision). Single narrow covers both lines.

### 4. `poker_solver/hunl.py:827` — int-overload on object

**Error:** `No overload variant of "int" matches argument type "object"  [call-overload]` — note: existing `# type: ignore[arg-type]` did not cover this error code.

**Root cause:** `_normalize_hole_action(action: object)` falls through to `int(action)` after the `isinstance(action, tuple)` check. `int()` does not accept arbitrary `object`.

**Fix:** Replace the wrong `# type: ignore[arg-type]` with an explicit `isinstance(action, (int, str))` narrow + `TypeError` on mismatch. Now mypy sees `int | str` going into `int(...)`, which matches the first overload.

### 5. `poker_solver/range_aggregator.py:699` — optional indexing inside lambda

**Error:** `Value of type "list[float] | None" is not indexable  [index]`

**Root cause:** The conditional expression `idx = 0 if probs is None else max(range(len(probs)), key=lambda i: probs[i])` does narrow `probs` for the `max()` call, but the lambda closure re-captures `probs` and mypy widens it back to `list[float] | None` inside the lambda body.

**Fix:** Rewrite as `if/else` and inside the `else` bind `probs_nn = probs` (a non-Optional local). The lambda captures `probs_nn` and stays narrow.

### 6. `poker_solver/cli.py:202` — tuple index out of range

**Error:** `Tuple index out of range  [misc]` on `subgame.initial_hole_cards[0]` / `[1]`.

**Root cause:** Same `tuple[...] | tuple[()]` union as hunl.py:468. `default_tiny_subgame()` always populates both pairs but mypy doesn't track that.

**Fix:** Add `assert len(hole) == 2, "default_tiny_subgame must define both hole pairs"` before indexing.

### 7. `ui/views/library_browser.py:248` — missing AppState attribute

**Error:** `"AppState" has no attribute "selected_library_spot_id"  [attr-defined]`

**Root cause:** The write `state.selected_library_spot_id = sid` is a forward-looking stash so spot_input.py can pick up the selection. The `AppState` dataclass never declared the field. The existing `try/except` around the write made it a runtime no-op, masking the type error.

**Fix:** Add `selected_library_spot_id: str | None = None` to the `AppState` dataclass (placed last because it has a default — required-field ordering preserved). Added a docstring noting the cross-view stash contract. The `try/except` is kept as defence-in-depth (harmless now that the attribute exists).

## Verification

```bash
cd /Users/ashen/Desktop/poker_solver_worktrees/pr-84-mypy

mypy poker_solver ui
# -> Success: no issues found in 40 source files

pytest tests/test_equity.py -x --timeout=60 -q                   # -> 8 passed
pytest tests/test_dcfr_diff.py -x --timeout=60 -q                # -> 5 passed
pytest tests/test_range_vs_range_aggregator.py -x --timeout=300 -q  # -> 21 passed
pytest tests/test_cli_subcommands.py -m "not slow" -x --timeout=60 -q  # -> 6 passed

ruff check                                                       # -> All checks passed
ruff format --check poker_solver ui                              # -> 40 files already formatted
```

Note on worktree environment: the worktree doesn't have `poker_solver/_rust.cpython-313-darwin.so` built (compilation via `maturin develop` would be required). For the Rust-backed tests (`test_dcfr_diff.py`, `test_range_vs_range_aggregator.py`), the symlink trick was used:

```bash
ln -s /Users/ashen/Desktop/poker_solver/poker_solver/_rust.cpython-313-darwin.so \
      /Users/ashen/Desktop/poker_solver_worktrees/pr-84-mypy/poker_solver/_rust.cpython-313-darwin.so
```

`.so` files are gitignored, so the symlink doesn't pollute the commit.

## Constraints honoured

- No `pyproject.toml` edits (PR #43 already configured `[tool.mypy]`).
- No behavioural change — all fixes are type-only (asserts/narrowing/closure binding/dataclass field add). The two `assert`s codify pre-existing runtime invariants that would have crashed downstream anyway. The `TypeError` in `_normalize_hole_action` is reachable only via a contract violation (wrong action type), which was previously an opaque `int(object)` crash.
- No new dependencies.

## Files touched (5)

- `poker_solver/cli.py` — +7, -1
- `poker_solver/equity.py` — +8, -2
- `poker_solver/hunl.py` — +15, -3
- `poker_solver/range_aggregator.py` — +7, -1
- `ui/state.py` — +4, -0

Total: 5 files changed, 41 insertions(+), 7 deletions(-).
