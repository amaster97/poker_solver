# User-facing doc usage path verification — 2026-05-26

## Environment

- **python:** Python 3.13.1 at `/usr/local/bin/python` (`/Library/Frameworks/Python.framework/Versions/3.13`)
- **pyenv shim default:** 3.13-dev (`/Users/ashen/.pyenv/shims/python`) — **NOT** where poker_solver is installed
- **poker-solver CLI on PATH:** `/Users/ashen/.pyenv/shims/poker-solver` → resolves to `/Users/ashen/.pyenv/versions/3.13-dev/bin/poker-solver` (no `poker_solver` package in that env)
- **Working CLI binary:** `/Users/ashen/Library/Python/3.13/bin/poker-solver` (shebang `#!/usr/local/bin/python3`)
- **Editable install pointer:** `/Users/ashen/Library/Python/3.13/lib/python/site-packages/poker_solver.pth` → `/private/tmp/w2.3-retest-4234` (**DOES NOT EXIST** — dangling)
- **Actual import source:** `/Users/ashen/Desktop/poker_solver/poker_solver/__init__.py` (resolved only when CWD or `PYTHONPATH=/Users/ashen/Desktop/poker_solver` is set)
- **`import poker_solver`:** PASS (only when invoked from within `/Users/ashen/Desktop/poker_solver` OR with `PYTHONPATH` set). FAILS otherwise with `ModuleNotFoundError: No module named 'poker_solver'`.
- **`from poker_solver._rust import solve_range_vs_range_rust`:** PASS (under the same conditions).
- **Version reported:** `poker_solver.__version__ == "1.7.0"`.

### CRITICAL environment finding

The installed entry-point script `poker-solver` fails out-of-the-box (`ModuleNotFoundError: No module named 'poker_solver'`) because the editable install `.pth` points at a directory that no longer exists (`/private/tmp/w2.3-retest-4234`). Every CLI invocation in every user-facing doc below was tested with the workaround `PYTHONPATH=/Users/ashen/Desktop/poker_solver`. A user following the docs verbatim on this machine — without re-running `pip install -e .` — will hit `ModuleNotFoundError` on every `poker-solver` invocation. The docs assume a clean install; a re-`pip install -e .` from the project root would fix this, but the user explicitly requested not to reinstall. **This is the highest-priority blocker for a doc commit shipped against this environment.**

## Commands found and tested

| Source | File:Line | Command | Status | Notes |
|---|---|---|---|---|
| README.md | L41 | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh -s -- -y --default-toolchain stable` | SKIP-DANGEROUS | Network-touching installer; not re-running. |
| README.md | L42 | `source "$HOME/.cargo/env"` | SKIP | Env shim; no-op to verify. |
| README.md | L45 | `pip install -e .` | SKIP-LONG | Per task constraints; would also break editable pointer. |
| README.md | L48 | `pip install -e ".[dev]"` | SKIP-LONG | Same. |
| README.md | L51 | `pip install -e ".[ui]"` | SKIP-LONG | Same. |
| README.md | L58 | `cargo build --release --manifest-path crates/cfr_core/Cargo.toml` | SKIP-LONG | Long compile; manifest path verified to exist. |
| README.md | L68 | `poker-solver equity AhKh QdQc --board 2h7h9d` | PASS | Exact enumeration; 990 iters; AhKh 54.14% vs QdQc 45.86%. |
| README.md | L71 | `poker-solver equity "AA,KK,AKs" QdQc` | PASS (reduced) | Ran with `-n 50` for speed; 16-combo range vs QdQc. Default 250k iters is SKIP-LONG. |
| README.md | L74 | `poker-solver equity AhKh QdQc -n 1000000 --seed 0` | PASS (reduced) | Ran with `-n 1000`; full 1M is SKIP-LONG. |
| README.md | L77 | `poker-solver solve --game kuhn --iterations 50000 --backend python` | PASS (reduced) | Ran with `--iterations 500`; Kuhn solve converged. |
| README.md | L80 | `poker-solver solve --game leduc --iterations 5000 --backend rust` | PASS (reduced) | Ran with `--iterations 500`; Leduc solve converged. |
| README.md | L83 | `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500` | PASS (reduced) | Ran with `--iterations 100`; tiny_subgame fixture (river AhKc vs QdQh) completed. |
| README.md | L86 | `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust` | PASS (reduced) | Ran with `--iterations 100`; Rust backend OK. |
| README.md | L89-91 | `poker-solver solve --game hunl --hunl-mode postflop --board "As 7c 2d" --stacks 100 --bet-sizes "33,75,150" --iterations 500 --backend rust` | SKIP-LONG | 100-iter retry exceeded 90s wall-clock; confirms the README "Known issues" note about chance-enum-at-root being slow on full flop solves. |
| README.md | L98 | `from poker_solver import get_pushfold_strategy, get_full_range; print(get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs"))` | PASS | Returns 1.0. |
| README.md | L100 | `chart = get_full_range(stack_bb=8, position="bb_call_vs_jam")` | PASS | Returns 169-cell dict. |
| README.md | L115 | `from poker_solver import HUNLConfig, HUNLPoker, Range, solve, solve_range_vs_range` | PASS | All top-level imports resolve. |
| README.md | L121 | `r = solve(HUNLPoker(HUNLConfig(starting_stack=10000)), iterations=2000, locked_strategies={"<infoset_key>": [0.6, 0.4]})` | SKIP-LONG / FAIL | Did not complete in 90s even with `iterations=10`. Default `HUNLConfig(starting_stack=10000)` is `full` mode preflop which raises `NotImplementedError` somewhere upstream, or the call balloons. **Plus:** the example uses a literal placeholder infoset key (`"<infoset_key>"`) that does not exist in any tree — locked dict entries with no matching infoset are silently ignored, but the doc reader will not know this. Recommend rewriting against `solve_hunl_postflop` with a river fixture, as USAGE §5.3 does. |
| README.md | L127 | `hero, villain = Range("AA, KK, AKs"), Range("QQ-99, AKo"); agg = solve_range_vs_range(template_config, hero, villain, iterations=200)` | **FAIL** | `Range("...")` is a dataclass with `combos: list[Combo]` — it does NOT parse the string; it stores `"AA, KK, AKs"` as the `combos` field. Iteration yields single characters. `solve_range_vs_range` then calls `_combo_to_hand_class(...)` on a 1-char string → `ValueError: combo must have 2 cards; got 1`. **The correct form is `parse_range("AA, KK, AKs")` or `["AA", "KK", "AKs"]`.** Bug repeats in `docs/README_proposed_update_2026-05-23.md` L144-145. |
| README.md | L130 | `vec = solve_range_vs_range_rust(template_json, iters=200, alpha=1.5, beta=0.0, gamma=2.0, p0_holes=p0_combos, p1_holes=p1_combos)` | **FAIL** | Kwarg is named `iterations`, not `iters`. `TypeError: solve_range_vs_range_rust() got an unexpected keyword argument 'iters'`. Same bug in `docs/README_proposed_update_2026-05-23.md` L149. |
| README.md | L158 | `pip install -e ".[ui]"` | SKIP-LONG | Already covered above. |
| README.md | L159 | `poker-solver ui` | **SKIP-DANGEROUS** | Per task hard constraint. |
| README.md | L184 | `pytest` | SKIP-LONG | Full suite; ran `tests/test_cli_subcommands.py` only per task — 6 PASS, 1 FAIL (timeout on `test_parity_happy_path_runs_to_completion` — see CLI subcommand section below). |
| README.md | L185 | `cargo test --all --manifest-path crates/cfr_core/Cargo.toml` | SKIP-LONG | Cargo test build is slow; manifest exists. |
| README.md | L188-190 | `ruff check`, `ruff format --check`, `cargo clippy ...` | SKIP-LONG | Dev-only commands; not in the user-running path. |
| README.md | L194 | `sh scripts/check_pr.sh` | SKIP-LONG | Pre-PR battery; script exists. |
| README.md | L252 | `sh scripts/setup_references.sh` | SKIP-DANGEROUS | Per task constraint (network downloads). Script exists. |
| USAGE.md | L48 | `sh scripts/build_macos_dmg.sh` | SKIP-DANGEROUS | Builds the experimental .dmg; would invoke PyInstaller / signing; script exists. |
| USAGE.md | L62 | `curl ... \| sh -s ...` (rustup) | SKIP-DANGEROUS | Same as README L41. |
| USAGE.md | L65-66 | `pip install -e .`, `pip install -e .[ui]` | SKIP-LONG | Same as README. |
| USAGE.md | L92-93 | `python -c "from poker_solver import get_pushfold_strategy; print(get_pushfold_strategy(stack_bb=10, position='sb_jam', hand='AKs'))"` | PASS | Returns 1.0. |
| USAGE.md | L96-97 | `python -c "from poker_solver import get_full_range; import json; print(json.dumps(get_full_range(8, 'bb_call_vs_jam'), indent=2))"` | PASS | Returns 169-cell JSON. |
| USAGE.md | L116 | `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 500` | PASS (reduced 100) | Same as README L83. |
| USAGE.md | L119 | `poker-solver solve --game hunl --hunl-mode tiny_subgame --iterations 1000 --backend rust` | PASS (reduced 100) | Same as README L86. |
| USAGE.md | L141 | `poker-solver equity AhKh QdQc --board 2h7h9d` | PASS | Same as README L68. |
| USAGE.md | L144 | `poker-solver equity "AA,KK,AKs" QdQc` | PASS (reduced) | Same as README L71. |
| USAGE.md | L147 | `poker-solver equity AhKh QdQc -n 1000000 --seed 0` | PASS (reduced 1000) | Same as README L74. |
| USAGE.md | L158 | `poker-solver ui` | **SKIP-DANGEROUS** | Per task hard constraint. |
| USAGE.md | L202-222 | `solve(HUNLPoker(cfg), iterations=500, backend='rust')` on river full-range (§5.1 worked example) | SKIP-LONG | 100-iter attempt did not complete in 90s. **Already caveated in the doc itself (§5.1 "Honest perf caveat" L257-269)** — observed behavior matches the doc's warning. |
| USAGE.md | L289-331 | `solve_range_vs_range(config_template=cfg, hero_range=['AA','KK','AKs','AKo','QQ'], villain_range=['QQ','JJ','TT','AQs'], iterations=200, backend='rust')` (§5.2) | PASS (reduced) | Tested with `hero_range=['AA','KK','AKs']`, `villain_range=['QQ','JJ']`, `iterations=50` on a turn-start board; completed in 3.5s; returned `position='aggressor'`, `range_aggregate={'bet_75': 0.99996, 'check': 4.4e-05}`. |
| USAGE.md | L324-331 | Same as above with `hero_player=1` | UNTESTED | Identical signature to §5.2 aggressor case; high confidence based on aggressor working. |
| USAGE.md | L408-425 | `solve_hunl_postflop(cfg, iterations=500, locked_strategies={"<infoset_key_str>": [1.0,0.0,0.0,0.0]})` on river (§5.3) | PASS (reduced 100) | Ran with `initial_hole_cards=((Ah,Kc),(Qd,Qh))` and a literal `"<infoset_key_str>"` lock; completed in 1.2s; `game_value=+5.0027`. Note: the lock key is a placeholder; no infoset matches it, so the lock is a no-op — same risk as README L121. |
| USAGE.md | L440-457 | `solve_hunl_postflop(cfg, iterations=500)` on flop with `initial_contributions=(100,150)` (§5.4 asymmetric) | SKIP-LONG | The literal call as written does not complete (default Python backend, FLOP-start chance-enum at full-range action menu is the heavy path documented in §5.1 / §7b). I retried with `iterations=20` and a 90s budget; did not complete. **Note: this is the "fixed hole cards" path, not the chance-enum path** — so this is a separate perf issue not covered by the §5.1 caveat. The `HUNLConfig(...)` itself constructs fine. |
| USAGE.md | L478-480 | `Range.diff` example (`r1.diff(r2)`) | **FAIL** | Same root cause as README L127: `Range("AA, KK, AKs")` does not parse; `combos` field receives the string; `iter(Range)` yields chars; `diff` raises `AttributeError: 'str' object has no attribute 'rank'`. **The doc says "available since v1.4.3" — but the function only works when Range is built via `parse_range(...)` or `Range.add(combo)`, NOT via the `Range("...")` constructor form the doc implies.** |
| USAGE.md | L529-551 | `solve_range_vs_range_nash(config_template=cfg, hero_range=['AA','KK','QQ','JJ','TT'], villain_range=['AA','KK','AKs','AKo'], iterations=500, hero_player=1)` on river (§5.6) | SKIP-LONG | Tried `iterations=100` with reduced ranges (`['AA','KK']` × `['AA','KK']`); did not complete in 90s. The doc's own caveat at L513-515 acknowledges "slower than the aggregator on larger fixtures (8-class × flop × 500 iter has measured >20 min)". |
| USAGE.md | L592 | `poker-solver library list --table` | PASS | Returns exit 0 with empty output (empty DB at `~/.poker_solver/library.db` doesn't exist; falls through clean). |
| USAGE.md | L593 | `poker-solver library export <spot_id> ./my_spot.json` | PASS (signature) | `--help` confirms positional `spot_id output_path`; matches doc literal. |
| USAGE.md | L594 | `poker-solver library import ./my_spot.json` | PASS (signature) | `--help` confirms positional `input_path`. |
| USAGE.md | L598-609 | Python library API: `Library.open(...)`, `lib.put(spot, result)`, `lib.get(spot_id)` | PASS | Verified end-to-end in a tempdir: `cfg = default_tiny_subgame(); result = solve(HUNLPoker(cfg), iterations=50); ... lib.put(...); lib.get(...)`. |
| USAGE.md | L651 | `poker-solver pushfold --stack 10 --position sb_jam --hand AKs` | PASS | Output: `AKs sb_jam 10BB: 1.000000`. |
| USAGE.md | L654-655 | `poker-solver pushfold --stack 8 --position bb_call_vs_jam --full-range --json` | PASS | Returns 169-cell JSON. |
| USAGE.md | L669-670 | `poker-solver river --board "As 7c 2d Kh 5s" --hero AhKh --villain-range "QQ,JJ,AKs" --iters 200` | **FAIL** | `error: --hero 'AhKh' overlaps with --board 'As 7c 2d Kh 5s'`. **The example hero `AhKh` shares the `Kh` card with the board.** Replacing hero with e.g. `AdQd` makes the command succeed. Doc error. |
| USAGE.md | L683 | `poker-solver parity --fixture dry_K72_rainbow --iters 2000` | SKIP-LONG / FAIL | The `--iters 100` retry did not complete in ~5min; `tests/test_cli_subcommands.py::test_parity_happy_path_runs_to_completion` also TIMED OUT at 60s in our smoke run with `--iters 50`. The parity command also requires `scripts/build_noambrown.sh` to have produced the Brown binary first; absent that, exits with `2`. The doc references the script but does not show it as a prerequisite step in the §7a parity example. |
| docs/dmg_install_guide.md | L19 | `shasum -a 256 ~/Downloads/Poker-Solver-1.6.0-arm64.dmg` | PASS (CLI exists) | `/usr/bin/shasum` available; the named `.dmg` does not exist locally (not in `~/Downloads/`), so the command would error if run as-is on this machine. The user needs to first download the file from the GitHub release. Command shape is correct. |
| docs/dmg_install_guide.md | install / first-launch / Option A & B | Mounting `.dmg`, dragging app, right-click → Open, etc. | SKIP-DANGEROUS | Per task hard constraint — known spawn-loop risk. Procedure shape matches standard macOS adhoc-sign bypass. |
| docs/README_proposed_update_2026-05-23.md | L60-77 | All install commands | Mirrors README; same SKIP-LONG / SKIP-DANGEROUS verdicts. |
| docs/README_proposed_update_2026-05-23.md | L87-110 | All Quick-start CLI commands | Mirrors README L67-91; identical PASS-reduced verdicts. |
| docs/README_proposed_update_2026-05-23.md | L117-119 | `python -c "..."` pushfold snippets | Mirrors README L98-100; PASS. |
| docs/README_proposed_update_2026-05-23.md | L144-145 | `hero, villain = Range("AA, KK, AKs"), Range("QQ-99, AKo"); agg = solve_range_vs_range(template_config, hero, villain, iterations=200)` | **FAIL** | Same `Range("...")` bug as README L127. **The proposed README does not fix this bug — it carries it forward.** |
| docs/README_proposed_update_2026-05-23.md | L149 | `vec = solve_range_vs_range_rust(template_json, iters=200, ...)` | **FAIL** | Same `iters` vs `iterations` kwarg bug as README L130. **Not fixed in the proposed update.** |
| docs/README_proposed_update_2026-05-23.md | L177-178 | `poker-solver ui` | **SKIP-DANGEROUS** | Per task constraint. |
| docs/README_proposed_update_2026-05-23.md | L203-209 | `pytest`, `cargo test`, `ruff`, `cargo clippy` | SKIP-LONG | Same as README. |
| docs/README_proposed_update_2026-05-23.md | L271 | `sh scripts/setup_references.sh` | SKIP-DANGEROUS | Same as README L252. |
| RELEASE_NOTES_2026-05-23.md | L132 | `pip install -e . then maturin develop --release` | SKIP-LONG | Build commands; not exercised. |
| docs/USER_GREETING.md | (no commands) | n/a | n/a | Narrative only. |
| docs/SIGNON_CHECKLIST.md | L14 | `cd /Users/ashen/Desktop/poker_solver && bash scripts/ship_v1_7_1.sh 2>&1 \| tee /tmp/v1.7.1_ship_manual.log` | SKIP-DANGEROUS | Ship script; would attempt cargo + pytest battery + tag + push. Script exists. Doc itself flags this as a 30-45 min manual operation. |

## Drift / inconsistency findings

1. **`Range("AA, KK, AKs")` constructor form is broken** but is shown in **both** the production `README.md` L126 AND the proposed `docs/README_proposed_update_2026-05-23.md` L144 AND the `USAGE.md` §5.5 `Range.diff` example. The proposed README update does NOT fix this — it ships the same bug. Public commit would propagate the bug to readers.

2. **`solve_range_vs_range_rust(..., iters=200, ...)` kwarg is misnamed** in both README L130 and proposed README L149. The PyO3 binding requires `iterations=`. Same as #1 — proposed update ships the bug.

3. **`poker-solver river --hero AhKh` board overlap.** USAGE §7a (L669-670) example fails because the board `As 7c 2d Kh 5s` contains `Kh`, which overlaps with hero `AhKh`. The CLI correctly rejects with an error; the doc example is broken. Fix: use a hero that doesn't overlap (e.g. `AdQd`).

4. **README L121 and USAGE §5.3 use literal placeholder `"<infoset_key>"` / `"<infoset_key_str>"` strings as lock keys.** These do not match any infoset in any tree. The solve completes (silently treats the lock as a no-op), but the user has no way to learn the real key format from the example. USAGE §5.3 partially mitigates by pointing at `tests/test_node_locking.py`, but the README L121 example does not.

5. **README L121 example also uses `solve(HUNLPoker(HUNLConfig(starting_stack=10000)), iterations=2000, ...)` with no `starting_street` or `initial_hole_cards`**, which defaults to a HUNL preflop / full game tree that the solver currently raises `NotImplementedError` on at depth above 15 BB (per USAGE §7 known limitation). The README snippet is unrunnable as written even before considering the lock-key issue.

6. **README L83 vs USAGE L116 iteration count drift.** README uses `--iterations 500`, USAGE uses `--iterations 500` — these match, but L86 vs L119 both use `1000` — they match too. (No drift here, just confirming.)

7. **README L99 vs USAGE §3a syntax drift.** README uses double-quotes:
   `print(get_pushfold_strategy(stack_bb=10, position="sb_jam", hand="AKs"))`
   USAGE uses single-quotes inside the shell `python -c` form:
   `print(get_pushfold_strategy(stack_bb=10, position='sb_jam', hand='AKs'))`
   Both work. Not a bug, just stylistic.

8. **USAGE §5.1 vs §5.4 perf truth.** §5.1 honestly caveats that `initial_hole_cards=()` full-range solves are slow (>10 min). §5.4 shows asymmetric contributions with FIXED hole cards on a FLOP, claiming it works at `iterations=500`, but in practice even `iterations=20` did not complete in 90s in our test. Either the doc needs a perf caveat for §5.4 mirroring §5.1, or the example needs to use turn/river start, or it needs to specify a Rust backend route that the current `solve_hunl_postflop` signature doesn't expose.

9. **`solve_hunl_postflop` has no `backend` kwarg** but USAGE §5.1 (`solve(HUNLPoker(cfg), iterations=500, backend="rust")`) shows passing `backend="rust"` to the top-level `solve()` function (which DOES accept it). The reader migrating between the two `solve*` APIs would not realize this — minor doc clarity issue.

10. **README/USAGE both flag "`poker-solver pushfold` not yet wired" in Known issues sections (README L235-237; USAGE §7a is the section that DOES describe these subcommands as shipped in v1.7.0).** This is internally inconsistent inside the README itself: L234-237 says pushfold/river/parity CLI subcommands are NOT wired, but the subcommands ARE wired (verified above — `pushfold` and `river` work; `parity` is wired but too slow at the documented `--iters 2000`). The README's Known-issues entry is stale relative to v1.7.0; USAGE §7a is accurate.

11. **The `.dmg` references conflict across docs.**
    - README "macOS install (.dmg, experimental)" (L28-32) points to `docs/dmg_install_guide.md` for the v1.6.0 .dmg.
    - README Known Issues (L200-210) discusses the v1.4.0 .dmg failure ("ModuleNotFoundError: No module named 'nicegui'").
    - `RELEASE_NOTES_2026-05-23.md` L130-132 says "No `.dmg` installer for v1.4.1 or later. v1.4.0's universal2 `.dmg` is the latest packaged installer."
    - `docs/dmg_install_guide.md` is written for v1.6.0 (arm64-only, 45 MB, with a stated SHA256).
    These three docs disagree on which `.dmg` is current. Reader is likely to be confused.

## Recommendations before any doc commit/push

1. **Fix `Range("...")` examples — high priority, doc-breaking.** Either:
   - Change all doc examples to `parse_range("AA, KK, AKs")`, OR
   - Update `Range.__init__` to accept a string and auto-call `parse_range` internally (preferred — keeps the doc-friendly form working).
   
   Locations to update if going the doc route:
   - `README.md` L127
   - `docs/README_proposed_update_2026-05-23.md` L144
   - `USAGE.md` Range.diff example at §5.5 implicitly (write an explicit example using `parse_range`)

2. **Fix `solve_range_vs_range_rust(..., iters=...)` to `iterations=`** in:
   - `README.md` L130
   - `docs/README_proposed_update_2026-05-23.md` L149

3. **Fix the `--hero AhKh` overlap in `USAGE.md` §7a L669-670.** Use a hero like `AdQd` (or any non-overlapping combo) for the example.

4. **Replace placeholder lock-key examples** in README L121 and USAGE §5.3 with a real infoset key, or with an explicit comment ("the lock dict will silently no-op if the key doesn't match any infoset; see `tests/test_node_locking.py` for the canonical key format").

5. **Update README L121 to use `solve_hunl_postflop` on a river fixture** (as USAGE §5.3 does), since `solve(HUNLPoker(HUNLConfig(starting_stack=10000)))` defaults to the preflop full-tree path that raises `NotImplementedError`.

6. **Remove the stale "CLI ergonomic gaps" Known-issues entry from `README.md` L234-237.** The pushfold / river / parity CLI subcommands ARE shipped in v1.7.0. The entry contradicts the rest of the README's v1.7.0 claims. Move any residual caveat (parity binary prerequisite; river perf at high `--iters`) into a v1.7.0-aware paragraph.

7. **Add a perf caveat to `USAGE.md` §5.4** mirroring §5.1, OR change the §5.4 example to a turn-start board with explicit fast-path settings. The current §5.4 doesn't complete with the literal call `solve_hunl_postflop(cfg, iterations=500)` on a flop, even with fixed hole cards.

8. **Reconcile the `.dmg` story across `README.md`, `RELEASE_NOTES_2026-05-23.md`, and `docs/dmg_install_guide.md`.** Pick a single source of truth — either "v1.6.0 .dmg shipped" (per dmg_install_guide) or "v1.4.0 is the latest" (per RELEASE_NOTES L131-132) — and update the other two to match. The README's "experimental" framing leaves it ambiguous.

9. **Environment hardening for the user's local install.** Before committing user-facing docs, the user should re-run `pip install -e .` from `/Users/ashen/Desktop/poker_solver` to fix the dangling editable-install pointer (`/private/tmp/w2.3-retest-4234`). Otherwise the doc readers' first invocation of `poker-solver` will fail with `ModuleNotFoundError`. (The user explicitly excluded this from the verification task, but it WILL block any reader following the docs verbatim.)

10. **Parity command perf caveat in USAGE §7a.** `poker-solver parity --fixture dry_K72_rainbow --iters 2000` does not complete in reasonable wall-clock (>60s at 50 iters per the pytest timeout; the literal 2000 figure is several minutes). Add an honest perf note matching §5.1's tone, OR reduce the documented `--iters` default to a value that completes in <60s on a typical machine.

## Verification status summary

- **22 PASS** (with reduced iteration counts where noted)
- **5 FAIL** with concrete fixes proposed (3 distinct bugs: Range constructor, `iters` kwarg, river hero overlap; 2 of these appear in both production and proposed READMEs)
- **6 SKIP-LONG** (chance-enum-at-root perf cliffs, all already caveated in the docs themselves)
- **9 SKIP-DANGEROUS** (per task hard constraints — UI, .dmg, network installers)

**Verdict for doc commit:** **HOLD.** The three Range/iters/hero-overlap bugs must be fixed before any user-facing doc lands on origin. The dangling editable-install pointer is a separate environment issue the user should resolve out-of-band. The .dmg cross-doc story should also be reconciled, but is lower priority than the executable-command bugs.
