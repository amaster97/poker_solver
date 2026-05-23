# PR 6 prep — final consistency check (post-v3 + post-shape-patches)

**Date:** 2026-05-22
**Reviewer:** orchestrator consistency-check agent (read-only; post-launch-readiness-v2/v3 + post-agent_a/c shape patches + on_progress cascade)
**Inputs reviewed:**
- `docs/pr6_prep/pr6_spec.md` (787 lines)
- `docs/pr6_prep/agent_a_prompt.md` (562 lines)
- `docs/pr6_prep/agent_b_prompt.md` (617 lines)
- `docs/pr6_prep/agent_c_prompt.md` (535 lines)
- `docs/pr6_prep/audit_prompt.md` (191 lines)
- `docs/pr6_prep/launch_readiness_v2.md`, `v3.md`, `MUST_PATCH_BEFORE_LAUNCH.md` (for context)

**Note:** `docs/pr6_prep/launch_kickoff.md` does NOT exist — kickoff agent has not landed, so only 5 docs were checked. Verdict scope is limited to those 5.

## Verdict: **LAUNCH-READY**

All 8 requested consistency checks pass. PR 6 can fire post-PR-5 with no further docs touch.

## Per-check results

### 1. AbstractionTables / AbstractionRef shape consistent across all 5 docs (PASS)

The committed PR 4 on-disk shape is consistently described in all 5 docs as:
- `flop/turn/river_assignments: Vec<u8>` (per-street flat bucket-id arrays)
- `flop/turn/river_board_index: HashMap<String, u32>` (string-keyed)
- `flop/turn/river_hand_index: HashMap<String, HashMap<String, u32>>` (nested string-keyed)
- `metadata: AbstractionMetadata` (typed struct from JSON-encoded `metadata` blob — holds `schema_version, version, bucket_counts, feature_bins, seed` + `#[serde(flatten)] extra`)
- `source_path: PathBuf` (set at load time, NOT on disk)

Evidence: `pr6_spec.md:299-319`, `agent_a_prompt.md:414-446` (cross-agent contract), `agent_b_prompt.md:122-194` (Rust shape declaration), `agent_c_prompt.md:444-459` (Rust contract block), `audit_prompt.md:57-65` (focus area #3 + #9).

The previous draft's `HandLookup` packed struct + top-level scalar fields (`bucket_counts`, `schema_version`, `feature_bins`, `seed` as separate top-level keys) are fully purged. No occurrences of `HandLookup` in any of the 5 docs. `AbstractionRef = (source_path: str, version: str)` is cited on `HUNLConfig.abstraction` in all docs and is **never** re-declared in PR 6 scope (consumes only).

One minor consistency observation (NOT blocking): `pr6_spec.md:117` describes Rust `HUNLConfig.abstraction: Option<Arc<AbstractionTables>>` (in-process form, post-load), whereas `agent_a_prompt.md:159-160` shows `abstraction_path: Option<String>` + `abstraction_version: Option<String>` (JSON-marshalled form, pre-load). Both shapes are internally consistent — JSON arrives over PyO3 with path + version, Rust loads the table independently and may then hold it via `Arc`. Launch-readiness v3 §"Residual findings" #2 already noted and excused this.

### 2. resolve_abstraction_ref referenced consistently (PASS)

Canonical Python entry point `resolve_abstraction_ref(ref) -> AbstractionTables` (LRU-cached + version-checked) is cited consistently:
- `pr6_spec.md:447, 455, 492, 502` (§6.1 example code + §6.3 canonical declaration)
- `agent_b_prompt.md:48, 316, 322, 327, 372` (read-first list + `_solve_rust` snippet + version-check note)
- `audit_prompt.md:89-93` (focus area #9 — flags bypass as **must-fix**)
- `agent_a_prompt.md:444` (cross-agent contract docstring reference)
- `agent_c_prompt.md:440` (Rust contract block docstring)

All cite the same property: NEVER reach into `cfg.abstraction.source_path` directly; always go through the resolver. Audit prompt enforces this as must-fix if bypassed.

### 3. PR 9 §6 canonical dispatch cited in all 5 docs (PASS — with caveat)

- `pr6_spec.md:5, 479-490` (§6.1 dispatch-ordering invariant block; 5-step head-to-tail enumeration)
- `agent_b_prompt.md:42, 349-360` (read-first + canonical ordering block with same 5-step enumeration)
- `audit_prompt.md:15, 95-102` (focus area #10 — explicit must-fix trigger for elif inserted before push/fold)

**Caveat:** `agent_a_prompt.md` and `agent_c_prompt.md` do NOT mention PR 9 §6 dispatch ordering directly. **This is correct by scope** — Agent A owns Rust state/tree/eval (no Python `_solve_rust` touch); Agent C owns tests (consumes `solve(backend='rust')` not the dispatch wiring). The invariant is Agent B's responsibility and the audit's gate. No fix needed.

### 4. 5e-3/1e-3 diff tolerance consistent (PASS)

All 5 docs use the same tolerance cluster: **1e-3** (river-only) / **5e-3** (flop fixture) with **1e-6** absolute floor:
- `pr6_spec.md:521, 528, 549, 551, 705` (§7.1 / §7.3 / §11 #7)
- `agent_a_prompt.md:74` (D7 lock summary)
- `agent_b_prompt.md:76` (D7 lock summary)
- `agent_c_prompt.md:10, 36, 61, 75, 92, 107, 116, 121, 322, 489` (test code + rationale)
- `audit_prompt.md:71-75, 95` (focus area #5 — must-fix trigger if silently loosened)

`agent_c_prompt.md:107` codes the canonical assertion: `tol = max(1e-6, 1e-3 * max(abs(p), abs(r)))`. No stale `1e-4` outlier; no doc silently loosens.

### 5. Slumbot (MIT) cited as inspiration; postflop-solver (AGPL) excluded (PASS)

Slumbot2019 MIT cited as the inspiration source for hand-eval and abstraction-layout patterns:
- `pr6_spec.md:42, 50, 230, 243, 720, 750` (§3 source table; §4.3 eval reference)
- `agent_a_prompt.md:55, 307, 479, 519` (read-first; module docstring template for `hunl_eval.rs`)
- `agent_b_prompt.md:60, 113, 504` (read-first; module docstring template for `abstraction.rs`)
- `audit_prompt.md:47, 54` (attribution focus areas)

`postflop-solver` is explicitly marked AGPL "NEVER copy" in all 5 docs (`pr6_spec.md:43`, `agent_a_prompt.md:58, 90, 247, 382, 481, 494`, `agent_b_prompt.md:63, 115, 212, 430, 505, 519`, `agent_c_prompt.md:55, 387`, `audit_prompt.md:43, 49`). No doc cites postflop-solver as the inspiration source for any algorithm.

Note: "EMD inspiration source" is not directly relevant in PR 6 scope — EMD clustering is PR 4 (already landed). The user's framing applies to the equivalent "MIT inspiration source for hand-eval + abstraction-layout patterns," which is uniformly slumbot2019 across all 5 docs.

### 6. HUNL Rust file names consistent (PASS)

All 5 docs reference the same Rust file names:
- `crates/cfr_core/src/hunl.rs` — game state (Agent A)
- `crates/cfr_core/src/hunl_tree.rs` — flat tree (Agent A)
- `crates/cfr_core/src/hunl_eval.rs` — hand evaluator (Agent A)
- `crates/cfr_core/src/abstraction.rs` — bucket loader (Agent B)
- `crates/cfr_core/src/hunl_solver.rs` — solve entry (Agent B)
- `crates/cfr_core/src/lib.rs` — PyO3 surface (Agent B, additive)

Spec §4.5 (`pr6_spec.md:349-385`) and Agent B (`agent_b_prompt.md:201-250`) both reference `hunl_solver.rs` as the Rust file name (counterpart to Python's `poker_solver/hunl_solver.py`). Agent A correctly notes (`agent_a_prompt.md:29`) that Agent B owns this file. Agent C's contract block (`agent_c_prompt.md:466`) uses `cfr_core::hunl_solver` consistently. Audit prompt lists the same file path (`audit_prompt.md:28`).

### 7. License attribution header requirements uniform (PASS)

All 5 docs require the same module-level attribution docstring template per spec §3:
- `pr6_spec.md:53-65` (canonical template)
- `agent_a_prompt.md:485-496` (verbatim template for `hunl_*.rs` files)
- `agent_b_prompt.md:508-521` (verbatim template for `abstraction.rs` / `hunl_solver.rs`)
- `audit_prompt.md:43-55` (focus area #1 + #2 — must-fix if missing; specific per-file expectations)

Agent C is excluded from this requirement by scope (tests don't ship MIT/Apache attribution). Each per-file template names: (a) Python source as semantic truth, (b) MIT/Apache patterns adapted (noambrown river_game/cards/trainer, slumbot hand_value_tree/card_abstraction, ndarray-npy), (c) explicit "NEVER copy from postflop-solver / TexasSolver (AGPL)" disclaimer.

### 8. Cross-references between docs use correct anchors (PASS — post-shape-patch verification)

After patches landed in launch-readiness v3, anchors are stable:
- `pr6_spec.md` §4.1, §4.2, §4.3, §4.4, §4.5, §6.1, §6.3, §7.1, §7.3, §8.1, §8.2, §8.3, §9, §10, §11 are all referenced by sibling docs and resolve correctly (sections exist in the spec at expected positions).
- `audit_prompt.md` cites spec §3, §4.4, §4.5, §5, §6, §6.3, §7, §7.3, §9, §9 #1-#15, §10 — all anchors resolve.
- `agent_a/b/c_prompt.md` cite spec §3, §4.1, §4.1.5, §4.2, §4.3, §4.4, §4.5, §5, §6.1, §6.3, §7, §7.1, §7.3, §8.1, §8.2, §8.3, §9, §10, §11 — all resolve.
- `audit_prompt.md` does refer to "§9 (critical correctness items — 15 items)" but the actual spec §9 (`pr6_spec.md:629-657`) enumerates **15** items (1-15). PASS.
- Line-number-based references in launch_readiness_v3 (`pr6_spec.md:251-296` etc.) still resolve correctly (lines did not shift further after the v3-confirming patches).

## Residual findings

None blocking. Two harmless observations carried over from v3:
1. `_serialize_hunl_config` JSON does not explicitly mention `source_path` flattening (`agent_b_prompt.md:289-305`); the spec §6.1 example code (`pr6_spec.md:454-456`) shows the flattening site separately. Both sites are mutually consistent.
2. The `Option<Arc<AbstractionTables>>` (spec §4.1 in-process form) vs `abstraction_path/abstraction_version` (agent_a JSON-marshalled form) duality is internally consistent — see check 1 above.

## Recommendation

**Launch PR 6 3-agent fan-out (A + B + C) post-PR-5 with no further docs touch.** Audit agent fires after all three land. The 5-doc bundle is internally consistent and faithful to the committed PR 4 on-disk layout, the PR 3.5 push/fold short-circuit, PR 8's pre-mirrored `use_pcs` field, and the 1e-3 / 5e-3 tolerance cluster.
