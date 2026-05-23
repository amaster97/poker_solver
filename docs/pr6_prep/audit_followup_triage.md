# PR 6 audit follow-up triage

**Source audit:** `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_report.md` §"Should-fix" (7 items, lines 98-112).
**Verdict:** READY-WITH-PATCHES (low-severity polish only; no must-fix gates).
**Deliverable:** triage table + exact apply-now patches + PR 4.5 scope additions.
**Read-only:** this document does NOT modify any files. Patches listed are pre-staged for execution after PR 6 commit lands and before PR 7 launches.

---

## 1. Triage table

| # | Audit item (one-line) | Decision | Owner sequence | Rationale |
|---|---|---|---|---|
| 1 | `ndarray = "0.16"` deserves explicit dep-row in CHANGELOG narrative | APPLY NOW (commit message only) | Commit pipeline | One-word edit to the commit body's "new deps" line; zero file delta. Audit-narrative correctness for v0.5.0 release notes. |
| 2 | `Cargo.toml [package].version = "0.2.0"` should bump for PR 6 surface | APPLY NOW | Commit pipeline | One-line edit. Already on the commit-prep checklist (audit §"Recommended commit-prep checklist" item 3). Aligns Rust crate version with Python `__version__ = "0.5.0"`. |
| 3 | `seed` parameter unused — docstring nudge OR wire into StdHasher | APPLY NOW (docstring nudge only) | Commit pipeline | Two-line docstring expansion at `hunl_solver.rs:278-281`. Spec §9 #13 explicitly defers the wire-up to PR 8. Audit recommends "smallest fix." |
| 4 | `target_exploitability` parameter unused — same docstring fix | APPLY NOW (docstring nudge only) | Commit pipeline | Same patch as #3; both args documented together. Single 4-line block at lines 278-281. |
| 5 | `_rust.so` stale-binary silent-skip — pre-commit recipe gap | DEFER (split: half NOW, half PR 6.5) | Commit pipeline (recipe) + PR 6.5 (loud-RuntimeError patch) | The `maturin develop --release` step is already in the commit recipe (audit §"Recommended commit-prep checklist" item 1). The test-file patch (silent `pytest.skip` → loud `RuntimeError`) is the "must-act top-3" item per the orchestrator prompt — **pre-staged, NOT applied** since the commit pipeline is touching `tests/test_hunl_diff.py`. Apply post-commit as PR 6.5 (or fold into PR 7's first commit). |
| 6 | `hunl_solver.rs:281` doc says `target_exploitability` is "no-op" but variable is `_target_exploitability` | APPLY NOW (rolled into #3/#4) | Commit pipeline | Same docstring block; resolves the underscore-prefix mismatch in one edit. Zero-cost piggyback. |
| 7 | `HUNLDcfr` is a private duplicate of `DCFRSolver<G>` (trait-widening needed) | DEFER (PR 4.5 → add to scope as 6-A, OR fold into PR 8 explicitly) | PR 4.5 OR PR 8 | Non-trivial trait-widening that touches `Game::infoset_key(player)` signature; impacts Kuhn / Leduc consumers too. NOT mechanical. Audit explicitly calls this out as "known maintenance debt" — log it; don't sneak it into PR 6. Default routing: **PR 8** (the broader Rust feature wave), since trait widening to accept abstraction reference is a strategic interface change, not a debt-sweep. **NOT a fit for PR 4.5** (which is mechanical-only per launch_kickoff.md §2). |

**Summary:**
- **APPLY NOW (with commit):** items 1, 2, 3, 4, 6 (five items; ~10 LoC across 2 files).
- **DEFER to PR 6.5 (post-commit, pre-PR-7):** item 5 (test-file silent-skip → loud-RuntimeError patch).
- **DEFER to PR 8 (strategic interface change):** item 7.

---

## 2. Exact apply-now patches

### Patch 2-A — `crates/cfr_core/Cargo.toml:3` (Item #2)

**Change:**

```diff
 [package]
 name = "cfr_core"
-version = "0.2.0"
+version = "0.5.0"
 edition = "2021"
 license = "MIT"
```

**Rationale:** Bump from `0.2.0` (PR 1 baseline) to `0.5.0` to match the planned Python `__version__ = "0.5.0"` cadence. Per audit §"Should-fix" item 2: "PR 6 ships substantial new functionality — `cdylib` test changes, new modules, new public API."

**Risk:** None. Maturin consumes the version via `pyproject.toml`'s own `version` field; the Rust crate version is informational for direct `cargo` consumers (none currently external).

---

### Patch 2-B — `crates/cfr_core/src/hunl_solver.rs:278-281` (Items #3, #4, #6 — bundled docstring nudge)

**Current text (lines 278-281):**

```rust
/// `target_exploitability` is currently a no-op (per spec §9 #13 option 1 —
/// the generic DCFR loop does not expose an early-exit hook; PR 8 may
/// revisit). `seed` is forward-compat; vanilla DCFR is deterministic given
/// identical iteration order.
```

**Proposed replacement:**

```rust
/// `_target_exploitability` and `_seed` are accepted for forward-compat with
/// PR 8 but are **no-ops in PR 6** (both variable names carry an underscore
/// prefix to suppress dead-code warnings — grep for `target_exploitability`
/// and `seed` without the prefix will return no hits inside the function
/// body). Per spec §9 #13 option 1, the generic DCFR loop does not expose
/// an early-exit hook; vanilla DCFR is deterministic given identical
/// iteration order, so the seed has no observable effect. PR 8 may wire
/// `_seed` into a `StdHasher` for `HashMap` insertion-order determinism and
/// `_target_exploitability` into an `exploitability::compute` poll loop.
```

**Rationale:** Bundles audit items 3, 4, and 6 into one edit. Resolves the underscore-prefix grep mismatch (item 6) by naming both prefixed and non-prefixed forms; resolves the buried-docstring concern (items 3/4) by stating both no-op statuses in the leading sentence; preserves the PR 8 forward-compat narrative.

**Risk:** None — comment-only. Verify: `cargo doc --package cfr_core --no-deps` renders the new docstring; `cargo clippy -- -D warnings` stays green (no rustdoc warnings).

---

### Patch 2-C — commit message narrative addition (Item #1)

**Change locus:** the PR 6 commit message body (not a file), specifically the "New deps" line.

**Current draft (per `docs/pr6_prep/commit_message_draft.md`):** likely says `New deps: ndarray-npy = "0.9"`.

**Replacement narrative:** `New deps: ndarray = "0.16", ndarray-npy = "0.9" (both MIT/Apache 2.0 dual; ndarray is the base crate required by ndarray-npy).`

**Rationale:** Audit §"Should-fix" item 1: the "new dep: only `ndarray-npy`" framing in `audit_prompt.md` was off-by-one; `ndarray` itself is a separate dep-row declaration at `Cargo.toml:30`. Both crates are MIT/Apache 2.0; informational fix only.

**Risk:** None — narrative-only.

---

## 3. Sequencing

**Order of operations:**

1. **PR 6 commit lands** to `pr-6-rust-hunl-port` branch with all 5 apply-now patches inline (2-A + 2-B + 2-C). Commit pipeline already plans the `maturin develop --release` step (item #5 partial).
2. **PR 6 audit-of-applied-patches** (lightweight re-verification: docstring renders, version bump consistent across `Cargo.toml` + `pyproject.toml`, commit body cites `ndarray`).
3. **PR 6 merges to `integration`** via `--no-ff`.
4. **PR 6.5 fires (immediately, pre-PR-7):** single-agent ~15-min patch to `tests/test_hunl_diff.py:55-61` — replace silent `pytest.skip("_rust extension unavailable")` with `raise RuntimeError(f"_rust extension required for diff tests but failed to import: {exc!r}; rebuild via `maturin develop --release`")`. This is the must-act top-3 item flagged by the orchestrator prompt.
5. **PR 7 launches** against `integration` post-6.5.

**Pre-staged PR 6.5 patch (DO NOT APPLY YET):**

**File:** `tests/test_hunl_diff.py:55-61`

**Current (defensive import + silent skip):**

```python
try:
    from poker_solver import _rust  # noqa: F401
except ImportError:
    pytest.skip("_rust extension unavailable", allow_module_level=True)
```

**Proposed (loud RuntimeError; halts collection, surfaces stale-binary architecture mismatch):**

```python
try:
    from poker_solver import _rust  # noqa: F401
except ImportError as exc:
    raise RuntimeError(
        f"_rust extension required for HUNL diff tests but failed to import: "
        f"{exc!r}. Rebuild via `maturin develop --release` from the project "
        f"root; common cause is a stale `.so` from a prior architecture "
        f"(x86_64 binary on arm64 host or vice versa)."
    ) from exc
```

**Why deferred:** the PR 6 commit pipeline is currently touching `tests/test_hunl_diff.py` (per audit's note about the test file's tolerance literals at lines 70-71). Editing the same file from two concurrent streams risks the no-concurrent-branch-ops violation logged in the user-memory rule. Stage as PR 6.5's sole patch; <5 min agent runtime.

**PR 6.5 alternative (cheap):** fold the patch into PR 7's first commit instead of spawning a dedicated PR. Decision: PR 6.5 is cleaner audit-trail-wise (single-purpose) but adds one merge cycle. **Recommend folding into PR 7's first commit** to avoid PR-proliferation churn; the orchestrator can re-decide at PR 7 launch time.

---

## 4. PR 4.5 scope additions

**Decision: no PR 4.5 additions from PR 6 audit.**

Rationale:
- Items 1-4, 6 are commit-pipeline polish — they belong with the PR 6 commit itself, not bundled into PR 4.5.
- Item 5 is the test-file loud-RuntimeError patch — better as PR 6.5 / PR 7's first commit (single-file, ~5 LoC); PR 4.5 is the *Python-side mechanical sweep* (license headers, ValueError narrowing, dead-code removal) and lives in a different file surface (`poker_solver/` not `tests/`).
- Item 7 (HUNLDcfr ↔ DCFRSolver collapse) requires `Game::infoset_key` trait widening to accept an optional `&AbstractionTables` — this is a strategic interface change (Kuhn / Leduc consumers must also be updated). NOT mechanical. **Routes to PR 8** as part of the broader Rust feature wave; flagged in the audit-followup-backlog rather than PR 4.5.

**PR 4.5 launch_kickoff.md §2 scope remains 13 items (unchanged).** No edits to `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md` from this triage.

---

## 5. Cross-references

- Audit source: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_report.md` §"Should-fix" (lines 98-112).
- Audit verdict: `/Users/ashen/Desktop/poker_solver/docs/pr6_prep/audit_report.md` §"Overall verdict" (lines 188-201; cites 4-item commit-prep checklist that maps to apply-now patches 2-A through 2-C plus the `maturin develop --release` recipe step).
- PR 4.5 scope: `/Users/ashen/Desktop/poker_solver/docs/pr4_5_audit_debt/launch_kickoff.md` §2 — no additions from PR 6 audit per §4 above.
- Audit-followup backlog: `/Users/ashen/Desktop/poker_solver/docs/audit_followup_backlog.md` — append PR 6 item 7 (HUNLDcfr trait-widening) as PR 8 candidate; append PR 6 item 5 (loud-RuntimeError) as PR 7-first-commit candidate.

---

## 6. Files touched (when patches apply)

**APPLY NOW (during PR 6 commit pipeline):**
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/Cargo.toml` (1 line: `version = "0.2.0"` → `"0.5.0"`).
- `/Users/ashen/Desktop/poker_solver/crates/cfr_core/src/hunl_solver.rs` (lines 278-281: 4-line docstring rewrite).
- PR 6 commit message body (narrative addition for `ndarray` dep-row).

**DEFER (PR 6.5 or PR 7 first commit):**
- `/Users/ashen/Desktop/poker_solver/tests/test_hunl_diff.py:55-61` (silent skip → loud RuntimeError).

**DEFER (PR 8 strategic):**
- `crates/cfr_core/src/dcfr.rs` (trait-widening for `Game::infoset_key`).
- `crates/cfr_core/src/hunl_solver.rs` (HUNLDcfr struct deletion + DCFRSolver<HUNLState> substitution).
- `crates/cfr_core/src/kuhn.rs`, `leduc.rs` (trait-widening propagation).

---

## 7. Net delta

- **Apply-now footprint:** 5 LoC delta across 2 files + 1 commit-message-narrative tweak. Sub-30-second agent runtime; can be folded into the existing PR 6 commit pipeline without a new wave.
- **PR 6.5 footprint:** 7 LoC delta in 1 file. ~5-min agent runtime if PR 6.5 fires; ~0 if folded into PR 7.
- **PR 8 footprint:** TBD; strategic, not mechanical. Tracked in audit-followup-backlog.

**No PR 4.5 impact.** PR 4.5's 13-item scope is unchanged.
