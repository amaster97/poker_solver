# Developer guide

This is the "I want to make the codebase do something" entry point. Read
[`README.md`](README.md) for user-facing features and [`CONTRIBUTING.md`](CONTRIBUTING.md)
for the dev-environment setup, branching, license rules, and PR audit
contract — this document does not repeat those, it cross-links them and
focuses on architecture, mental model, and the workflow for landing a
substantive change. For the strategic roadmap and locked design
decisions see [`PLAN.md`](PLAN.md).

Goal: orient a new contributor in about fifteen minutes.

## 1. Two-tier architecture (why, and how to use it)

The repo is split into two parallel implementations of the same
algorithm:

- **Python reference tier** — [`poker_solver/`](poker_solver/). The
  readable spec. Numpy-backed DCFR, easy to read line-by-line, easy to
  debug. Slow for anything beyond Kuhn / Leduc / a tiny river subgame
  but bit-exact against itself across runs.
- **Rust performance tier** — [`crates/cfr_core/`](crates/cfr_core/),
  exposed to Python as `poker_solver._rust` through PyO3 / maturin. The
  workhorse. Same algorithm, same hyperparameters, same infoset keying,
  same action ordering — measured ~24x faster on HUNL postflop
  (3.88 s Rust vs 92.9 s Python at 100k iters on an M4 Pro).

The two tiers are gated by **differential testing**:
[`tests/test_dcfr_diff.py`](tests/test_dcfr_diff.py),
[`tests/test_leduc_diff.py`](tests/test_leduc_diff.py),
[`tests/test_hunl_diff.py`](tests/test_hunl_diff.py), and
[`tests/test_river_diff.py`](tests/test_river_diff.py) run both
backends with the same seeds and assert agreement to ~1e-4 per action
probability. A Rust change that drifts strategies fails CI. This is the
single most load-bearing invariant in the repo, so do not weaken it
without an explicit PR-level decision.

The two-tier pattern is not novel: Noam Brown's reference repo
[`references/code/noambrown_poker_solver`](references/code/) ships a
`python/` and a `cpp/` tier with the same correspondence. We adopted
it for the same reason — the readable tier is the spec, the fast tier
is the deliverable, the diff test is the gate.

**Rule of thumb:** Algorithm changes (new DCFR variant, abstraction
tweak, action set change) land in Python first, get tested against a
closed-form Nash value or open_spiel oracle where one exists, then
port to Rust, then pass the diff test. Performance-only changes (a
SIMD inner loop, a cache-blocking pass) land in Rust and are gated by
the existing diff tests plus a perf benchmark.

## 2. Repo tour

Top-level layout:

| Path | Purpose |
|---|---|
| [`poker_solver/`](poker_solver/) | Python reference tier (ground truth). |
| [`crates/cfr_core/`](crates/cfr_core/) | Rust performance tier (PyO3 ext). |
| [`tests/`](tests/) | Pytest suite. `test_*_diff.py` are the two-tier gates. |
| [`references/`](references/) | Papers, blogs, OSS solver clones. Read-first source of truth. |
| [`ui/`](ui/) | NiceGUI app (PR 10a; mock-backed today, PR 10b swaps in real). |
| [`scripts/`](scripts/) | `check_pr.sh`, chart generation, macOS packaging. |
| [`docs/`](docs/) | Per-PR prep folders, audit reports, release notes, architecture deep-dive. |

Inside [`poker_solver/`](poker_solver/):

- [`card.py`](poker_solver/card.py), [`evaluator.py`](poker_solver/evaluator.py), [`range.py`](poker_solver/range.py) — primitives.
- [`equity.py`](poker_solver/equity.py) — hybrid exact/Monte Carlo equity.
- [`games.py`](poker_solver/games.py) — `Game` protocol plus `KuhnPoker` and `LeducPoker`.
- [`dcfr.py`](poker_solver/dcfr.py) — the DCFR algorithm; quote it when citing the update equations.
- [`solver.py`](poker_solver/solver.py) — the `solve()` entry point that dispatches across games and backends.
- [`hunl.py`](poker_solver/hunl.py) — HUNL game state machine, integer-cents chip arithmetic.
- [`action_abstraction.py`](poker_solver/action_abstraction.py) — 14-action abstraction with raise caps.
- [`hunl_solver.py`](poker_solver/hunl_solver.py) — HUNL postflop solver tying tree + DCFR + abstraction together.
- [`abstraction/`](poker_solver/abstraction/) — EMD-based card bucketing (256/128/64 flop/turn/river).
- [`charts/`](poker_solver/charts/) — push/fold lookup JSONs (2–15 BB).
- [`pushfold.py`](poker_solver/pushfold.py) — push/fold chart loader; auto-dispatched from `solve()` below 15 BB effective.
- [`library.py`](poker_solver/library.py), [`library_schema.sql`](poker_solver/library_schema.sql) — solution library / persistence.
- [`cli.py`](poker_solver/cli.py) — argparse-based CLI; ships as `poker-solver`.

Inside [`crates/cfr_core/src/`](crates/cfr_core/src/):

- [`lib.rs`](crates/cfr_core/src/lib.rs) — PyO3 module surface (`poker_solver._rust`).
- [`dcfr.rs`](crates/cfr_core/src/dcfr.rs), [`solver.rs`](crates/cfr_core/src/solver.rs) — the algorithm.
- [`game.rs`](crates/cfr_core/src/game.rs) — Rust `Game` trait (mirrors the Python protocol).
- [`kuhn.rs`](crates/cfr_core/src/kuhn.rs), [`leduc.rs`](crates/cfr_core/src/leduc.rs) — small-game ports.
- [`hunl.rs`](crates/cfr_core/src/hunl.rs), [`hunl_tree.rs`](crates/cfr_core/src/hunl_tree.rs), [`hunl_eval.rs`](crates/cfr_core/src/hunl_eval.rs), [`hunl_solver.rs`](crates/cfr_core/src/hunl_solver.rs) — HUNL postflop port.
- [`abstraction.rs`](crates/cfr_core/src/abstraction.rs) — bucket lookup from the precomputed `.npz`.

Inside [`references/`](references/):

- [`papers/`](references/papers/) — PDFs of DCFR, CFR+, vanilla CFR, Libratus, Pluribus, Deep CFR, ReBeL, hyperparameter schedules, surveys. Per-paper notes in `papers/_INDEX.md`.
- [`code/`](references/code/) — gitignored OSS solver clones (cloneable via `scripts/setup_references.sh`): `noambrown_poker_solver`, `slumbot2019`, `open_spiel`, `postflop-solver`, `TexasSolver`, `shark-2.0`.
- [`blog/`](references/blog/), [`products/`](references/products/) — competitor analysis.

## 3. Setup

Prerequisites: Python 3.9+ (developed on 3.13), the Rust stable
toolchain, and `maturin` (pulled in via the `dev` extra). [`CONTRIBUTING.md`](CONTRIBUTING.md)
has the canonical install recipe; the dev-tier short version is:

```bash
pip install -e ".[dev]"      # builds Python + Rust + dev tools (pytest, ruff, mypy, maturin)
```

If you only want a fast rebuild of the Rust side without reinstalling
the wheel:

```bash
maturin develop --release --manifest-path crates/cfr_core/Cargo.toml
```

First-run sanity check on a fresh clone of `main`:

```bash
pytest -x                                                           # Python suite, fail-fast
cargo test --all --manifest-path crates/cfr_core/Cargo.toml          # Rust suite
```

Both should be green. If they are not, that is a bug; file an issue.

## 4. DCFR at a glance

The algorithm is tabular Discounted CFR (Brown & Sandholm, AAAI 2019),
with the paper-default hyperparameters `(alpha, beta, gamma) = (1.5, 0.0, 2.0)`.
Quote these equations exactly (verbatim from
[`poker_solver/dcfr.py`](poker_solver/dcfr.py)):

```text
R^t(I, a) = R^{t-1}(I, a) * (t^alpha / (t^alpha + 1)) + r^t(I, a)   if R^{t-1} > 0
R^t(I, a) = R^{t-1}(I, a) * (t^beta  / (t^beta  + 1)) + r^t(I, a)   if R^{t-1} <= 0
s_I[a]    = s_I[a] * (t / (t + 1))^gamma + pi_{-i}(I) * sigma^t(I, a)
```

With `beta = 0` the negative-regret scale `t^0 / (t^0 + 1) = 1/2`, i.e.
negative regrets are halved each iteration rather than zeroed (regret
matching+, used by CFR+, is the `beta = -inf` corner). The strategy sum
is weighted by `((t-1)/t)^gamma` on the prior accumulator before the
new contribution lands.

**Convergence is measured as exploitability as a percentage of pot,
not iteration count.** A million iterations on a degenerate tree can
still be far from Nash; a few thousand on a well-abstracted tree can be
within 0.01 BB/100. For Kuhn we compare to the closed-form Nash value
of -1/18; for Leduc we diff against `open_spiel`; for HUNL river spots
we diff against `noambrown/poker_solver` (see
[`tests/test_river_diff.py`](tests/test_river_diff.py)).

## 5. Adding a new game

The `Game` protocol in [`poker_solver/games.py`](poker_solver/games.py)
is the entry point. To add a new game:

1. **Python first.** Implement the protocol (`num_players`,
   `initial_state`, `current_player`, `legal_actions`, `apply`,
   `is_terminal`, `utility`, `infoset_key`, optional
   `chance_outcomes`) on a new class.
2. **Closed-form check (if available).** If the game has a known
   Nash value (Kuhn) or a published oracle (Leduc via open_spiel),
   add a single-backend test that converges to it within tolerance.
3. **Port to Rust.** Add `crates/cfr_core/src/<game>.rs`, implement
   the `Game` trait there, wire it into [`lib.rs`](crates/cfr_core/src/lib.rs).
4. **Differential test.** Add a `tests/test_<game>_diff.py` that runs
   both backends on the same seed and asserts strategy agreement.
5. **CLI hook (optional).** Add a `--game <name>` branch to
   [`poker_solver/cli.py`](poker_solver/cli.py) so the new game is
   reachable from the command line.

[`poker_solver/games.py::LeducPoker`](poker_solver/games.py) is the
cleanest reference implementation — multi-round, with a mid-game chance
node, ~288 infosets — for what a non-trivial new game looks like.

## 6. PR workflow

[`CONTRIBUTING.md`](CONTRIBUTING.md) has the full contract; the
developer-facing summary:

- **Branch.** From PR 3 onward every change ships on its own feature
  branch named `pr-N-<short-title>`. Never commit to `main`.
- **Check battery.** Run [`sh scripts/check_pr.sh`](scripts/check_pr.sh)
  before opening the PR. It runs the full pytest suite, `cargo test`,
  `ruff check` + `black --check`, `mypy poker_solver` (strict),
  `cargo clippy --all-targets -- -D warnings`, all diff tests, license
  / dependency audit (catches AGPL strings in build files), a perf
  gate, and references integrity. It writes
  [`pr_report.md`](pr_report.md) at the repo root; that file must be
  clean.
- **Audit (PR 3+).** A fresh general-purpose agent with no
  implementation context reads the diff and writes
  [`audit_report.md`](audit_report.md) categorizing findings as
  must-fix / should-fix / nice-to-fix / looks-good. Both reports must
  be clean before merge.
- **Test timeouts.** `pyproject.toml` sets a per-test wall-clock
  default of **90 seconds** (`pytest-timeout`). Mark long-running tests
  with `@pytest.mark.slow` (5 min – 1 hr range; included by default,
  deselect with `-m 'not slow'`). For hour-scale precompute jobs use
  `@pytest.mark.very_slow`, which opts out of the timeout cap.

## 7. Reference-first rule

[`references/README.md`](references/README.md) is the topic-to-file
index for the entire CFR / DCFR / HUNL literature plus competitor
solver code. **Check it before any technical claim.** If a paper or a
competitor repo is the authoritative source for a formula, hyperparameter,
or architectural choice, quote that source — do not paraphrase from
training data. This rule applies in code comments, docstrings, PR
descriptions, and prose docs.

If you are unsure where to look, start in [`references/papers/_INDEX.md`](references/papers/_INDEX.md)
and `references/code/<repo>/_NOTES.md`.

## 8. License rules (load-bearing)

Project license is **MIT** and is locked. AGPL contamination is a
one-way door. Summary table (the full version lives in
[`references/README.md`](references/README.md) section 2):

| Repo | License | Copy policy |
|---|---|---|
| `noambrown_poker_solver` | MIT | OK to port verbatim with attribution. |
| `slumbot2019` | MIT | OK to port verbatim with attribution. |
| `open_spiel` | Apache 2.0 | OK to copy with attribution. Also our Kuhn/Leduc oracle. |
| `postflop-solver` | AGPL-3.0 | **Read-only inspiration. Do not copy.** |
| `TexasSolver` | AGPL-3.0 | **Read-only inspiration. Do not copy.** |
| `shark-2.0` | Unlicensed (effectively all-rights-reserved) | **Read-only inspiration. Do not copy.** |

If you are unsure whether a snippet was influenced by an AGPL source,
say so in the PR — rewriting from the underlying paper is cheap;
contamination is permanent.

## 9. Conventions

- **Python:** `ruff check` clean, `black --check` clean, `mypy
  poker_solver` strict-clean on new code.
- **Rust:** `cargo clippy --all-targets -- -D warnings` clean (zero
  warnings).
- **No floating-point chip math** anywhere in
  [`poker_solver/hunl.py`](poker_solver/hunl.py). Integer cents only;
  convert to BB-floats at terminal states.
- **Per-decision audit trail.** Substantive design decisions go in
  [`docs/autonomous_log.md`](docs/autonomous_log.md) with date,
  rationale, and the references consulted.
- **No emojis in code or docs** unless explicitly requested by the
  user.

## 10. Where to go next

- [`PLAN.md`](PLAN.md) — strategic roadmap. PR 8 (NEON SIMD + cache
  blocking + public chance sampling), PR 9 (HUNL preflop full solve),
  and PR 10b (mock -> real solver swap in the UI) are the next
  scheduled tracks.
- [`docs/<pr>_prep/`](docs/) — staged launch docs for each PR
  (e.g. [`docs/pr8_prep/`](docs/pr8_prep/), [`docs/pr9_prep/`](docs/pr9_prep/)).
- [`docs/audit_followup_backlog.md`](docs/audit_followup_backlog.md) —
  known should-fix items from prior audits, with severity tags. Good
  first-issue source.
- [`docs/architecture.md`](docs/architecture.md) — deeper architectural
  reference if you want the long version of section 1 above.
