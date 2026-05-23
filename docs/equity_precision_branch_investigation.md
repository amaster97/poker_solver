# `origin/equity-precision` Branch Investigation

**Date:** 2026-05-22
**Triggered by:** PLAN.md §6 entry — orchestrator had not seen this remote branch before.
**Investigator:** read-only git inspection (no push, no delete).

---

## 1. Commits on the branch

`git log origin/equity-precision -10 --oneline`:

```
01475e8 Equity: hybrid exact-enum + MC, tighter precision default
17c9756 PR 2: Leduc poker (Python + Rust) + Game trait abstraction
3425da8 Slim down public repo: untrack PLAN.md and docs/
9d2d66a PR 1: Two-tier CFR foundation (Python + Rust)
023956e Initial commit: Texas Hold'em equity solver
```

Total: 5 commits. Tip = `01475e8` ("Equity: hybrid exact-enum + MC, tighter precision default") authored by `amaster97 <amaster1997@gmail.com>` on 2026-05-21 01:36:47 -0400.

**Commits unique to `origin/equity-precision`** (`git log --oneline origin/equity-precision ^main ^integration`):

```
01475e8 Equity: hybrid exact-enum + MC, tighter precision default
```

Only one commit is unique by SHA. Everything else is shared with main.

---

## 2. Diff vs main

`git diff main..origin/equity-precision --stat` → **empty output**.
`git diff main..origin/equity-precision -- pyproject.toml poker_solver/equity.py` → **empty output**.

The tree at `origin/equity-precision` tip is byte-identical to `main` tip's tree for the equity files (and everything else). In other words: the only difference between this branch and main is which SHA carries the equity hybrid changes.

- `origin/equity-precision` carries it on **`01475e8`** (original direct commit, dated 01:36:47).
- `main` carries it on **`2b67370`** (squash-merge of PR #1, dated 01:39:21, ~3 min later).

Both commits share the same parent `17c9756` (PR 2 Leduc). Confirmed via `git rev-parse origin/equity-precision^` == `git rev-parse 2b67370^` == `17c9756b...`.

---

## 3. Diff vs integration

`git diff integration..origin/equity-precision --stat` shows **30 files, +66 / -9876** — but every change is a *deletion* against integration: PR 3, PR 3.5, PR 4 work (HUNL tree, push/fold, card abstraction, charts, scripts, tests).

`git log integration ^origin/equity-precision --oneline` shows exactly those PRs:

```
5832b2f Integration: merge PR 4 (card abstraction)
f67bfa3 Integration: merge PR 3.5 audit follow-up (1cbf52a)
6565b84 PR 4: Card abstraction pipeline (EMD bucketing, 256/128/64, suit-iso)
1cbf52a PR 3.5 audit follow-up: API completeness + spec amendments
fd0a2c7 Integration: merge PR 3.5 (push/fold + v0.3 capstone)
9f91c83 PR 3.5 + v0.3 capstone: push/fold mode (2-15 BB) + project meta
351cbee Integration: merge PR 3 (rebased on equity-hybrid main)
a96675c PR 3: HUNL tree builder + action abstraction (Python tier)
2b67370 Equity: hybrid exact-enum + MC, tighter precision default (#1)
```

Conclusion: `origin/equity-precision` is **stale** relative to integration — it predates PR 3, 3.5, and 4 (everything since the equity hybrid). It contributes nothing that integration lacks.

---

## 4. Is it merged into main?

**Git ancestry check:**

- `git merge-base --is-ancestor origin/equity-precision main` → **NOT an ancestor** (because main rewrote the SHA via squash).
- `git merge-base --is-ancestor origin/equity-precision integration` → **NOT an ancestor** (same reason).

**Content-equivalence check:**

- `git diff main..origin/equity-precision --stat` is empty.
- `git diff origin/equity-precision..2b67370 --stat` is empty.
- Parents match (`17c9756`).

**Verdict:** **Effectively merged.** The branch is a content-identical sibling of `main`'s PR #1 squash-merge commit. Standard squash-merge artifact — original feature branch's tip SHA never becomes a direct ancestor of main, but every change it carries is already in main and integration.

---

## 5. Recommended action

**Delete `origin/equity-precision`** (pending user approval).

Reasoning:
- Zero unique content vs main / integration (diff stat is empty against main).
- Stale by ~5 days; missing PR 3, 3.5, and 4 work; would never be reused.
- Original commit `01475e8` is preserved in reflog if ever needed for forensic reference; the squashed `2b67370` on main carries identical changes with a cleaner message and PR linkage.
- Hypothesis in the task brief confirmed: this is the pre-merge development branch for the equity hybrid (PR #1).

**Suggested command (requires user approval, NOT executed here):**

```bash
git push origin --delete equity-precision
```

**Alternative (lighter touch):** leave it alone — it costs nothing on the remote and could be useful as a historical pointer to the un-squashed commit. The PR brief authored by user prefers tidy branches, so deletion is the default recommendation.

**Do NOT merge anything from it.** There is nothing to merge: every file at `origin/equity-precision` tip already exists at `main` tip with identical content.

---

## Load-bearing facts not on main/integration

None. The only SHA unique to this branch is `01475e8`, and its tree is byte-identical to `2b67370` already on main.
