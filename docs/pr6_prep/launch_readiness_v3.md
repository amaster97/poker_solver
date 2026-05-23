# PR 6 launch readiness — v3

**Date:** 2026-05-22
**Reviewer:** orchestrator audit agent (post-launch-readiness-v2 round-1 + post-agent_a/agent_c shape patches)
**Inputs reviewed:**
- `docs/pr6_prep/pr6_spec.md` (787 lines; 2026-05-21 + 2026-05-22 amendments at top)
- `docs/pr6_prep/agent_a_prompt.md` (562 lines, post-shape patch)
- `docs/pr6_prep/agent_b_prompt.md` (617 lines, post-shape patch)
- `docs/pr6_prep/agent_c_prompt.md` (535 lines, post-shape patch)
- `docs/pr6_prep/audit_prompt.md` (191 lines, post-dispatch-ordering add)
- `docs/pr6_prep/launch_readiness_v2.md` (the previous failing-check list)
- `poker_solver/abstraction/buckets.py` (committed PR 4 — authoritative on-disk shape)

## Verdict: **READY**

All 7 checks from launch-readiness v2 now pass. The three follow-up confirmations (Agent A "Cross-agent contracts" section, Agent C Rust contract block, audit_prompt focus area #10) are also in place. PR 6 3-agent fan-out can fire.

## Re-run of launch-readiness v2 checks

### Check 1: AbstractionTables shape matches committed PR 4 (PASS)

PR 4 (`poker_solver/abstraction/buckets.py:55-81`) ships `AbstractionTables` with `flop/turn/river_board_index: dict[str, int]`, `flop/turn/river_hand_index: dict[str, dict[str, int]]`, `metadata: dict[str, object]`, `source_path: Path | None`. The `.npz` writer (`save_abstraction`, lines 262-315) encodes each index dict + the metadata as **JSON-bytes one-element uint8 arrays**.

- `pr6_spec.md:251-296` now matches: §4.4 explicitly documents the JSON-encoded `*_board_index` / `*_hand_index` / `metadata` layout (lines 253-267), with Rust shape `HashMap<String, u32>` board indices, `HashMap<String, HashMap<String, u32>>` hand indices, `metadata: AbstractionMetadata` (lines 298-319). No `HandLookup`, no top-level scalar fields.
- `agent_a_prompt.md:402-462` cross-agent contract uses the same shape.
- `agent_b_prompt.md:88-194` reflects the same shape, including the `decode_json_bytes` helper.
- `agent_c_prompt.md:427-462` Rust contract block is correctly updated.

### Check 2: `resolve_abstraction_ref()` used (not direct `.source_path` reach) (PASS)

- `pr6_spec.md:447-461` (§6.1 `_solve_rust` snippet) and `:492` explicitly call `resolve_abstraction_ref(game.config.abstraction)` and forbid direct `.source_path` access.
- `agent_b_prompt.md:316-328` shows the same call pattern with a comment block explaining the LRU cache + version-check rationale.
- `audit_prompt.md:89-93` focus area #9 calls out bypassing the resolver as a must-fix.

### Check 3: PR 9 §6 canonical dispatch invariant cited (PASS)

- `pr6_spec.md:479-490` (§6.1) declares the dispatch ordering (push/fold → HUNL Rust → HUNL Python → HUNL preflop → Kuhn/Leduc) and cites PR 9 §6 as canonical.
- `agent_b_prompt.md:349-360` mirrors the ordering with the same head-to-tail enumeration.
- `audit_prompt.md:95-102` adds focus area #10 with the exact 5-step ordering and the must-fix trigger.

### Check 4: Slumbot MIT cited for eval; postflop-solver (AGPL) never copied (PASS)

- `pr6_spec.md:38-46` (§3 source table) cites slumbot2019 MIT for hand-eval + abstraction layout; postflop-solver/TexasSolver as "read-only inspiration, never copy."
- `agent_a_prompt.md:55, 304-309` cites slumbot2019 `hand_value_tree.cpp` (MIT) in `hunl_eval.rs` docstring template.
- `agent_b_prompt.md:60, 112-113` cites slumbot2019 `card_abstraction*.cpp` (MIT) in `abstraction.rs` docstring template.
- All four prompts call postflop-solver / TexasSolver AGPL with "NEVER copy" framing.

### Check 5: 5e-3 / 1e-3 tolerance consistent (PASS)

- `pr6_spec.md:521, 528, 549` lock 1e-3 (river) / 5e-3 (flop) with 1e-6 absolute floor.
- `agent_a_prompt.md:74`, `agent_b_prompt.md:76`, `agent_c_prompt.md:61` all reference the 1e-3 / 5e-3 cluster.
- `agent_c_prompt.md:106-110` codes the assertion with `tol = max(1e-6, 1e-3 * max(abs(p), abs(r)))`.
- `audit_prompt.md:71-75` flags any silent loosening as must-fix.

### Check 6: AbstractionRef field type throughout (PASS)

- `poker_solver/hunl.py:118` (per launch-readiness v2 check 2) ships `HUNLConfig.abstraction: AbstractionRef | None`.
- All four PR 6 prompts (grep verified in launch-readiness v2) avoid `AbstractionTables | None` as a `HUNLConfig` field type. Spec §6.3 (`pr6_spec.md:498-502`) reaffirms PR 4 already declares the field; PR 6 consumes, does not re-declare.

### Check 7: License attribution headers required in Rust source modules (PASS)

- `pr6_spec.md:53-65` (§3) supplies the verbatim module-docstring template.
- `agent_a_prompt.md:485-496` and `agent_b_prompt.md:508-521` reiterate the template per-file with mandatory MIT/Apache attribution + AGPL "NEVER copy" disclaimer.
- `audit_prompt.md:43-51` focus area #1 calls out missing attribution as must-fix; `:52-55` focus area #2 enumerates per-file expectations (`hunl.rs` cites noambrown river_game.h/cpp; `hunl_eval.rs` cites noambrown cards + slumbot hand_value_tree; `abstraction.rs` cites ndarray-npy MIT/Apache).

## Prior-finding follow-up confirmations

### Agent A "Cross-agent contracts" section (PRESENT)

`agent_a_prompt.md:396-466` provides the canonical opaque `crate::abstraction` surface Agent A imports: `AbstractionMetadata` + `AbstractionTables` (with `HashMap<String, u32>` / `HashMap<String, HashMap<String, u32>>` shape), plus `load_abstraction`, `lookup_bucket` signatures. Locked by spec §4.4 reference.

### Agent C Rust contract block (PRESENT)

`agent_c_prompt.md:420-462` provides the matching Rust contract Agent C tests against, including a docstring noting "post launch-readiness-v2 amendment, 2026-05-22" and explicit warnings that no `HandLookup` / no `Vec<u32>` top-level board indices exist. The 10K-roundtrip canary's expectations are anchored to this shape.

### audit_prompt focus area #10 (PRESENT)

`audit_prompt.md:95-102` is the new focus area #10 (PR 9 §6 canonical dispatch ordering). It enumerates the canonical 5-step order and flags an HUNL Rust elif inserted before the push/fold short-circuit as must-fix.

## Per-check summary

| # | Check | v2 status | v3 status |
|---|---|---|---|
| 1 | AbstractionTables shape matches committed PR 4 | PARTIAL | PASS |
| 2 | `resolve_abstraction_ref()` used (no `.source_path` reach) | FAIL | PASS |
| 3 | PR 9 §6 canonical dispatch invariant cited | FAIL | PASS |
| 4 | Slumbot MIT for eval; postflop-solver never | PASS | PASS |
| 5 | 5e-3 / 1e-3 tolerance consistent | PASS | PASS |
| 6 | `AbstractionRef` field type (not `AbstractionTables`) | PASS | PASS |
| 7 | License attribution headers required | PASS | PASS |
| + | Agent A "Cross-agent contracts" present | n/a | PASS |
| + | Agent C Rust contract block present | n/a | PASS |
| + | audit_prompt focus area #10 (dispatch ordering) | n/a | PASS |

**Net:** 7/7 PASS + 3/3 prior-finding follow-ups confirmed.

## Residual findings

None blocking. Two minor observations (not action items):

- The Python-side `_serialize_hunl_config` JSON shape (`agent_b_prompt.md:289-305`) does not explicitly include the in-process-loaded `AbstractionTables.source_path` — Agent B is expected to flatten `cfg.abstraction.source_path` into `abstraction_path` separately (already shown in `pr6_spec.md:454-456`). The two sites are consistent; just worth a one-line confirmation in Agent B's verification step.
- `pr6_spec.md:117` Rust `HUNLConfig.abstraction` is typed `Option<Arc<AbstractionTables>>`, while `agent_a_prompt.md:159-160` shows the Rust mirror with `abstraction_path: Option<String>` + `abstraction_version: Option<String>`. Both are internally consistent (spec §4.1's Arc form is the in-process shape after load; Agent A's form is the JSON-marshalled config the Rust side receives). No drift, but agents should know the `_solve_rust` path passes the path string and Rust does the `load_abstraction` independently per §6.1 + §6.3.

## Recommendation

**Fire PR 6 A/B/C agents in parallel.** Spec + prompts are internally consistent and faithful to the committed PR 4 on-disk shape. Audit prompt covers all v2 must-fix triggers plus the new dispatch-ordering invariant.
