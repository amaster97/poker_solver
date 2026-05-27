# W2.3 Post-v1.8 Persona Retest — Sarah Deep-Stack Turn Postflop (Nash)

- **Date:** 2026-05-26
- **Author:** orchestrator retest fire (post-v1.8 SIMD-merge wave)
- **Trigger:** memory rule `feedback_post_ship_persona_retest` + pre-staged prompt at
  `docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md`
- **Hard cap (per user constraint):** 10 min wall-clock, SKIP-LONG on breach
- **Verdict:** **BLOCKED — SKIP-LONG (timeout-breach)**
- **Type classification (per `feedback_persona_test_rectification`):** **Type D (perf)** — same family as v1.7.0
- **W2.3 status delta vs `persona_test_status_2026-05-25.md`:** **NO CHANGE — remains BLOCKED**

---

## TL;DR

Pre-staged W2.3 retest fired against current `origin/main` (HEAD `bf645ae`). The Python package
under `.venv/` reports `poker_solver.__version__ == 1.7.0` — i.e. the v1.8 SIMD-wiring work merged
on `main` did **not** result in a version bump (no `v1.8.0` tag, `pyproject.toml` and
`poker_solver/__init__.py` both still pinned at `1.7.0`). The retest exercised the version on disk
(editable install via `.venv/lib/.../poker_solver.pth`).

The retest crunched at ~100 % CPU on a single core for **~654 s** without ever emitting a single
`on_progress` callback, then was hard-killed by SIGTERM at the 10-min user-imposed cap (the
in-process SIGALRM at 600 s did not deliver — the Python signal handler was masked while the
Rust extension held CPU in `_rust` / `dcfr_vector`). No `result` object was produced, so all
strategy / exploit / KK-defend / agreement assertions are **NOT MEASURED**.

This is consistent with `docs/v1_8_simd_perf_benchmark_2026-05-26.md`, which found the v1.8 SIMD
work delivered **~1.0× speedup** vs v1.7.0 on the workloads that matter (rather than the 4-8×
projected by the implementation roadmap). The pre-staged prompt's "PASS expected on M-series"
assumption was predicated on the 4-8× projection; with the empirically-locked ~1.0× delta,
W2.3's binding perf wall is unchanged.

---

## Pre-staged prompt summary

Source: `docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md`

- **Workflow:** W2.3 Sarah "Solve a 200 BB deep-stack postflop spot." Retest uses **turn** (not flop;
  flop reserved for v1.9 candidate per `v1_8_decision_brief.md:26`). Pre-v1.8 8-class / 500-iter
  turn Nash > 10 min (Type D vs Sarah 5-min budget per `v1_8_decision_brief.md:16`).
- **v1.8 SIMD projection (NEON / SSE4.2 / AVX2):** 4-8× speedup → 75-150 s on M-series.
- **PASS thresholds (all of):** completes, wall ≤ 5 min, `backend == "rust_vector"`,
  Layer-3 p75 exploitability < 0.6, top-action agreement ≥ 60 %, KK defend ≥ 0.95,
  row-sums 1.0 ± 1e-6, no NaN/inf.
- **PARTIAL ladder:** wall 5-8 min → v1.8.x perf followup.
- **FAIL / Type D:** wall > 8 min, KK defend < 0.95, top-action agreement < 50 %, Layer-3 p75 ≥ 1.0,
  NaN/inf, exception. Type D explicitly routes "v1.8 SIMD claim NOT delivered. SURFACE, HALT,
  perf diagnostic, hold release narrative."
- **Fixture:** turn `Qs 7h 2d 5c`, 200 BB (`starting_stack=20000`), pot=2000,
  `initial_contributions=(1000,1000)`, `bet_size_fractions=(0.5,1.0)`,
  `postflop_raise_cap=3`, `include_all_in=False`, 8 classes (KK, QQ, JJ, TT, 99, AQs, KQs, QJs),
  `iterations=500`, `hero_player=1`, `compute_exploitability_at_end=True`.

---

## Pre-condition checks

| Check | Expected | Observed | Pass |
|---|---|---|---|
| Host arch | arm64 (M-series) | `arm64` (`uname -m`) | YES |
| `_rust.cpython-313-darwin.so` arch | arm64 (no x86_64-on-arm64 silent skip) | `Mach-O 64-bit dynamically linked shared library arm64` (`file …_rust.so`) | YES |
| Python | `.venv/bin/python` (per `feedback_dotso_arch_check`) | `Python 3.13.1` | YES |
| `poker_solver.__version__` | `1.8.0` per prompt | **`1.7.0`** — see Caveats §1 | NO |
| `git log main` HEAD | post-v1.8 wave | `bf645ae` ("docs: v1.8 release notes honesty (~1.0x not 4-8x) + W3.2 BR smoke (#56)") | YES |
| `git tag` for v1.8 | `v1.8.0` present | **absent** — latest tag is `v1.7.0` | NO |
| `solve_range_vs_range_nash` importable | YES | YES (`poker_solver/range_aggregator.py`) | YES |

---

## Retest invocation

Read-only. No source / fixture / test edits. Driver inlined via `python - <<'PYEOF'` (no `/tmp/`
script file per session policy). Hard cap = 10 min via two independent mechanisms:

1. **In-process SIGALRM** (`signal.alarm(600)`) — soft cap, breaks at next Python opcode.
2. **External SIGTERM** at the 10-min boundary — hard kill, guaranteed.

```python
# Excerpt — full driver in transcript
import signal
def _alarm_handler(signum, frame):
    raise TimeoutError("HARD-CAP 600s exceeded (per user constraint)")
signal.signal(signal.SIGALRM, _alarm_handler)
signal.alarm(600)

from poker_solver import Card, HUNLConfig, Street, solve_range_vs_range_nash
cfg = HUNLConfig(
    starting_stack=20000, small_blind=50, big_blind=100, ante=0,
    starting_street=Street.TURN,
    initial_board=tuple(Card.from_str(c) for c in ("Qs","7h","2d","5c")),
    initial_pot=2000, initial_contributions=(1000,1000),
    initial_hole_cards=(), postflop_raise_cap=3,
    bet_size_fractions=(0.5,1.0), include_all_in=False,
)
classes = ["KK","QQ","JJ","TT","99","AQs","KQs","QJs"]
result = solve_range_vs_range_nash(
    cfg, hero_range=classes, villain_range=classes,
    iterations=500, hero_player=1,
    compute_exploitability_at_end=True, on_progress=progress,
)
```

Background launch (per harness): `.venv/bin/python - <<PYEOF | tee /tmp/w23_v18_retest_output.log`
(stdout-only; tee captured everything that reached fd 1).

---

## Observed output (captured)

```
poker_solver.__version__ = 1.7.0
FIXTURE: turn Qs7h2d5c, 200 BB, classes=['KK', 'QQ', 'JJ', 'TT', '99', 'AQs', 'KQs', 'QJs'], iters=500, hero_player=1
```

That is the complete captured stdout. After the fixture banner, the process entered the Rust
`solve_range_vs_range_nash` call and emitted **zero** further lines:

- No `progress: iter=N/500` callbacks (the progress callback was wired and would have fired every
  5 s if invoked; it never was).
- No exception traceback.
- No `=== RESULT ===` banner.

External monitoring:

| t (s) | Process state | Notes |
|---|---|---|
| 0 | fork + import | Python PID 57950 spawned by zsh PID 57948 |
| ~1-5 | imports + cfg construction | banner emitted |
| 5 - 654 | **100.0 % CPU one core** | `ps`: `99.6%`, then `100.0%` |
| 600 | SIGALRM scheduled to fire | **did not deliver** — Python signal handler masked while Rust holds CPU below GIL |
| 654 | external SIGTERM | `kill -TERM 57950`; process reaped |

**Wall-clock at kill: ~654 s (10 min 54 s).** No completion.

---

## Verdict

**SKIP-LONG / BLOCKED — Type D (perf timeout).** Identical failure mode to W2.3 post-v1.7.0
(`docs/persona_test_results/W2_3_post_v1_7_0_result.md`): solve exceeded budget, no `on_progress`
flush, KK-defend / exploitability / agreement **NOT MEASURED**.

Per the pre-staged prompt's classification routing:
> **Type D.** Wall-clock > 8 min — v1.8 SIMD claim NOT delivered. SURFACE, HALT, perf diagnostic,
> hold release narrative. Headline-validation failure mode.

The relevant headline is already revised in `docs/v1_8_simd_perf_benchmark_2026-05-26.md` and PR #56
(`bf645ae`, "docs: v1.8 release notes honesty (~1.0x not 4-8x)") — i.e. the "SURFACE, HALT, revise
narrative" step is already done by the bench wave; this retest **confirms downstream** that the
~1.0× SIMD reality also means the W2.3 unblock claim is not delivered.

---

## Comparison to `persona_test_status_2026-05-25.md` snapshot

| Item | 2026-05-25 snapshot | 2026-05-26 retest | Delta |
|---|---|---|---|
| W2.3 verdict | **BLOCKED** (v1.7.0 PARTIAL-TIMEOUT; "v1.8.0 retest pre-staged") | **BLOCKED** (post-v1.8 SKIP-LONG) | none |
| W2.3 blocker text | "4-class iter=100 flop aggregator >300 s on 200 BB deep stack. Awaits v1.8 SIMD ship — projected 75-150 s on M-series." | "8-class iter=500 turn Nash >654 s on 200 BB deep stack. v1.8 SIMD merged; measured speedup ~1.0× (per `v1_8_simd_perf_benchmark_2026-05-26.md`); turn fixture still > 10 min." | revised |
| Projected end-state row for W2.3 | "v1.8 SIMD (4-8× per `v1_8_decision_brief.md`) projected to bring flop solve into Sarah's 5 min budget" | **invalidated** — empirical SIMD delta is ~1.0×, not 4-8× | invalidated |
| Aggregate count | 4 BLOCKED (W2.3, W3.2, W3.4) | 4 BLOCKED (same set; W3.4 retest pending) | none |

**W2.3 stays BLOCKED.** The pre-staged retest's "PASS expected on M-series" was conditional on the
roadmap's 4-8× SIMD projection; that projection is now empirically refuted at ~1.0×, so the
expected verdict shifts to Type D in lockstep with the SIMD-bench finding.

---

## Why SIGALRM didn't fire

Python's `signal.alarm()` schedules SIGALRM delivery, but the handler can only execute between
Python opcodes. While `solve_range_vs_range_nash` is inside the Rust `_rust` extension (which
releases the GIL but does not periodically yield back to the Python signal-handling loop), the
queued signal cannot run. SIGALRM was delivered to the kernel at 600 s but the Python interpreter
never got a chance to run its handler — and so the `TimeoutError` raise never executed.

This is a known hazard for long-running Rust-bound calls and is the root cause behind the
`feedback_post_ship_persona_retest` recommendation to wire `on_progress` callbacks for any solve
that may exceed budget: the callback path is the **only** way Python regains control mid-solve.
The v1.8 vector-CFR path appears to **not invoke** the `on_progress` callback during the inner
loop — at least not on this fixture — which means a stuck solve is invisible until external kill.
See "Recommendation §2" for follow-up.

---

## Caveats

1. **Version banner says 1.7.0, not 1.8.0.** Source `pyproject.toml` and `poker_solver/__init__.py`
   are still pinned at `1.7.0`. `git tag` shows no `v1.8.0` tag (latest is `v1.7.0`). However, the
   SIMD wiring work (PR 32 phases 1-3 per `v1_8_simd_perf_benchmark_2026-05-26.md`) is **merged on
   `main`** (HEAD `bf645ae`), so the editable `.venv` install does exercise the v1.8 SIMD code
   path despite the unchanged version string. This is a **version-bump-pending** state, not a
   "wrong code" state — the SIMD work is loaded; the bump is just deferred until the
   release-notes-honesty wave (PR #56) lands and the actual ship decision is made. For the
   purposes of this retest, the answer "does the v1.8 wiring deliver W2.3 unblock on M-series?"
   is empirically **no**, regardless of the version-string state.

2. **No mid-solve progress visibility.** Driver wired `on_progress` but received zero callbacks
   in 654 s. Cannot distinguish "converging-but-slow" from "stuck mid-iteration" from
   "stuck in setup before iteration 1." Same caveat as W2.3 v1.7.0 retest (`W2_3_post_v1_7_0_result.md` §"Caveats §1").

3. **Single hardware sample.** Measured on M4 Pro arm64 (per `v1_8_simd_perf_benchmark_2026-05-26.md`
   §Hardware). M1/M2/M3 behavior unmeasured; x86_64 (AVX2) entirely unmeasured.

4. **Iteration count = 500, not 5000.** The prompt called for `iterations=500`. The SIMD bench's
   per-iter timing on a smaller fixture (1081-hand river, 3-5 actions, 5 iters → 936-4777 ms/iter)
   suggests the 8-class turn fixture would be substantially heavier per iter; 500 iters at that
   per-iter cost trivially exceeds the 5-min Sarah budget even at the SIMD's optimistic projection.
   The kill at 654 s is consistent with this.

5. **No source / fixture / test edits.** Read-only retest. No commits, no pushes. Driver was
   inlined in the bash heredoc; no scratch files were retained in the working directory.

---

## Recommendation

1. **Surface as Type D + record W2.3 perf-wall as unchanged.** Update `persona_test_status_2026-05-25.md`
   (or its 2026-05-26 successor) to reflect that the post-v1.8 retest empirically holds W2.3 at
   BLOCKED. The "Projected end-state" row for W2.3 ("v1.8 SIMD projected to bring flop into 5 min")
   is invalidated by `docs/v1_8_simd_perf_benchmark_2026-05-26.md` + this retest; either drop it
   or rewrite to reflect that the next perf lever is **not** SIMD (autovectorizer already covers
   the small-slice case).

2. **Wire `on_progress` invocation inside `dcfr_vector` inner loop.** The current behavior
   (zero callbacks over 654 s) makes long-running solves un-killable by SIGALRM and un-diagnosable
   by progress streaming. A periodic `on_progress(iter, total, "in-iter")` callback every N iters
   (e.g. N=5) would (a) let SIGALRM fire, (b) let users see "still converging" vs "stuck", and
   (c) let the timeout watchdog work. Type C-USEFUL Rust+Python change — not a code fix here
   (read-only retest), but the right next-perf-followup deliverable.

3. **Do NOT re-fire W2.3 against the same fixture on v1.8.x without a real perf delta.**
   The SIMD bench locked the perf-delta at ~1.0×. Re-running the same fixture will yield the
   same SKIP-LONG. Next legitimate W2.3 retest trigger should be:
   - v1.9+ with a measured ≥3× speedup on the `dcfr_vector` path, OR
   - a smaller-fixture variant (e.g. 4-class instead of 8-class) that **acknowledges scope-down**
     and routes to the "PARTIAL-RIVER-ENVELOPE / FLOP-BLOCKED" framing already in use for W2.1.

4. **No release-narrative impact.** PR #56 already lands the honesty correction
   ("docs: v1.8 release notes honesty (~1.0x not 4-8x)"); this retest is downstream confirmation
   that the honest reframing is correct. No additional surface action required beyond the
   updated status snapshot.

---

## Files referenced

- `docs/persona_test_results/post_v1_8_0_W2_3_retest_prompt.md` — pre-staged brief
- `docs/persona_test_results/W2_3_post_v1_7_0_result.md` — v1.7.0 PARTIAL-TIMEOUT precedent
- `docs/persona_test_status_2026-05-25.md` — pre-retest snapshot
- `docs/v1_8_simd_perf_benchmark_2026-05-26.md` — ~1.0× speedup measurement
- `docs/v1_8_decision_brief.md` — 4-8× projection (now refuted)
- `poker_solver/range_aggregator.py` — `solve_range_vs_range_nash` entrypoint
- `poker_solver/_rust.cpython-313-darwin.so` — arm64 native binding (verified)
- `pyproject.toml`, `poker_solver/__init__.py` — both pinned `version = "1.7.0"` (no v1.8 bump yet)
- `/tmp/w23_v18_retest_output.log` — captured stdout (2-line banner only; transient)

## No source changes

Read-only retest. No edits to `poker_solver/`, `tests/`, `scripts/`, `docs/pr13_prep/`, or any
fixture. Driver heredoc was inlined in the transcript (not retained as a file). Only artifact
written: this report.
