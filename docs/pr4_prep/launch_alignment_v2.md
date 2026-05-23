# PR 4 final launch alignment check v2

**Date:** 2026-05-21
**Reviewer:** alignment-check agent (post-consistency-v2 patches)
**Inputs reviewed:**
- `docs/pr4_prep/pr4_spec.md` (latest, includes consistency v2 amendments)
- `docs/pr4_prep/agent_a_prompt.md` (latest, patched for AbstractionRef)
- `docs/pr4_prep/agent_b_prompt.md` (latest)
- `docs/pr4_prep/agent_c_prompt.md` (latest)
- `docs/pr4_prep/audit_prompt.md`
- `docs/pr4_prep/postflop_solver_emd_patterns.md`
- `docs/pr4_prep/launch_readiness_report.md`
- `docs/spec_consistency_review_v2.md`

## Verdict

**NEEDS-PATCH** — 4 issues found; 2 are load-bearing (will produce broken contract between Agent B's impl and Agent C's tests), 2 are documentation-quality. The patches are small (≤20 lines total across 2 files). No regressions vs. the previous launch-readiness report; the previously-flagged Patch #1 (`lookup_bucket_via_ref`) is still **not applied** and has morphed into a slightly different shape (`resolve_abstraction_ref` instead). Additionally, the `AbstractionRef` dataclass itself is referenced but never declared in Agent B's public API surface.

---

## Per-check findings

### Check 1. Three implementation prompts internally consistent with each other

**Status: FAIL — 2 cross-prompt inconsistencies.**

#### Cross-prompt signature comparison

All function signatures listed in the previous launch-readiness report (compute_*_features, equity_distribution, canonicalize_for_suit_iso, emd_1d, batch_emd, kmeans_emd, KMeansResult, lookup_bucket, save/load_abstraction, build_abstraction) remain consistent across Agent A's "Public API contract" (agent_a_prompt L67-279), Agent B's "Agent A's exports you depend on" (agent_b_prompt L62-90), and Agent C's "Public API you test" (agent_c_prompt L45-98).

Default value table:
| Decision | Agent A | Agent B | Agent C |
|---|---|---|---|
| D1 (suit-iso INCLUDED) | L54 ✓ | L52 ✓ | L130 ✓ |
| D2 (MC at 200K iter) | L55 ✓ | L53 ✓ | L131 ✓ |
| Bucket counts (256, 128, 64) | L56 ✓ | L54 ✓ | L132 ✓ |
| H=50 | L57 ✓ | L67 ✓ | L133 ✓ |
| .npz format | n/a | L55 ✓ | L134 ✓ |
| schema_version=1 | n/a | L56 ✓ | L135 ✓ |
| Preflop returns -1 | n/a | L482 ✓ | L136, L164 ✓ |
| No new deps | L60 ✓ | L59 ✓ | L137 ✓ |

File ownership table (agent_a/b/c L17-34, L17-36, L17-32): **zero overlap**, reciprocally enumerated.

#### Inconsistency 1.A (LOAD-BEARING) — `HUNLConfig.abstraction` value type mismatch in Agent C integration test

`agent_c_prompt.md:182` says: *"override `HUNLConfig(..., abstraction=loaded_table)`"* — but `loaded_table` is an `AbstractionTables`. The locked contract (post-NEW-1, see Check 2 below) requires `HUNLConfig.abstraction: AbstractionRef | None` — so the test should pass an `AbstractionRef`, not the loaded tables.

**Consequence:** Agent C's `test_tiny_subgame_with_abstraction_produces_bucketed_infosets` will not type-check against Agent B's `HUNLConfig` field type. Agent C may attempt to instantiate `HUNLConfig(abstraction=AbstractionTables(...))` and either (a) silently get accepted if the field is loosely typed, leading to a wrong test, or (b) get rejected, causing Agent C's test to fail for the wrong reason.

#### Inconsistency 1.B (LOAD-BEARING) — `AbstractionRef` dataclass NOT declared in Agent B's public API

`agent_b_prompt.md:331` declares `HUNLConfig.abstraction: "AbstractionRef | None"`, and L334 says `AbstractionRef` is "declared in `poker_solver/abstraction/buckets.py` alongside `AbstractionTables`". However the §"Public API you produce → buckets.py" section (L96-221) only declares `AbstractionTables`, `lookup_bucket`, `save_abstraction`, `load_abstraction`. **`AbstractionRef` is never given an explicit dataclass declaration** in Agent B's prompt despite being referenced in `HUNLConfig`'s field annotation and the `infoset_key` snippet. The dataclass body is documented in `pr4_spec.md:159-163` (`@dataclass(frozen=True) class AbstractionRef: source_path: str; version: str`) but Agent B's prompt doesn't echo it as a declared deliverable.

**Consequence:** Agent B may produce code where `AbstractionRef` is mentioned but not actually declared. Agent C cannot import `AbstractionRef` (it's not in the `__init__.py` re-export list at L286-323 either). Test code at agent_c_prompt L182 wants to construct an `AbstractionRef` but has no import path.

### Check 2. Prompts match the latest PR 4 spec (post-amendments)

**Status: PASS (with 1 cosmetic spec-side drift).**

- The PR 4 spec `pr4_spec.md:3` header amendment declares `HUNLConfig.abstraction: Optional[AbstractionRef]` + metadata-as-nested-dict-JSON-encoded. The amendments are propagated to:
  - spec §3.5 line 53 ✓ (post-NEW-1 patch)
  - spec §6 line 156 ✓
  - spec §8 line 354 ✓
- All three prompts use the new `AbstractionRef | None` type for the field (a/b/c verified above in Check 1.A).
- Spec §4 Stage 5 body (`pr4_spec.md:120-136`) still describes `metadata` as a literal dict layout without naming the JSON-bytes-encoding wrapper. This is the **NEW-2 cosmetic** from `spec_consistency_review_v2.md:86-88`; the header amendment is authoritative. Agent B's prompt at L197-198 covers the JSON-encoding requirement directly, so Agent B will get this right despite the spec body's silence.
- D1 (suit-iso INCLUDED) is in `autonomous_log.md` and propagated through all three prompts, but PR 4 spec §4 Stage 4 (`pr4_spec.md:109-112`) and §8 line 351 still describe the **pre-D1** "no suit-iso in PR 4" prose. The previous launch-readiness report's **Patch #2** flagged this; it was not applied. Risk: a careful agent reads spec first, encounters pre-D1 prose, then reads prompt D1 override. Not blocking, since prompts override authoritatively.

### Check 3. Audit prompt matches the implementation prompts

**Status: FAIL (1 entry stale — the `lookup_bucket_via_ref` / `resolve_abstraction_ref` gap from previous launch-readiness Patch #1).**

- Audit prompt L74, L110, L111 references only `lookup_bucket(tables, ...)`. This matches Agent B's declared public API (L162-181) and Agent C's tests.
- However, Agent B's `infoset_key` snippet at L348-354 uses `resolve_abstraction_ref(cfg.abstraction)` (note: different name than the previous launch-readiness report's `lookup_bucket_via_ref` — the patch shape has morphed slightly). `resolve_abstraction_ref` is **not declared** in:
  - Agent B's public API section L96-221
  - Agent B's `__init__.py` re-exports L286-323
  - Agent C's test surface L75-97
  - Audit prompt focus areas
- Audit prompt L77-80 covers `AbstractionRef` field type but doesn't ask the auditor to verify the ref→tables resolver function exists / is reachable from public API.

**Consequence:** Audit agent will not check whether the resolver function is declared / tested. If Agent B implements `resolve_abstraction_ref` as a private helper (`_resolve_abstraction_ref`), no test reaches it directly; Agent C's `test_tiny_subgame_with_abstraction_produces_bucketed_infosets` indirectly exercises it through `infoset_key`. The audit prompt should explicitly call this out.

### Check 4. Prompts cite slumbot2019 (MIT) as EMD inspiration, NOT postflop-solver

**Status: PASS (but documentation could be sharper).**

Searched all three impl prompts + audit_prompt for `slumbot`, `postflop-solver`, and EMD-related citations:

| Prompt | EMD-pattern source cited | Postflop-solver disposition |
|---|---|---|
| agent_a_prompt L343-345 | `slumbot2019/src/build_kmeans_buckets.cpp` (MIT), `kmeans.cpp::SeedPlusPlus` (MIT), `build_rollout_features.cpp` (MIT) | L349: "AGPL v3. Read-only inspiration. No code copy." |
| agent_b_prompt L506 | `slumbot2019/src/build_kmeans_buckets.cpp` (MIT) — build-pipeline shape | L510: "AGPL v3, read-only inspiration only. No code copy." |
| agent_c_prompt L231 | (tests are first-party; no source cited) | "AGPL repos: postflop-solver, TexasSolver — no copy" |
| audit_prompt L83-86 | Slumbot's `build_kmeans_buckets.cpp` (MIT — attributable) | "NOT copy code from postflop-solver (AGPL)" |

**No prompt cites postflop-solver as an EMD-pattern source.** All four prompts correctly direct EMD/k-means inspiration to slumbot2019 (MIT) and call out postflop-solver as AGPL no-copy.

**Should-improve:** None of the prompts explicitly cite the new finding from `postflop_solver_emd_patterns.md` (the report that says "postflop-solver does not perform any abstraction, so it's the wrong reference for EMD bucketing"). A careful agent might still try to mine postflop-solver for EMD patterns and find none, wasting build time. Cross-reference would prevent this.

### Check 5. AGPL-trap warning (HAND_TABLE in postflop-solver) appears in the prompts

**Status: FAIL — warning exists only in the report, not in the prompts.**

Searched for `HAND_TABLE`, `hand_table`:
- `docs/pr4_prep/postflop_solver_emd_patterns.md` discusses the HAND_TABLE AGPL trap at L171, L191, L517, L569, L583, L587.
- **Zero hits** in any of the four implementation/audit prompts (`agent_{a,b,c}_prompt.md`, `audit_prompt.md`).

The HAND_TABLE warning is specifically about regenerating (vs copying) the 4824-i32 lookup table in postflop-solver's hand evaluator. PR 4 Agent A imports `poker_solver.evaluator.evaluate` (existing PR 1 evaluator), so the agent should never go anywhere near postflop-solver's evaluator. But if Agent A or Agent B is tempted to optimize Stage 1 by inlining a faster evaluator, they could land in this trap unknowingly. The audit prompt L82-87 covers "zero AGPL contamination" generally but doesn't name the HAND_TABLE specifically.

**Consequence:** If an implementation agent ports a precomputed evaluator table from postflop-solver, the audit may not catch it because the audit grep is for `postflop-solver/src/` function names, not for the specific data-table pattern.

### Check 6. Cross-PR dependencies clear

**Status: PARTIAL (PR 3 dependency clear; PR 3.5 push/fold dispatch dependency not actually a PR 4 concern).**

- PR 4 depends on PR 3 (HUNLPoker, HUNLConfig, Street enum, infoset_key): clearly documented in all four prompts. Agent B explicitly says PR 3 lossless behavior must be preserved (agent_b L463, L46, L527). Agent C has `test_pr3_tiny_subgame_still_passes_without_abstraction` as test #1 of the integration file (L181). Spec §6 line 171, §11 line 439, §3.5 line 51 all reference PR 3.
- PR 3.5 push/fold dispatch precedence: **PR 4 does not actually depend on this**. PR 4 only modifies `HUNLPoker.infoset_key` (which runs after a HUNLState exists; push/fold dispatch happens at the solver-routing layer in PR 5+ when consuming the abstraction artifact). The user's question (Check 6 of the task brief) presumably refers to *forward-looking* coordination: PR 4's `HUNLConfig.abstraction` field should not interfere with PR 5's dispatch precedence (push/fold ≤15 BB → postflop → preflop → error per PR 9 §6 canonical). Since PR 4 only adds an optional field with default None, this is structurally non-interfering, and none of the prompts need to reference PR 9 §6. **Status: no patch needed**.
- PR 6 forward-compat (AbstractionRef separated from AbstractionTables): documented in spec §3.5 + §6 + §8, in Agent B's prompt L43, L57 (source_path field), and in audit prompt L77-80. Consistent.

---

## Recommended patches

### Patch #1 (LOAD-BEARING) — declare `AbstractionRef` dataclass + `resolve_abstraction_ref` in Agent B's public API + re-exports

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_b_prompt.md`
**Where:** Insert `AbstractionRef` dataclass declaration into §"Public API you produce → `buckets.py`" immediately AFTER `AbstractionTables` (between current L159 and L162). Also insert `resolve_abstraction_ref` function declaration after `load_abstraction` (after current L220). Also add both names to the `__init__.py` re-export list (L286-323) and `__all__` (L307-322).

Insert after L159 (end of `AbstractionTables` field declarations):

```python
@dataclass(frozen=True)
class AbstractionRef:
    """Lightweight reference to an on-disk abstraction artifact.

    Stored on HUNLConfig.abstraction (instead of the full AbstractionTables)
    so that PR 6's Rust solver can pass a path across the PyO3 boundary
    without serializing the entire (up to 750 MB) bucket table.

    Callers materialize the in-memory tables via load_abstraction(ref.source_path).
    """
    source_path: str   # absolute path to the .npz on disk
    version: str       # e.g. "v1"; matches metadata['schema_version']
```

Insert after L220 (end of `load_abstraction`):

```python
def resolve_abstraction_ref(ref: AbstractionRef) -> AbstractionTables:
    """Resolve an AbstractionRef to a cached AbstractionTables.

    The cache is process-local module state, keyed on ref.source_path.
    Subsequent calls with the same path return the same tables instance
    (no re-load, no re-parse). Used by HUNLPoker.infoset_key so that
    HUNLConfig holds only the AbstractionRef (path + version), never the
    materialized bucket table.

    Raises:
        FileNotFoundError: if ref.source_path doesn't exist on disk.
        ValueError: if loaded artifact's schema_version doesn't match ref.version.
    """
    ...
```

Add to `__init__.py` re-exports (L286-323):
```python
from poker_solver.abstraction.buckets import (
    AbstractionRef,                # new
    AbstractionTables,
    load_abstraction,
    lookup_bucket,
    resolve_abstraction_ref,       # new
    save_abstraction,
)
```

Add to `__all__`:
```python
"AbstractionRef",
"resolve_abstraction_ref",
```

### Patch #2 (LOAD-BEARING) — fix Agent C's integration test #2 to use `AbstractionRef`

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_c_prompt.md`
**Where:** L182.

Edit:
- OLD: "load it into the `default_tiny_subgame()` config (override `HUNLConfig(..., abstraction=loaded_table)`)."
- NEW: "load it into the `default_tiny_subgame()` config (override `HUNLConfig(..., abstraction=AbstractionRef(source_path=str(path), version='v1'))`)."

Also update Agent C's §"Agent B produces" snippet L75-97 to include the `AbstractionRef` dataclass + `resolve_abstraction_ref` function signatures so Agent C is aware of them:

Insert after L88 (after `source_path: Path | None = None  # B2 amendment`):
```python
@dataclass(frozen=True)
class AbstractionRef:
    source_path: str
    version: str

def resolve_abstraction_ref(ref: AbstractionRef) -> AbstractionTables: ...
```

Optionally add Agent C test: `test_resolve_abstraction_ref_caches_load` — calling `resolve_abstraction_ref` twice on the same ref returns the same tables instance (cache check).

### Patch #3 (documentation-quality) — audit prompt covers `AbstractionRef` + resolver

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/audit_prompt.md`
**Where:** Append to Check 7 (L77-80).

Add:
- Verify `AbstractionRef` is declared as a frozen dataclass in `poker_solver/abstraction/buckets.py`.
- Verify `resolve_abstraction_ref(ref)` function exists, is in the public API (`poker_solver/abstraction/__init__.py`), and caches loads by `ref.source_path`.
- Verify `HUNLPoker.infoset_key` uses `resolve_abstraction_ref(cfg.abstraction)` to materialize the cached tables (does NOT hold a direct `AbstractionTables` reference on `HUNLConfig`).

### Patch #4 (documentation-quality) — note `postflop_solver_emd_patterns.md` finding in prompts

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_a_prompt.md`, `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_b_prompt.md`
**Where:** Add to the "License-aware sourcing" section a redirect-line.

Insert in agent_a_prompt after L350:
```
**Note (per `docs/pr4_prep/postflop_solver_emd_patterns.md`):** postflop-solver
performs NO card abstraction (no EMD, no k-means; lib.rs:17 says verbatim
"The solver does not perform any abstraction"). It is the WRONG reference
for EMD/clustering patterns — use slumbot2019 (MIT) above. Specifically,
DO NOT copy the `HAND_TABLE` literal (`hand_table.rs`, ~4824 i32 entries) —
this is the central AGPL trap. Our `poker_solver.evaluator.evaluate` is
the production path; don't try to inline a faster evaluator from postflop-solver.
```

Similar block for agent_b_prompt after L511.

---

## Summary table — pre-launch readiness deltas

| Issue | Source | Severity | Status | Patch |
|---|---|---|---|---|
| Previous launch-readiness Patch #1 (`lookup_bucket_via_ref` undeclared) | launch_readiness_report.md | LOAD-BEARING | NOT APPLIED — morphed into `resolve_abstraction_ref` undeclared | Patch #1 above |
| Agent C test #2 passes wrong value type | This audit Check 1.A | LOAD-BEARING | NEW finding | Patch #2 above |
| `AbstractionRef` declared in spec but not in Agent B's public API surface | This audit Check 1.B | LOAD-BEARING | NEW finding | Patch #1 above |
| Audit prompt blind to `AbstractionRef` resolver | This audit Check 3 | DOC-QUALITY | NEW finding | Patch #3 above |
| HAND_TABLE AGPL trap warning absent from prompts | This audit Check 5 | DOC-QUALITY | NEW finding | Patch #4 above |
| Previous launch-readiness Patch #2 (D1 override in spec §4 Stage 4 + §8 L351) | launch_readiness_report.md | DOC-QUALITY | NOT APPLIED | (optional; not in this report's recommended patches) |
| Previous launch-readiness Patch #3 (function-style vs method-style at spec L53) | launch_readiness_report.md | COSMETIC | NOT APPLIED | (deferred) |
| Spec §4 Stage 5 body silent on JSON-bytes wrapper (NEW-2) | spec_consistency_review_v2.md | COSMETIC | NOT APPLIED | (deferred; header amendment authoritative) |

---

## Recommended launch order

After applying Patch #1 + Patch #2 (load-bearing, ~25 lines total across `agent_b_prompt.md` + `agent_c_prompt.md`), the fan-out can launch in parallel as previously recommended. Patches #3 and #4 are documentation polish and can be deferred to a post-launch cleanup wave.

**Without Patch #1 + Patch #2:** Agent B will produce `resolve_abstraction_ref` as an undeclared internal helper, Agent C's `test_tiny_subgame_with_abstraction_produces_bucketed_infosets` will fail with a type error when constructing `HUNLConfig(abstraction=AbstractionTables(...))` against the `AbstractionRef | None` field, and the audit agent will not catch either issue because neither symbol is in its focus list.

---

## What was previously declared READY-WITH-PATCHES but remained un-patched

The previous launch-readiness report (`launch_readiness_report.md` 2026-05-21) flagged 3 patches:
1. **Patch #1** (load-bearing): declare `lookup_bucket_via_ref` in public API → **NOT APPLIED**; instead, the helper got renamed to `resolve_abstraction_ref` inline in Agent B's `infoset_key` snippet (still undeclared). Carrying forward as Patch #1 above with the new name.
2. **Patch #2** (doc-quality): note D1 override in pr4_spec.md §4 Stage 4 + §8 — **NOT APPLIED**. Low priority; prompts override.
3. **Patch #3** (cosmetic): function-style `lookup_bucket(tables, ...)` consistency in spec §3.5 — **NOT APPLIED**. Cosmetic.

The orchestrator must apply at minimum Patch #1 + Patch #2 from this report before launching the PR 4 fan-out. The remaining items can be deferred or batched into a documentation-polish wave.
