# PR 6: MUST PATCH BEFORE LAUNCH

**Priority: high. Do NOT launch PR 6 implementation agents until these patches land.**

User explicitly flagged this should be on the immediate to-do list after pytest-timeout wiring.

## Findings from `docs/pr6_prep/launch_readiness_v2.md`

1. **CRITICAL — AbstractionTables shape drift.** PR 6 spec §4.4 + agent_b_prompt describe integer-keyed `Vec<u32>` + nested structs; PR 4 actually shipped string-keyed dict-of-dict + JSON-encoded metadata blob in `.npz`. Loader would fail.

2. **HIGH — `resolve_abstraction_ref()` not used.** agent_b_prompt's `_solve_rust` reaches into `.source_path` directly, bypassing PR 4's LRU-cached resolver + version check.

3. **MEDIUM — PR 9 §6 canonical dispatch invariant not cited.** No prompt mentions the HUNL Rust branch must compose AFTER push/fold short-circuit.

## Patch agent

In flight as task #102 (agent `a91afbc5439a7e429`). Will update PR 6 spec §4.4 + agent_b_prompt.md + audit_prompt.md.

## After patches land

- Re-run `docs/pr6_prep/launch_readiness_v2.md`-style verification with the patched prompts.
- Only THEN launch PR 6 3-agent fan-out.
