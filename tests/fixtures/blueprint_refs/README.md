# Blueprint Reference Fixtures

Machine-readable fixtures for Premium-A Phase 7's diff-test
(`tests/test_blueprint_diff_vs_external.py`, not yet shipped — see
`docs/premium_a_blueprint_subplan.md` §2 Phase 7).

See **`docs/blueprint_reference_inventory.md`** for the full inventory and
the gap analysis covering what *is not* here.

## Files

| File | Source kind | Stack depth(s) | Shippable? |
|---|---|---|---|
| `hu_100bb_user_supplied_chart_2026-05-28.json` | `user_supplied` | 100 BB | Yes (conditional — see fixture `license_notes`) |
| `hu_pushfold_self_2_to_15bb_v1.json` | `solver_dump` (self) | 2–15 BB | Yes (MIT, our own data) |

## Adding a new fixture

Per memory rule `feedback_references`, the user controls additions. The
fixture-creator workflow:

1. The user supplies a reference (manual transcription, exported chart,
   etc.) by placing it in `references/manual_downloads/` or by handing it
   to the orchestrator.
2. The orchestrator transcribes / converts it to the fixture schema below
   and writes it here.
3. The orchestrator updates `docs/blueprint_reference_inventory.md` §4.1
   with the new fixture and any new gaps it fills.

## Schema

```json
{
  "fixture_version": "1.0",
  "source": "<citation string>",
  "source_kind": "user_supplied | published_chart | solver_dump | heuristic",
  "shippable_in_repo": true,
  "license_notes": "<one-line summary>",
  "date_scraped": "YYYY-MM-DD",
  "date_added_to_repo": "YYYY-MM-DD",
  "config": {
    "stack_depth_bb": <int>,
    "ante_bb": <float>,
    "small_blind_bb": <float>,
    "big_blind_bb": <float>,
    "open_size_bb": <float | null>,
    "three_bet_size_bb": <float | null>,
    "four_bet_size_bb": <float | null>,
    "action_menu_notes": "<one-line>",
    "convention_notes": "<one-line, e.g., 'Brown terminal-utility convention'>"
  },
  "spots": {
    "<spot_id>": {
      "context": "<SB_RFI | BB_vs_SB_RFI | SB_vs_BB_3bet | ...>",
      "action_sequence": "<engine action history token>",
      "actions": ["fold", "call", "<size>", "..."],
      "expected_strategy": {
        "AA": [<probs aligned with `actions`>],
        "...": [...]
      },
      "expected_dominant_action": {
        "AA": "<one of `actions`>",
        "...": "..."
      },
      "notes": "<per-spot caveats>"
    }
  },
  "nash_multiplicity_notes": [
    "<one caveat per documented multiplicity region>"
  ]
}
```

**Either `expected_strategy` (full distribution) OR
`expected_dominant_action` (label-only) is required per spot.** Charts
that publish only "which hand is in the range" can fill
`expected_dominant_action` and leave `expected_strategy: null`. Charts
that publish full mixed strategies fill both.

For fixtures that reference data already on disk (rather than inlining
it), the `fixture_kind: "indirect"` + `data_file_relative: "<repo-relative
path>"` pattern is used. See
`hu_pushfold_self_2_to_15bb_v1.json` for an example.

## Diff-test consumer contract

Phase 7's `tests/test_blueprint_diff_vs_external.py` (not yet shipped)
loads every `*.json` in this directory and computes per-class L1 against
the Premium-A blueprint shard whose `config.stack_depth_bb` matches the
fixture. Per memory rule `feedback_silent_skip_hazard`: missing fixtures
or mismatched depths SKIP **with an explicit visible message**, not
silently.

## Licensing flags (summary; full detail in
`docs/blueprint_reference_inventory.md` §5)

- `user_supplied` with unclear provenance — KEEP unless user identifies
  as commercial-solver export.
- `solver_dump` from our own engine — KEEP (MIT).
- `published_chart` from book / paper — cite + KEEP for citation; do
  not redistribute figure data as raw fixture unless explicitly licensed.
- GTO Wizard / PioSolver / Snowie / Monker — **DO NOT SHIP** without
  explicit licensing review. If a user hands one over, place it in
  `references/manual_downloads/` (which is git-ignored or kept local
  per the user's discretion), not here.
