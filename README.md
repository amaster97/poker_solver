# poker_solver

A Texas Hold'em equity calculator + GTO solver, written in Python with a Rust performance tier.

- **Hand evaluator**: ranks any 5-to-7 card hand into one of the 9 categories (high card → straight flush) with tiebreaker kickers.
- **Monte Carlo equity**: computes win/tie equity for two or more hole-card hands, optionally against a partial board.
- **Range parser**: accepts standard poker range notation (`AA, KK-TT, AKs, AKo, 76s+`) and expands it into combos.
- **GTO solver (preview)**: Discounted CFR (Brown & Sandholm 2019) in a two-tier architecture — readable Python reference + fast Rust production. Currently solves Kuhn poker; HUNL postflop + preflop coming in follow-up PRs (see `PLAN.md`).
- **CLI**: `poker-solver equity` and `poker-solver solve`.

## Build

A Rust toolchain is required because the project includes a Rust extension module via PyO3.

```bash
# One-time: install Rust (skip if already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
source "$HOME/.cargo/env"

# Build + install the package (this builds both Python and Rust):
pip install -e .
```

## CLI

### Equity (Monte Carlo)

```bash
# Hand vs hand
poker-solver equity AhKh QdQc

# Hand vs hand on a flop
poker-solver equity AhKh QdQc --board 2h7h9d

# Three-way with a turn
poker-solver equity AsKs QdQc 7h7d --board 2h7c9d --iterations 50000

# Range vs hand
poker-solver equity "AA,KK,AKs" QdQc --iterations 20000
```

### Solver (preview)

Solve Kuhn poker to equilibrium via Discounted CFR (DCFR):

```bash
# Python reference tier (slow, readable)
poker-solver solve --game kuhn --iterations 50000

# Rust production tier (fast)
poker-solver solve --game kuhn --iterations 50000 --backend rust
```

Output is the average-strategy table per information set, the game value (P1 perspective), and the final exploitability. Both backends produce numerically equivalent strategies (within 1e-4 per action probability) — this is enforced by the differential test in `tests/test_dcfr_diff.py`.

## Library

```python
from poker_solver import equity, parse_hand, parse_board, solve, KuhnPoker

# Equity calc
hands = [parse_hand("AhKh"), parse_hand("QdQc")]
board = parse_board("2h7h9d")
result = equity(hands, board=board, iterations=10000)
for i, r in enumerate(result):
    print(f"hand {i}: equity = {r.equity:.2%}")

# CFR solve
r = solve(KuhnPoker(), iterations=50000)               # Python backend
r = solve(KuhnPoker(), iterations=50000, backend="rust")  # Rust backend
print(f"Game value: {r.game_value:+.6f}")              # ≈ -1/18
```

## Run tests

```bash
pip install -e .[dev]
pytest
```

## References

The project relies on a curated set of papers, OSS solver repos, and competitor blog posts that are **kept local only** (not checked into git — 3rd-party copyright + repo size). To populate them on a fresh clone:

```bash
sh scripts/setup_references.sh
```

That clones the 6 OSS reference solvers into `references/code/`. Papers and blog posts need to be fetched manually; see `PLAN.md` for the must-have list. See `PLAN.md` for the long-term roadmap and full decision log.

## Notation

- Ranks: `2 3 4 5 6 7 8 9 T J Q K A`
- Suits: `s h d c` (spades, hearts, diamonds, clubs)
- A card is two characters: rank + suit (e.g. `Ah`, `Ts`, `2c`)
- Range notation:
  - `AA` — pocket aces
  - `AKs` — ace-king suited
  - `AKo` — ace-king offsuit
  - `AK` — both suited and offsuit
  - `KK-TT` — pocket pairs from KK down to TT
  - `76s+` — 76s, 87s, 98s, T9s, JTs, QJs, KQs (suited connectors at or above 76s)
  - Comma-separated combinations: `AA, KK-TT, AKs, AKo`

## License

MIT
