# poker_solver

A Texas Hold'em equity solver in pure Python — no dependencies.

- **Hand evaluator**: ranks any 5-to-7 card hand into one of the 9 categories (high card → straight flush) with tiebreaker kickers.
- **Monte Carlo equity**: computes win/tie equity for two or more hole-card hands, optionally against a partial board.
- **Range parser**: accepts standard poker range notation (`AA, KK-TT, AKs, AKo, 76s+`) and expands it into combos.
- **CLI**: `poker-solver equity` runs equity simulations from the command line.

## Install

```bash
pip install -e .
```

## CLI

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

Output:

```
Hand 1: AhKh   win 46.21%  tie  0.43%  equity 46.43%
Hand 2: QdQc   win 53.36%  tie  0.43%  equity 53.57%
```

## Library

```python
from poker_solver import equity, parse_hand, parse_board

hands = [parse_hand("AhKh"), parse_hand("QdQc")]
board = parse_board("2h7h9d")
result = equity(hands, board=board, iterations=10000)
for i, r in enumerate(result):
    print(f"hand {i}: equity = {r.equity:.2%}")
```

## Run tests

```bash
pip install -e .[dev]
pytest
```

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
