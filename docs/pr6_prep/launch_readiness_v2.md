# PR 6 launch readiness — v2

**Date:** 2026-05-22
**Reviewer:** orchestrator audit agent (post-PR-4-merge + post-PR-3.5-follow-up)
**Inputs reviewed:**
- `docs/pr6_prep/pr6_spec.md` (canonical spec, 720 lines, header amended 2026-05-21)
- `docs/pr6_prep/agent_a_prompt.md` (527 lines)
- `docs/pr6_prep/agent_b_prompt.md` (570 lines)
- `docs/pr6_prep/agent_c_prompt.md` (501 lines)
- `docs/pr6_prep/audit_prompt.md` (180 lines)
- `docs/autonomous_log.md` (PR 4 amendments, S2 + spec consistency fixes)
- `docs/spec_consistency_review_v2.md` (NEW-1 + NEW-3 findings)
- `poker_solver/abstraction/{buckets,equity_features,emd_clustering,precompute}.py` (committed PR 4 code)
- `poker_solver/hunl.py` (HUNLConfig.abstraction definition)

## Verdict: **NEEDS-PATCH**

Spec body and prompts have **substantive drift from the committed PR 4 code**. The agents will produce a Rust abstraction loader that fails parity testing against Python because the spec describes a *different on-disk layout* than what `save_abstraction` actually writes.

## Verification checklist (per launch-readiness checks)

### Check 1: PR 4 public API references (PARTIAL DRIFT)

The committed PR 4 public API surface (per `poker_solver/abstraction/buckets.py`):

```python
class AbstractionTables:
    flop_assignments, turn_assignments, river_assignments  # np.uint8
    flop_board_index, turn_board_index, river_board_index  # dict[str, int]
    flop_hand_index, turn_hand_index, river_hand_index     # dict[str, dict[str, int]]
    metadata: dict[str, object]
    source_path: Path | None  # populated by load_abstraction()

class AbstractionRef:
    source_path: str
    version: str

def resolve_abstraction_ref(ref) -> AbstractionTables  # LRU-cached
def lookup_bucket(tables, board, hole_cards, street) -> int
def load_abstraction(path) -> AbstractionTables
def save_abstraction(tables, path) -> None
```

The PR 6 spec §4.4 and Agent B's prompt §"From abstraction.rs" both describe a DIFFERENT shape:

```rust
// SPEC SAYS (drift):
pub struct AbstractionTables {
    pub flop_assignments: Vec<u8>,
    pub flop_board_index: Vec<u32>,        // SHOULD BE: HashMap<String, u32>
    pub flop_hand_lookup: HandLookup,      // SHOULD BE: HashMap<String, HashMap<String, u32>>
    // ... bucket_counts: [u16; 3]         // NOT a top-level field on Python side
    // ... feature_bins, seed              // ARE in metadata, not top-level
}
```

The Python `lookup_bucket` keys are **string** `canonical_board_key` / `canonical_hand_key` (produced by `canonicalize_for_suit_iso`), NOT integer `u32` IDs as the spec implies with `_canonical_board_id() -> u32`.

**Drift sources:**
- pr6_spec.md:251-261 (Stage-5 layout sketch shows `flop_board_index: uint32[1755]` — wrong; actual layout is JSON-bytes dict).
- pr6_spec.md:268-296 (Rust `AbstractionTables` shape with `HandLookup` + top-level `bucket_counts`/`schema_version`/`feature_bins`/`seed` — these aren't separate top-level fields; Python carries them in `metadata`).
- agent_b_prompt.md:101-130 (same drift: `HandLookup` struct + top-level scalar fields).
- agent_b_prompt.md:155-156 (`_canonical_board_id() -> u32`, `_canonical_hand_key() -> u32` — Python returns `str` keys, NOT u32).
- spec §4.4 says "metadata is one nested dict" (correct) but body still shows `bucket_counts` as a top-level field on `AbstractionTables` (inconsistent).

### Check 2: `HUNLConfig.abstraction: AbstractionRef | None` (PASS)

Python correctly declares `abstraction: AbstractionRef | None` at `poker_solver/hunl.py:118`. Prompts and spec correctly reference this on the Python side.

### Check 3: NOT mention `AbstractionTables | None` as HUNLConfig field (PASS)

Grepped all four prompts: zero occurrences of `AbstractionTables | None` as a `HUNLConfig` field type. The pre-amendment phrasing is fully purged from PR 6 docs. (Note: spec_consistency_review_v2.md flags NEW-1 in *PR 4's spec* §3.5 + §8 still has stale `AbstractionTables | None`, but PR 6 prompts are clean.)

### Check 4: slumbot2019 cited for hand-eval; NOT postflop-solver (PASS)

- agent_a_prompt.md:55 + module-docstring template lines 305-309 cite `slumbot2019/src/hand_value_tree.cpp (MIT)` for the 7-card eval pattern.
- agent_b_prompt.md:59 cites `slumbot2019/src/card_abstraction*.cpp (MIT)` for abstraction layout.
- All four prompts (a, b, c, audit) explicitly call postflop-solver "AGPL — NEVER copy" and frame it as read-only inspiration only.
- EMD/kmeans are NOT in PR 6 scope (PR 4 already ported kmeans via slumbot pattern). Correctly omitted from PR 6 prompts.

### Check 5: PR 9 §6 canonical dispatch composition (FAIL — NOT CITED)

Grepped agent A/B/C and audit prompts for "PR 9 §6" / "PR 9 spec §6" / "canonical dispatch": **zero matches**. The audit_prompt.md does NOT instruct the auditor to verify `_solve_rust` HUNL branch composes correctly with PR 3.5 push/fold short-circuit (which PR 9 §6 declares canonical). Agent B's prompt for the `_solve_rust` HUNL branch (lines 281-313) shows the postflop-only branch without referencing the PR 9 §6 ordering invariant. Risk: Agent B may insert the HUNL branch in a position that breaks PR 3.5's short-circuit-first dispatch invariant.

### Check 6: 5e-3 / 1e-3 tolerance (PASS)

- agent_c_prompt.md:90-121 codes `1e-3` for river-subgame test, `5e-3` for flop fixture test, with `1e-6` absolute floor.
- agent_a_prompt.md:74 and agent_b_prompt.md:75 lock D7 = "1e-3 (river-only), 5e-3 (flop fixture)".
- audit_prompt.md:69-73 calls out anti-pattern: "if test tolerance is silently looser than spec (e.g., 1e-2 or 5e-2), flag as must-fix".
- No occurrence of stale `1e-4` outlier in any PR 6 prompt.

### Check 7: License attributions (PASS)

- noambrown MIT cited for `river_game.{h,cpp}`, `cards.{h,cpp}`, `trainer.{h,cpp}` patterns in spec §3 + agent_a + agent_b prompts.
- slumbot2019 MIT cited for `hand_value_tree.cpp` (eval) and `card_abstraction*.cpp` (layout).
- postflop-solver + TexasSolver explicitly "AGPL — NEVER copy" with shark-2.0 "Unlicensed — never study" in every prompt.
- Module-level attribution template specified verbatim per file in agent_a + agent_b prompts.
- audit_prompt.md focus area #1 is a HARD audit gate with grep checks for distinctive AGPL names (`bunching`, `valid_indices`, `isomorphism_swap`, `flatten_action_tree`).

## Top 3 findings (ranked by blast radius)

1. **Spec `AbstractionTables` Rust shape contradicts committed PR 4 code (CRITICAL).** PR 4 ships `*_board_index: dict[str, int]` + `*_hand_index: dict[str, dict[str, int]]` keyed by **string** canonical keys, with metadata as a JSON-encoded blob. PR 6 spec §4.4 + Agent B's prompt describe `*_board_index: Vec<u32>` + `*_hand_lookup: HandLookup` keyed by integer IDs, with `bucket_counts`/`schema_version`/`feature_bins`/`seed` as top-level fields. Agent B will produce a loader that fails to parse the actual .npz. The 10K-input bucket-roundtrip canary will fail immediately.

2. **`AbstractionRef` resolution helper not referenced (HIGH).** PR 4 ships `resolve_abstraction_ref(ref) -> AbstractionTables` as the canonical LRU-cached resolver. Agent B's `_solve_rust` branch (agent_b_prompt.md:281-313) reaches into `game.config.abstraction.source_path` directly instead of using the public `resolve_abstraction_ref()` API. This bypasses the LRU cache and the version-check that the resolver enforces, causing re-loads on every solve call and silent version mismatches.

3. **PR 9 §6 canonical dispatch invariant not propagated (MEDIUM).** No prompt mentions that `_solve_rust`'s new HUNL branch must compose with PR 3.5's push/fold short-circuit per PR 9 §6's declared ordering. Agent B's example code shows only the HUNL elif branch; if inserted before the push/fold check, ≤15 BB postflop configs route to Rust HUNL solver instead of the push/fold chart fast path. Audit prompt does not call this out as a must-check.

## Recommended actions before PR 6 launch

1. **Patch pr6_spec.md §4.4 + agent_b_prompt.md "From abstraction.rs"** to match the committed PR 4 shape: `dict[str, int]` board indices, `dict[str, dict[str, int]]` hand indices, single `metadata: HashMap<String, serde_json::Value>` field instead of broken-out top-level scalars. Update `lookup_bucket` signature to use string keys (or document the canonicalize-then-stringify path that the Rust port must follow to produce the same dict keys Python writes).

2. **Patch agent_b_prompt.md §6.1 `_solve_rust` example** to use `from poker_solver.abstraction.buckets import resolve_abstraction_ref` and call `resolve_abstraction_ref(game.config.abstraction)` — leverage the LRU cache and version check rather than reaching into `.source_path` directly. Pass `tables.source_path` (Path) through to `_rust_solve_hunl` only after resolving.

3. **Amend audit_prompt.md** to add a check that the HUNL branch in `_solve_rust` is inserted AFTER the push/fold short-circuit and BEFORE the preflop branch, matching PR 9 §6 canonical ordering. Cite the §6 canonical declaration explicitly.

4. **Decide on string-vs-integer canonicalization in Rust.** Python's `canonical_board_key` is a sorted card-string; Rust should either (a) produce the same string keys (simpler; allows reuse of Python dicts as-is via serde), or (b) introduce a Rust-only u32 packing layer with byte-parity tests against Python's string keys. Spec currently implies (b) but PR 4 commits to (a). Pick one and propagate.

5. **Re-run consistency review v3** post-patch before launching A/B/C agents. The four PR-6 docs need to be internally consistent against the committed PR 4 code, not against the PR 4 spec at the time PR 6 prompts were drafted.

## Per-check summary

| # | Check | Status |
|---|---|---|
| 1 | PR 4 public API correctly referenced | PARTIAL — see finding #1 |
| 2 | HUNLConfig.abstraction: AbstractionRef \| None | PASS |
| 3 | NO `AbstractionTables \| None` as field type | PASS |
| 4 | slumbot2019 MIT for EMD/eval; NOT postflop-solver | PASS |
| 5 | PR 9 §6 canonical dispatch cited | FAIL — finding #3 |
| 6 | 5e-3 / 1e-3 tolerance (not 1e-4) | PASS |
| 7 | noambrown/slumbot MIT; postflop-solver NEVER | PASS |

**Net:** 5 PASS, 1 PARTIAL, 1 FAIL. Hold A/B/C launch until findings #1–#3 are patched. PR 6 cannot ship if Agent B builds the Rust loader against the spec'd shape — the diff tests will fail at the 10K-input bucket-roundtrip canary because the on-disk `.npz` doesn't have integer board-index arrays.
