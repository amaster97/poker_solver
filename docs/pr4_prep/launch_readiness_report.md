# PR 4 prompts launch-readiness report

**Date:** 2026-05-21
**Reviewer:** orchestrator pre-launch consistency agent
**Inputs reviewed:** `pr4_spec.md`, `agent_a_prompt.md`, `agent_b_prompt.md`, `agent_c_prompt.md`, `audit_prompt.md`, `spec_consistency_review_v2.md`, `autonomous_log.md`

## Verdict

**READY-WITH-PATCHES** — 3 small patches recommended before launch (one is load-bearing, two are documentation-quality). No hard blockers; the fan-out can run safely if even just patch #1 is applied. Patches 2-3 reduce the risk of mid-build confusion / spec-ambiguity flags from agents.

---

## Per-check findings

### Check 1. Type signatures consistent across all 3 prompts

**Status: PASS (with one named-export ambiguity flagged below in Check 7).**

Cross-prompt signature comparison:

| Function | Spec (§8 / §5) | Agent A prompt | Agent B prompt | Agent C prompt |
|---|---|---|---|---|
| `compute_river_features(boards, hands_per_board, H=50, mode="mc", mc_iterations=200_000, seed=42, progress=False) -> np.ndarray` | §8 Agent A | matches (L121-139) | matches in deps (L70-71) | matches (L51-52) |
| `compute_turn_features(...)` | §8 Agent A | matches (L142-153) | matches (L73) | matches (L54) |
| `compute_flop_features(...)` | §8 Agent A | matches (L156-167) | matches (L74) | matches (L55) |
| `canonicalize_for_suit_iso(board, hand) -> tuple[str, int]` | (D1 addition; not in spec §5/§8 explicitly) | matches (L170-192) | matches in deps (L76) | matches (L57-58) |
| `equity_distribution(board, hole_cards, street, H=50, mode="mc", mc_iterations=200_000, rng=None) -> np.ndarray` | §8 Agent A | matches (L81-118) | matches in deps (L67-68) | matches (L48-49) |
| `emd_1d(p, q) -> float` | §8 Agent A | matches (L204-216) | matches in deps (L79) | matches (L60) |
| `batch_emd(points, centroids) -> np.ndarray` | §8 Agent A | matches (L219-229) | matches in deps (L80) | matches (L61) |
| `kmeans_emd(features, K, seed=42, max_iter=200, change_tolerance=0.001) -> KMeansResult` | §8 Agent A | matches (L239-261) | matches in deps (L88-89) | matches (L69-70) |
| `KMeansResult.assignments` dtype | spec silent | "uint16 (or uint8 if K <= 256)" (L234) | "uint16" (L84) | not specified (L65) |
| `lookup_bucket(tables, board, hole_cards, street) -> int` | §5, §8 Agent B | n/a (Agent A doesn't expose) | matches (L162-181) | matches (L90) |
| `load_abstraction(path) -> AbstractionTables` | §5 | n/a | matches (L209-220) | matches (L92) |
| `save_abstraction(tables, path) -> None` | §5 | n/a | matches (L184-206) | matches (L91) |
| `build_abstraction(out_path, bucket_counts=(256,128,64), seed=42, H=50, max_iter=200, streets=(FLOP,TURN,RIVER), flop_mode="mc", mc_iterations=200_000, progress=True, size_guard_gb=1.0) -> AbstractionTables` | §8 Agent B | n/a | matches (L245-256) | matches (L94-97) |

**Minor drift (not blocking):** Agent A documents `KMeansResult.assignments` dtype as "uint16 (or uint8 if K <= 256)" while Agent B and Agent C just say "uint16". Both fall under "fits in u16," so Agent A's runtime choice never violates either downstream contract. No patch needed; flag for monitoring.

### Check 2. Default decisions consistent across prompts

**Status: PASS.**

- **D1 (suit-iso INCLUDED in PR 4):** locked in agent_a_prompt L54, agent_b_prompt L52, agent_c_prompt L130. All three explicitly call out the override of spec §7.6.
- **D2 (Monte Carlo 200K iter as default):** locked in agent_a_prompt L55, agent_b_prompt L53, agent_c_prompt L131. All three explicitly invoke MC across all three postflop streets.
- **Bucket counts (256/128/64):** agent_a_prompt L56, agent_b_prompt L54, agent_c_prompt L132. Consistent.
- **Bucket file format (.npz):** agent_b_prompt L55, agent_c_prompt L134. (Agent A doesn't deal with file format; correctly silent.) Consistent.
- **H = 50:** agent_a_prompt L57, agent_b_prompt L67 (in deps signature), agent_c_prompt L133. Consistent.
- **Schema version 1:** agent_b_prompt L56, agent_c_prompt L135. Consistent. (Agent A doesn't touch serialization; correctly silent.)
- **Preflop returns -1:** agent_b_prompt L482, agent_c_prompt L136 + L164. Consistent.
- **No new third-party deps:** all three prompts (agent_a_prompt L60, agent_b_prompt L59, agent_c_prompt L137). Consistent.

### Check 3. `HUNLConfig.abstraction` field type consistent (NEW-1 fix)

**Status: PASS for agent_b and agent_c prompts; STALE references remain in spec but not in prompts.**

- Agent B prompt L331: `abstraction: "AbstractionRef | None" = field(default=None, compare=False, hash=False)` ✓
- Agent B prompt L334: "the HUNLConfig field type is `AbstractionRef | None`, NOT `AbstractionTables | None`" ✓ explicit fix-language
- Agent C prompt L106: `abstraction: AbstractionRef | None = None  # NEW (corrected: AbstractionRef not AbstractionTables — see pr4_spec.md §3.5)` ✓
- Agent A prompt: doesn't touch HUNLConfig (correctly silent).

**STALE references in pr4_spec.md** (NEW-1 not fully propagated):
- pr4_spec.md L156: `HUNLConfig` gains an optional `abstraction: Optional[AbstractionRef] = None` field ✓ (correct per §6 amendment)
- pr4_spec.md L354: "Modifies `HUNLConfig` (adds `abstraction: AbstractionRef | None = None` field — NOT `AbstractionTables`, per §3.5 and §6 amendments)" ✓ now corrected
- pr4_spec.md L53 (§3.5): `abstraction: AbstractionRef | None = None` (NOT `AbstractionTables`) ✓ now corrected with parenthetical "corrected per consistency review v2 NEW-1"

Spec is now self-consistent on this point; the consistency v2 NEW-1 finding has been resolved in pr4_spec.md (the orchestrator already amended §3.5 line 53 and §8 line 354 — both lines now say `AbstractionRef | None`). The prompts also reflect the new type. **No patch needed for type consistency.**

### Check 4. File ownership non-overlapping

**Status: PASS.**

Cross-prompt ownership table:

| File | Agent A | Agent B | Agent C |
|---|---|---|---|
| `poker_solver/abstraction/equity_features.py` | OWNS | NOT TOUCH | NOT TOUCH |
| `poker_solver/abstraction/emd_clustering.py` | OWNS | NOT TOUCH | NOT TOUCH |
| `poker_solver/abstraction/__init__.py` | NOT TOUCH | OWNS | NOT TOUCH |
| `poker_solver/abstraction/buckets.py` | NOT TOUCH | OWNS | NOT TOUCH |
| `poker_solver/abstraction/precompute.py` | NOT TOUCH | OWNS | NOT TOUCH |
| `poker_solver/hunl.py` | NOT TOUCH (read-only) | EDIT (additive) | NOT TOUCH |
| `poker_solver/__init__.py` | NOT TOUCH | EDIT (re-exports) | NOT TOUCH |
| `poker_solver/cli.py` | NOT TOUCH | EDIT (subcommand) | NOT TOUCH |
| `pyproject.toml` | NOT TOUCH | EDIT (deps verify) | NOT TOUCH |
| `tests/test_abstraction_emd.py` | NOT TOUCH | NOT TOUCH | OWNS |
| `tests/test_abstraction_buckets.py` | NOT TOUCH | NOT TOUCH | OWNS |
| `tests/test_abstraction_integration.py` | NOT TOUCH | NOT TOUCH | OWNS |

Zero overlap. Each prompt's "Strict file ownership" section reciprocally lists the other two agents' files as off-limits.

### Check 5. Cross-agent imports clear

**Status: PASS-WITH-NOTE.**

- Agent C prompt L239: "Imports: `from poker_solver import ...` or `from poker_solver.abstraction import ...`. Do NOT import from internal modules like `poker_solver.abstraction.equity_features` or `poker_solver.abstraction.buckets` directly (the `__init__.py` re-exports everything needed)."
- Agent B prompt L281-323 declares the contents of `poker_solver/abstraction/__init__.py` explicitly, including re-exports of: `AbstractionTables`, `load_abstraction`, `save_abstraction`, `lookup_bucket`, `build_abstraction`, `canonicalize_for_suit_iso`, `equity_distribution`, `compute_river_features`, `compute_turn_features`, `compute_flop_features`, `KMeansResult`, `emd_1d`, `batch_emd`, `kmeans_emd`. This covers everything Agent C needs.

Contract surface confirmed: `poker_solver/abstraction/__init__.py` is the single import seam for tests. Agent B owns that file. The contract is explicit and bidirectionally consistent.

**Note (not blocking):** Agent B's deps-section (L88) lists `KMeansResult` import from `emd_clustering` but doesn't import it in the `precompute.py` snippet (L233-241) — but precompute may not need it directly; it consumes `kmeans_emd`'s return value indirectly. Not a contract issue.

### Check 6. License-aware sourcing language present in all 3 prompts

**Status: PASS.**

- Agent A prompt §"License-aware sourcing" L340-358: AGPL-vs-MIT language, postflop-solver + TexasSolver named as AGPL no-copy, slumbot2019 + noambrown_poker_solver named as MIT-portable, attribution-comment template provided. ✓
- Agent B prompt §"License-aware sourcing" L497-515: same structure, postflop-solver + TexasSolver named no-copy, slumbot2019 + noambrown named portable, attribution template provided. ✓
- Agent C prompt §"License-aware sourcing" L229-233: tests are first-party; same AGPL/MIT distinction; attribution template provided. ✓
- All three prompts include the same "no extrapolation from training data" clause (agent_a_prompt L352, agent_b_prompt L509, agent_c_prompt implicit via "tests written from scratch").

### Check 7. Bucket lookup helper name (`lookup_bucket` vs `lookup_bucket_via_ref`)

**Status: FAIL — load-bearing inconsistency between agent_b_prompt and the public API contract.**

The recent patch to agent_b_prompt introduced `lookup_bucket_via_ref` inside the `infoset_key` implementation snippet (agent_b_prompt L348-354):

```python
from poker_solver.abstraction.buckets import lookup_bucket_via_ref
bucket_id = lookup_bucket_via_ref(
    cfg.abstraction,  # AbstractionRef; loader caches the resolved tables
    state.board,
    state.hole_cards[player],
    state.street,
)
```

However:
1. `lookup_bucket_via_ref` is **never declared** in Agent B's "Public API you produce" section (L96-221). Only `lookup_bucket(tables, ...)` (L162) is declared. The new function name appears inline in the `infoset_key` snippet without a corresponding function-signature declaration.
2. `lookup_bucket_via_ref` is **not in** Agent B's `__init__.py` re-export list (L286-323). Only `lookup_bucket` is exported.
3. `lookup_bucket_via_ref` is **not mentioned** in Agent C's test prompt (agent_c_prompt L90, L164-185). Agent C tests use `lookup_bucket(tables, ...)` everywhere.
4. The audit prompt (audit_prompt.md L74, L110, L111) references only `lookup_bucket` — no awareness of the new helper.
5. `pr4_spec.md` L53 uses `tables.lookup_bucket(...)` (method-style), L147 / L349 use `lookup_bucket(tables, ...)` (function-style). The spec is itself ambivalent but does NOT mention `lookup_bucket_via_ref`.

**Consequences if not patched:** Agent B will produce code with TWO lookup entry points — `lookup_bucket(tables, ...)` (declared, tested by Agent C) and `lookup_bucket_via_ref(ref, ...)` (used by `infoset_key`, untested by Agent C, undocumented in any public API surface). Agent C's `test_tiny_subgame_with_abstraction_produces_bucketed_infosets` will exercise the `lookup_bucket_via_ref` path indirectly (through `infoset_key`), but no direct unit test covers `lookup_bucket_via_ref`. The audit prompt will also miss it as a focus area.

**Recommended patch (Patch #1, load-bearing):** Add a public-API entry for `lookup_bucket_via_ref` in Agent B's "Public API you produce" section, e.g., immediately after the `lookup_bucket` declaration (around L181):

```python
def lookup_bucket_via_ref(
    ref: "AbstractionRef",
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
) -> int:
    """Resolve `ref` to a cached AbstractionTables (loading once via
    load_abstraction(ref.source_path); caching keyed on source_path), then
    delegate to lookup_bucket(tables, board, hole_cards, street).

    Used by HUNLPoker.infoset_key so the engine never holds a direct
    AbstractionTables reference on HUNLConfig (PyO3 forward-compat).
    """
    ...
```

Plus add `lookup_bucket_via_ref` to the `__init__.py` re-exports (L286-323) and to `__all__` (L307-322).

Without this patch, Agent B's `infoset_key` implementation will compile but the function won't be a documented part of the public API surface — Agent C cannot directly test it, and the audit agent will flag it as an undocumented backdoor entry point.

### Check 8. Spec-side cross-references valid

**Status: PASS.**

Verified all spec section cross-references in each prompt resolve to existing sections in `pr4_spec.md`:

Agent A prompt:
- "§3 (conceptual architecture)" ✓ (spec L22)
- "§4 Stages 1–3 (your stages)" ✓ (spec L55)
- "§7.1 + §7.7 + §7.8 + §7.10 + §7.11 (your decisions)" ✓ (all exist; spec L178, L259, L281, L300, L309)
- "§8 Agent A deliverables" ✓ (spec L321 + L325 Agent A subsection)
- "§9 risks" ✓ (spec L407)
- "§7.6" ✓ (spec L243) referenced as the section being overridden by D1
- "§7.7" ✓ (spec L259) referenced for MC vs exact

Agent B prompt:
- "§3 (conceptual architecture)" ✓
- "§4 Stages 4–5 (your stages)" ✓
- "§5 (files to create)" ✓ (spec L142)
- "§6 (files to modify)" ✓ (spec L153)
- "§7.5 + §7.6 + §7.12 (your decisions)" ✓ (all exist)
- "§8 Agent B deliverables" ✓
- "§9 risks" ✓
- "§3.5 line 53" referenced in correction text ✓ (after the orchestrator's NEW-1 patch landed)

Agent C prompt:
- "§3 (architecture)" ✓
- "§4 (Stages 1-5)" ✓
- "§5 (file structure)" ✓
- "§6 (modifications to existing files)" ✓
- "§7 (design decisions)" ✓
- "§8 Agent C deliverables (your test plan)" ✓ (spec L321 + L357 Agent C subsection)
- "§11 (success criteria)" ✓ (spec L436)
- "pr4_spec.md §3.5" ✓ (cross-referenced for the AbstractionRef type)

All section references resolve. No dangling §X.

---

## Additional findings (not in the 8-check list but flagged for transparency)

### F1. Spec § ↔ prompt drift on suit-iso default

**Severity: LOW (locked by D1 but inconsistent prose left in spec).**

`pr4_spec.md` §4 Stage 4 (L109-112) and §8 Agent B deliverable line 351 still describe the OLD pre-D1 contract ("Suit-iso NOT applied per Decision 7.6"). The prompts correctly override via D1 ("SUIT-ISO INCLUDED in PR 4"), but the spec itself wasn't patched for D1 — only the agent_*_prompt.md files have the D1 override language.

The risk: agents read the spec first (instructed by the prompts' "Read first" sections); they'll encounter the OLD suit-iso = NOT applied language at spec L109-112 and L351, then read the prompt's "Default decisions LOCKED" section that overrides this. A careful agent reads both and applies the override. A careless agent who weights "first authoritative read" higher will produce the wrong code.

**Recommended patch (Patch #2, documentation-quality):** Add a one-line note at the top of `pr4_spec.md` §4 Stage 4 (around L107) and inside §8 line 351:

> Note: Per the autonomous_log.md "D1" decision (2026-05-21), suit-iso IS applied in PR 4 — `canonicalize_for_suit_iso(...)` is the canonical key. This section's pre-D1 prose describing "Suit-iso NOT applied" is superseded.

Not strictly load-bearing because the prompts already override; but a 2-line patch would prevent ambiguity flags from a careful agent.

### F2. Spec-side `tables.lookup_bucket` method-style vs prompts' `lookup_bucket(tables, ...)` function-style

**Severity: LOW.**

`pr4_spec.md` L53 uses `tables.lookup_bucket(board, hole_cards, street)` (method on `AbstractionTables`). Every other reference (spec L147, L349; agent_b_prompt L162, L181; agent_c_prompt L90) uses the function-style `lookup_bucket(tables, ...)`. The spec L53 is a stray inconsistency.

This is unlikely to cause confusion because all the prompts use function-style and Agent C will write tests against function-style. But a careful agent reading spec §3.5 might wonder whether `AbstractionTables` should expose a method as well.

**Recommended patch (Patch #3, cosmetic):** Edit `pr4_spec.md` L53 to use the function-style: `lookup_bucket(tables, board, hole_cards, street)` to match all other usages.

### F3. All 3 prompts cite `spec_consistency_review.md` (v1) not `spec_consistency_review_v2.md`

**Severity: LOW.**

agent_a_prompt L41, agent_b_prompt L43, agent_c_prompt L38 all cite the v1 review file. The v2 review file (`spec_consistency_review_v2.md`) exists and contains the NEW-1 finding that drove the recent patch to agent_b_prompt. Agents reading per the "Read first" instructions will skim v1 only.

Since the v1 → v2 patches (NEW-1) have already been applied to the prompts and spec, this is informational drift only. Not load-bearing because the patches are in the prompts directly. Optional cleanup: change "spec_consistency_review.md" → "spec_consistency_review_v2.md" in each prompt's Read-First section. Skip if launch is urgent.

---

## Recommended patches (if any)

Apply at least **Patch #1** before launch. Patches #2 and #3 are documentation polish.

### Patch #1 (LOAD-BEARING) — declare `lookup_bucket_via_ref` in agent_b_prompt's public API

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/agent_b_prompt.md`
**Where:** After line 181 (end of `lookup_bucket` declaration in §"Public API you produce → `buckets.py`")

Insert a new public-API declaration:

```python
def lookup_bucket_via_ref(
    ref: "AbstractionRef",
    board: Sequence[Card],
    hole_cards: tuple[Card, Card],
    street: Street,
) -> int:
    """Resolve `ref` to a cached AbstractionTables (load once via
    load_abstraction(ref.source_path); cache keyed on source_path), then
    delegate to lookup_bucket(tables, board, hole_cards, street).

    The cache is process-local module state; subsequent calls with the same
    ref.source_path return the cached tables. Used by HUNLPoker.infoset_key
    so HUNLConfig holds only the AbstractionRef (path + version), not the
    materialized in-memory tables (PyO3 boundary forward-compat per spec §6
    / consistency review B2).

    Raises:
        FileNotFoundError: if ref.source_path doesn't exist on disk.
        ValueError: if loaded artifact's schema_version doesn't match ref.version.
    """
    ...
```

Also add `lookup_bucket_via_ref` to the `__init__.py` re-export list in agent_b_prompt L286-323 and to `__all__` at L307-322.

Also update Agent C prompt (`agent_c_prompt.md`) §"Agent B produces" L89-92 to declare the new function so Agent C is aware of it (Agent C still tests `lookup_bucket(tables, ...)` directly; the indirect test of `lookup_bucket_via_ref` happens through `test_tiny_subgame_with_abstraction_produces_bucketed_infosets`). Optionally, ask Agent C to add a direct unit test for `lookup_bucket_via_ref` (returns same bucket as `lookup_bucket` for the same logical inputs, after caching).

Update audit_prompt.md L74, L110, L111 to mention both `lookup_bucket` and `lookup_bucket_via_ref` so the audit covers both entry points.

### Patch #2 (documentation-quality) — note D1 override in spec §4 Stage 4

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`
**Where:** Insert one note line at L108 (top of §4 Stage 4) and L352 (inside §8 Agent B's `_canonical_board_id` deliverable).

Add to both locations:

> **Override (2026-05-21):** Per the autonomous_log.md D1 decision, suit-iso IS applied in PR 4. The `canonicalize_for_suit_iso(...)` helper (declared in Agent A's `equity_features.py`) is the canonical lookup-key generator. This section's pre-D1 prose describing "Suit-iso NOT applied" is superseded.

### Patch #3 (cosmetic) — function-style consistency in spec §3.5

**File:** `/Users/ashen/Desktop/poker_solver/docs/pr4_prep/pr4_spec.md`
**Where:** L53.

Edit:
- OLD: "calls `tables.lookup_bucket(board, hole_cards, street)`"
- NEW: "calls `lookup_bucket(tables, board, hole_cards, street)`"

---

## Agent-launch order recommendation

**Recommended order: launch all 3 agents in PARALLEL.** The fan-out pattern is designed for parallel execution.

Justification:

- **Agent A (equity_features + emd_clustering)** has zero file dependencies on Agent B or Agent C. Its outputs are imported by Agent B's `precompute.py` but only at *integration time* (after Agent B has stub-imports). Agent A can also produce its own smoke tests against its public API.
- **Agent B (buckets + precompute + integration touches)** depends on Agent A's signatures (declared in the "Agent A's exports you depend on" section L62-90). Since the signatures are locked by the spec + prompt, Agent B can write its code against the *signature contract* without seeing Agent A's implementation. Integration testing happens after both land.
- **Agent C (tests)** is intentionally independent of A and B implementations (per agent_c_prompt L29 "do NOT read poker_solver/abstraction/equity_features.py, emd_clustering.py, buckets.py, or precompute.py even after Agents A/B land"). Agent C writes from spec alone.

The parallel fan-out is the **default for PR 4** per the user's locked "Parallel agents default" memory rule and per spec §8's "Launch concurrently, integrate at the end" instruction. Sequential launch (A → B → C) would lose ~50-70% of wall-clock parallelism.

**Order of integration validation (post-implementation):**

1. Agent A lands → run agent_a verification commands (Agent A's smoke tests).
2. Agent B lands → run agent_b verification commands (CLI subcommand smoke test, infoset_key parity).
3. Agent C lands → run agent_c verification commands (pytest collection + execution).
4. Audit agent runs against the integrated branch.

This integration-validation order is sequential (because each step depends on the prior), but the implementation phase is parallel.

**Caveat:** if Patch #1 is NOT applied, Agent B will need an integration-time decision about whether to expose `lookup_bucket_via_ref` publicly or as an internal helper. Either choice is workable, but the orchestrator should pre-decide and not delegate to Agent B mid-build (which would introduce a contract drift Agent C cannot anticipate).

---

## Summary

- **8/8 checks executed.** Check 7 (FAIL) is the only load-bearing finding; Checks 1-6 + 8 PASS.
- **3 patches recommended.** Patch #1 is load-bearing; Patches #2-3 are documentation polish.
- **Parallel A+B+C launch is the recommended cadence**, with the audit agent firing after integration.
- **Spec is internally consistent on the NEW-1 type fix** — `HUNLConfig.abstraction: AbstractionRef | None` is now consistently declared in spec §3.5 + §6 + §8, and in both agent_b_prompt and agent_c_prompt.
- **Hidden risk:** the `lookup_bucket_via_ref` patch introduced a function that isn't yet in the contract surface. Apply Patch #1 (a ~10-line addition to agent_b_prompt + ~3-line addition to agent_c_prompt + ~3-line addition to audit_prompt) before launch to avoid a mid-build contract ambiguity flag from Agent B.
