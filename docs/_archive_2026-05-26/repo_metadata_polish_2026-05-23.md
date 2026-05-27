# Repo Metadata Polish — 2026-05-23

Outside-observer audit flagged stale repo metadata. Two GitHub-side fixes
applied to `amaster97/poker_solver` (public repo).

## Fix #1: Description

**Old (stale, pre-v1 wording):**
```
Texas Hold'em equity solver in pure Python: hand evaluator, Monte Carlo equity, range parser, CLI.
```

**New (accurate, post-v1.4.0, ~340 chars):**
```
MIT-licensed two-tier (Python + Rust via maturin) HUNL Texas Hold'em GTO solver. Tabular DCFR with vector-form CFR for true range Nash; preflop push/fold + postflop tree solving; aggregator vs Nash range-vs-range APIs; NiceGUI GUI + macOS .dmg + CLI. Card abstraction 256/128/64 (flop/turn/river); diff-tested vs Brown's MIT reference.
```

Status: APPLIED + verified via `gh repo view --json description`.

## Fix #2: Topics

**Old:** `null` (no topics set).

**New (12 topics, alphabetical):**
- cfr
- dcfr
- gto
- holdem
- maturin
- nash-equilibrium
- poker
- poker-solver
- pyo3
- python
- rust
- texas-holdem

Status: APPLIED + verified via `gh repo view --json repositoryTopics`.
Count: 12 (within GitHub's 20-topic limit).

## Fix #3: Homepage URL

Current value: `""` (empty).
Action: UNCHANGED — no obvious URL to set; user can add a project page
later if desired.

## Verification command

```bash
gh repo view amaster97/poker_solver --json description,repositoryTopics,homepageUrl
```

## Anomalies

None. Both `gh repo edit` invocations returned cleanly (no output, which
is gh's success convention for write commands). Post-write JSON read
back the exact applied values for description + all 12 topics.

## Verdict

METADATA-POLISHED
