# Range preset library

This directory ships the PR 24b §3.1 preset library. Each `chart_*.json`
file is a single named range loadable via the UI's preset dropdown
(`ui/views/spot_input.py:_render_chart_preset_row`).

## Schema

```json
{
  "name": "<human-readable label>",
  "format": "pio_range_string",
  "data": "AA,KK,QQ,AKs,AKo,..."
}
```

Optional fields (ignored by the loader, useful for provenance):

- `_source`: one-line provenance note (where the range came from).
- `_combo_count_approx`: rough total combo count for sanity checks.

The `data` field uses standard Pio range syntax (suited / offsuit /
pair tokens, comma-separated). It is parsed via
`RangeWithFreqs.from_string(data)` which routes through
`poker_solver.range.parse_range`.

## Built-in presets (PR 24b)

| File | Stack | Combo count | Notes |
|------|-------|------------|-------|
| `chart_100bb_sb_open.json` | 100 BB | 606 (~46% of 1326) | HU SB-open default |
| `chart_100bb_bb_defend.json` | 100 BB | 526 (~40%) | BB-defend vs SB open |
| `chart_100bb_btn_3bet.json` | 100 BB | 162 (~12%) | Linear+blockers 3-bet |
| `chart_30bb_sb_jam.json` | 30 BB | 258 (~19%) | Short-stack SB jam |

**Honest framing:** These presets are published heuristics, not
authoritative GTO outputs. No reference repository in `references/`
provides authoritative range tables. Users SHOULD re-solve to confirm
against their site / format / stack depth. The presets are convenience
starting points — useful for quick exploration; not for production
decisions without further validation.

## User-saved presets

The UI's "Save as preset" button writes to `~/.poker_solver/charts/`.
User presets follow the same schema and are picked up by the loader
alongside the built-ins.

## TODO

- Source authoritative HU equilibrium ranges from the noambrown
  reference solver or postflop-solver test fixtures and cross-validate
  the published heuristics above. Currently the heuristics are
  conservative and untested against a reference solve.
- Add 3-bet pot defending ranges, c-bet response ranges, and turn /
  river bluff-catch ranges once authoritative sources land.
