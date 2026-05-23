# PR 4.5 commit message draft

**Status:** PRE-STAGED. Do NOT commit until 3-agent fan-out returns +
audit verdict is READY per `docs/pr4_5_audit_debt/audit_prompt_final.md`.
Final commit hash recorded by orchestrator in `docs/autonomous_log.md` §
post-merge entry.

**Version bump:** PATCH `0.5.1 -> 0.5.2`. Mechanical-only sweep with no
behavior change, no new public-API surface, no breaking change. The new
`max_boards_per_street` kwarg in `precompute.py` (4-D) is opt-in sentinel
with default behavior preserved -> backward-compatible -> PATCH per
SemVer. `PushFoldChartUnavailable(ValueError)` (3.5-A) is base-class
widening, also backward-compatible. If a higher-numbered PR ships
between this draft and PR 4.5 fire, increment from that tip instead.

**Pass via HEREDOC (zsh-safe).** Do NOT use `-m "..."` directly.

---

```sh
git commit -m "$(cat <<'EOF'
PR 4.5: Audit-debt sweep (mechanical fixes across PR 3/3.5/4/5) (v0.5.2)

Bundles 13 should-fix / nice-to-fix items from the PR 3 / 3.5 / 4 / 5
audit reports into one cleanup PR. No behavior changes; no spec
amendments; no new tests. Mechanical-only scope per
docs/pr4_5_audit_debt/launch_kickoff.md sec 2 (locked 13-item list).
Three-agent fan-out (A: PR 3/3.5 mechanical; B: PR 4 mechanical;
C: PR 5 mechanical). Audit verdict READY per
docs/pr4_5_audit_debt/audit_report.md.

Bumps __version__ 0.5.1 -> 0.5.2 (PATCH) per SemVer: backward-compatible
fixes only. New max_boards_per_street kwarg on precompute (4-D) is
opt-in sentinel with default behavior preserved; PushFoldChartUnavailable
now subclasses ValueError (3.5-A), backward-compatible for existing
`except PushFoldChartUnavailable` consumers (consumer-grep verified clean
per audit). poker_solver/__init__.py + pyproject.toml [project] version
bumped together; CHANGELOG.md gets a [0.5.2] - 2026-05-22 section above
[0.5.1] with the 13-item delta.

Items landed (cross-ref docs/pr4_5_audit_debt/launch_kickoff.md sec 2):

PR 3 / 3.5 (Agent A; +19 / -3 across hunl.py, action_abstraction.py,
pushfold.py):
- 3-A: License-posture header on poker_solver/hunl.py (+4 LOC; no
  third-party derivation; original implementation).
- 3-B: License-posture header on poker_solver/action_abstraction.py
  (+4 LOC).
- 3-E: Mark enumerate_legal_actions stack<=0 branch unreachable
  (action_abstraction.py; +3 LOC).
- 3.5 docs: pushfold.py documentation/header tightening (+8 LOC).
- Misc unreachable-branch annotation on hunl.py (+3 LOC).

PR 4 (Agent B; +39 / -7 across equity_features.py, emd_clustering.py,
precompute.py, hunl.py):
- 4-A: License-posture header on abstraction/equity_features.py
  (+3 LOC; no third-party derivation; equity feature is original).
- 4-B: Tighten SHOWDOWN predicate at hunl.py:326 from
  `state.street >= Street.FLOP` to explicit FLOP/TURN/RIVER membership
  (+5 LOC). Latent fix; solver's _is_terminal guard masks it currently.
- 4-C: Mark _kmeans_plusplus_init empty-cluster fallback unreachable
  (emd_clustering.py; +7 LOC); n < K branch already handled upstream.
- 4-D: Surface mc_iterations < 5000 autosize trigger as explicit kwarg
  (precompute.py; +24 LOC: named constants + sentinel value).
  max_boards_per_street=None (autosize) / -1 (no cap) / int>0
  (fixed cap). Surface-only; internal 5000 threshold unchanged.

PR 5 (Agent C; +13 / -4 in profiler/memory.py):
- 5-A: Drop unused numpy import + `_ = np` suppression and replace
  literal byte/iteration constants with named constants
  (profiler/memory.py; +9 named consts, +4 net delta).

Out of scope (deferred per launch_kickoff.md sec 3):
- K-means quality tuning (post-PR-6; Rust port enables full enumeration).
- save_abstraction byte-determinism design (no current consumer).
- 6 skip-marked PR 5 TURN tests (PR 6 Rust lookup_bucket resolves).
- 5-M1 lossless-flop exploitability hang (lands as part of PR 5).
- PR 3.5 sec 6 must-fixes 1-5 (already landed in commit 1cbf52a).
- Spec-amendment items (HUNLState.config source-of-truth; d=2 jam
  landmark; strategic-equivalence collapse).
- _canonicalize rename, CLI integration items, test coverage adds.

Cross-agent file ownership (per launch_kickoff.md sec 5a):
- Agent A: hunl.py (license header + unreachable annotation),
  action_abstraction.py (license header + unreachable annotation),
  pushfold.py (docs).
- Agent B: hunl.py:326 SHOWDOWN predicate only,
  abstraction/equity_features.py, abstraction/emd_clustering.py,
  abstraction/precompute.py.
- Agent C: profiler/memory.py.
Line ranges on hunl.py do not overlap (Agent A: header + low-line
unreachable; Agent B: :326 only); git auto-merged trivially.
No manual conflict-resolution commits on the branch (verified per
audit cross-agent-file-ownership section).

Verification:
- pytest -x -q: ~210/~210 pass + ~10 skip + 1 xfail + 0 fail.
  Test count + skip count match pre-PR-4.5 baseline; only the rake-
  config test exception-type swap (3-C consequence) differs.
- mypy --strict poker_solver/: clean. Import drops (3-D field, 5-A np)
  pre-grepped per launch_kickoff.md sec 8e; no symbol leak.
- ruff check + ruff format + black --check: clean.
- License attribution headers verified on the 3 modules (3-A, 3-B,
  4-A); wording normalized by aggregator per launch_kickoff.md sec 8d.
- check_pr.sh license audit: clean; no new AGPL/GPL deps.
- Unreachable asserts (3-E, 4-C) do not trip in CI; full pytest pass.
- 3.5-A consumer-grep clean; no `except PushFoldChartUnavailable`
  consumer relies on `not isinstance(e, ValueError)`.
- Diff stat: ~7-8 source files; net LOC delta ~+88 / -32
  (addition-heavy: 3 license-posture headers + named-constant
  expansions in precompute.py and profiler/memory.py + sentinel
  kwarg surface + unreachable-branch annotations).

Branch: pr-4.5-audit-debt-sweep (off integration tip post-PR-6).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Hand-off notes for orchestrator

1. **Replace `[N/N]` style stubs only if the audit-agent report fills them.**
   The figures above (~210 pass, 7 source files, <50 LoC delta) are the
   `launch_kickoff.md` expectations; audit-report numbers override at fire.
2. **Version-bump location reminders:** `poker_solver/__init__.py:1`
   (`__version__`); `pyproject.toml [project] version`; `CHANGELOG.md`
   (new `[0.5.2] - 2026-05-22` section above `[0.5.1]`); `README.md`
   ("Current version: 0.5.1" -> "Current version: 0.5.2"). All 4 files
   bumped together in this same commit per PR 6's release-bundle pattern
   (`docs/pr6_prep/commit_message_draft.md`).
3. **Stage explicit paths** per `launch_kickoff.md` sec 9c. Do NOT use
   `git add -A` / `git add .`. Expected staged set: 7 modified
   `poker_solver/...` files + version-bump trio + CHANGELOG +
   `docs/pr4_5_audit_debt/audit_report.md` + possibly 1-2 test files
   (rake-config exception swap, `test_infoset_key_*` if 4-B surfaces it).
4. **DO NOT amend.** If pre-commit hook fails, fix-stage-new-commit per
   global git safety protocol; never `git commit --amend` here.
5. **Reflog backup** captured at `/tmp/integration_pre_pr_4_5.hash` per
   pre-flight gate `launch_kickoff.md` sec 6e.
