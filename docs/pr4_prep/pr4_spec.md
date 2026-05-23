# PR 4 spec — card abstraction pipeline (EMD bucketing, Python tier)

**Updated 2026-05-21 per consistency review:** (a) §6 amended with a forward-looking declaration: `HUNLConfig.abstraction` is typed as `Optional[AbstractionRef]` (not `Optional[AbstractionTables]`), where `AbstractionRef = (source_path: str, version: str)` is a small dataclass declared alongside `AbstractionTables`. Rationale: PR 6's Rust loader needs only the path across the PyO3 boundary, not the full in-memory table object — declaring this in PR 4 avoids retroactive schema churn (resolves blocker B2 from `docs/spec_consistency_review.md`). (b) §4 Stage 5 clarifies that the `.npz` file's `metadata` is a single nested dict (NOT separate top-level NumPy arrays per metadata field). PR 6's Rust loader un-nests on load (resolves blocker B1). PR 4 stays authoritative on the writer side — `metadata` dict is serialized via `json.dumps(metadata).encode()` into a one-element `bytes_` array inside the `.npz` to keep numpy-native writing simple.

## 1. Goal

Ship the **card abstraction pipeline** that maps every (board, hole-card) pair on each postflop street to a small bucket id, so the HUNL tree from PR 3 can be solved within the 16 GB MacBook budget in PR 5. Target abstraction (per locked PLAN.md): **256 flop / 128 turn / 64 river buckets per side**, computed via **imperfect-recall, EMD-clustered equity-distribution features**, persisted to a single on-disk artifact (default `abstraction_v1.npz`), and plumbed behind the existing `HUNLPoker.infoset_key` interface as an optional layer (lossless when no bucket file is loaded; bucketed when one is). PR 4 ships the pipeline + the lookup + persistence + CLI tool to build it; PR 5 consumes it.

## 2. What PR 4 does NOT do

- **No lossless cards.** Lossless-hand mode (postflop-solver / noambrown convention) is **explicitly deferred to PR 5+**, gated on the per-street memory profiler that PR 5 ships. Per PLAN.md "Card abstraction (v1 locked)": *"PR 5 ships a memory profiler; revisit per-street based on data."* PR 4 does not pre-empt that revisit.
- **No neural-network embeddings (Deep CFR-style).** Deep CFR is a v2+ path (PR 13 candidate). PR 4 stays tabular.
- **No per-board precomputes** in the postflop-solver sense (`hand_strength` tables keyed by `card_pair_to_index(turn, river)`, `valid_indices_*`, isomorphism swap-lists). Those live in PR 5 / PR 6 as part of the Rust solver. PR 4 only builds the *abstraction* artifact — the bucket lookup table — not the per-board strength/blocker scaffolding.
- **No Rust port.** PR 4 is Python-tier only. PR 6 ports the lookup (the artifact is portable; the build pipeline does not need to be).
- **No OCHS, no EHS² bucketing variant.** v1 uses one feature design: equity-distribution histograms against a uniform random opponent over all reachable runouts. OCHS (Opponent Cluster Hand Strength) and bucketing on hand-strength-squared are explicitly out-of-scope; the file structure is laid out so a future PR can add them as alternate feature modules.
- **No abstraction-quality benchmarking against PioSolver outputs.** That's a PR 7-ish task (the river diff-test vs `noambrown_poker_solver` lands in PR 7). PR 4 ships unit-level correctness only: known-equity sanity checks and bucket-shape invariants.
- **No preflop bucketing.** Preflop has 169 strategically-unique starting hands; we do **not** cluster preflop and PR 4's lookup table only covers flop/turn/river. Preflop infosets stay lossless; PR 9 (preflop solver) will decide whether further compression is needed.
- **No incremental retraining.** Abstraction is built once via the CLI tool and persisted; we never partially re-cluster at solve time. If the user wants different bucket counts they rebuild the file.
- **No rake / variance considerations** in the features. We compute pure equity vs uniform random; PR 9 may layer in different opponent ranges if needed.
- **No imperfect-recall transitions network.** Some 2003-era abstractions stored an n×n transition matrix between buckets across streets (`gto_poker_survey_2024.pdf` page 5: "transition probabilities represent the likelihood of moving from one bucket to another"). PR 4 only stores per-street bucket assignments. The transition matrix is not needed for tabular CFR — the tree already encodes street transitions via chance nodes.

## 3. Conceptual architecture

### 3.1 Imperfect recall

A bucket label is the player's **only memory of card history**. On the turn, the player does not remember which flop bucket the hand belonged to; the turn bucket id is computed fresh from (turn-board, hole-cards). This means strategy decisions on later streets cannot condition on the bucket trajectory — only on the current street's bucket. This is the standard imperfect-recall abstraction (Libratus blueprint per `references/papers/libratus_brown_2017_science.pdf`: "imperfect-recall card abstraction with 2.5M flop buckets and 1.25M turn buckets"). We use much smaller bucket counts (256/128/64) because our action menu is wider (6 sizes vs Libratus's coarser early abstraction); the per-PR-5 memory profiler will tell us if we can grow these.

### 3.2 Per-street independent clustering

Three independent clusterings (flop, turn, river). Each maps a `(board, hole_cards)` instance to a bucket id in `[0, K_street)`. The clusterings are **not** required to be hierarchically nested (i.e., it is not the case that "flop bucket 5" deterministically transitions to a subset of turn buckets). This is what "imperfect recall" buys: each street's clustering is solved in isolation, on its own feature space.

### 3.3 EMD distance + k-means clustering

For each hand on a given street, we build a **feature vector** = the histogram of the hand's equity against a uniform-random opponent, integrated over all future board runouts. Two hands are "close" if their equity distributions look similar in shape (not just mean). The right distance for histograms-of-probability is **Earth Mover's Distance** (EMD), also called Wasserstein-1 distance. EMD-clustered k-means is the canonical card-abstraction technique referenced across:

- `references/papers/gto_poker_survey_2024.pdf` (Section 3.2): "hand strength and the hand's potential to improve... up to 7 buckets per player per round was common in early agents, with at least one bucket reserved for high-potential semi-bluff hands" — the modern EMD-on-equity-distributions approach generalizes this by capturing potential implicitly via the spread of the histogram.
- `references/papers/libratus_brown_2017_science.pdf`: confirms imperfect-recall card abstraction is the deployed pattern; specific algorithm not detailed in the Science paper itself.
- `references/code/slumbot2019/src/build_kmeans_buckets.cpp` (MIT — safe to port architecturally): the production reference. Slumbot's pipeline: (a) `build_rollout_features.cpp` writes per-hand feature vectors (percentiles of win/wmls rollout distributions) to `features.<game>.<ranks>.<features_name>.<street>`; (b) `build_kmeans_buckets.cpp` reads features, dedups identical vectors via `SparseAndDenseLong` (hash-keyed dedup), then runs k-means on the unique feature vectors with `kmeans++` seeding (`kmeans.cpp::SeedPlusPlus`) and writes assignments to `buckets.<game>.<...>.<street>`. We adopt the *shape* of this pipeline (feature vectors → dedup → k-means → write assignments) without copying the C++.
- Slumbot's empirical experience (`references/code/slumbot2019/notes/abstraction`): feature design that produces "5.16M unique objects" for river takes too long; tightening percentile choices to `wml0.2 / wml0.3 / wml0.4 / wml` gives ~154K unique objects with 100K-bucket output. **Lesson absorbed: dedup *before* clustering is load-bearing.**

### 3.4 Bucket lookup at solve time

Given `(board, hole_cards, street)`, a bucket id in `[0, K_street)` is returned in O(1) by a precomputed lookup:

- The lookup key is a canonicalized `frozenset[Card]` or a packed-integer hash (we pick one — see Design Decision 7.5).
- The lookup value is the bucket id.
- The full lookup table for street `s` has `|reachable (board, hole) pairs|` entries; see Section 7 for storage-size estimates.

### 3.5 Plumbing into `HUNLPoker.infoset_key`

PR 3's `HUNLPoker.infoset_key(state, player)` currently returns `f"{player_hole}|{board}|{street_token}|{betting_history}"` — lossless on cards. PR 4 swaps the lossless prefix for a bucket id **only when an abstraction artifact is configured on the `HUNLConfig`**. Otherwise the lossless key is unchanged. This preserves PR 3's tiny-subgame tests and the cards-unabstracted river-only fixture, while enabling abstracted infoset keys for the full HUNL solve in PR 5.

Concretely: `HUNLConfig` gains an optional field `abstraction: AbstractionRef | None = None` (NOT `AbstractionTables` — corrected per consistency review v2 NEW-1). When set, the runtime resolves the ref to an `AbstractionTables` (loaded once and cached) and `infoset_key` calls `tables.lookup_bucket(board, hole_cards, street)` and emits `f"b{bucket_id}|{street_token}|{betting_history}"` instead of the lossless form. The card-string fields and the board are dropped from the key (they're captured in the bucket). Reason for `AbstractionRef` over `AbstractionTables`: PR 6's Rust loader only needs the path across the PyO3 boundary, not the full in-memory table object.

## 4. Pipeline stages

Five concrete stages, each independently testable. Stages 1–4 run once at *build* time (the CLI tool `precompute-abstraction`); Stage 5 is the runtime lookup.

### Stage 1: Equity-distribution feature extraction

**Per (hole_cards, board, street) instance**, build a histogram of the hand's equity (P(win | board, hole) + 0.5 · P(tie | board, hole)) against a **uniform-random opponent hole pair**, over **all reachable future board runouts** drawn uniformly from the remaining deck.

Concretely, for a hand on the river (5 board cards already revealed, no future runouts): the "histogram" has a single bin — the hand's exact equity against a uniform opponent. The bin index in the global histogram is determined by binning that scalar equity into `H` bins.

For a hand on the turn (4 board cards revealed, 1 river card to come): for each of the ~44 unseen cards, compute the river equity given (board + that card) vs uniform opponent → 44 equity values → histogram of those 44 values over `H` bins.

For a hand on the flop (3 board cards revealed, 2 cards to come): the runouts are pairs of (turn, river) cards, ~44 × 43 / 1 = ~1892 ordered turn/river pairs (we use ordered because turn-then-river matters for the chance node sequence, but the resulting river equity is symmetric in (turn, river) so we can use unordered ~990 pairs; pick one — see Design Decision 7.10).

The result is a `(num_hands_on_street, H)` float matrix per street. Each row is L1-normalized (sums to 1; it's a probability distribution).

**Uniform-opponent equity vs. blocker-aware equity:** the opponent is drawn uniformly from the 45-card complement of (board ∪ hero_hole). We do *not* condition the opponent on board blockers in a more sophisticated way (e.g., conditioning on a tight preflop range); v1 uses uniform. PR 9 (preflop solver) may add an option for range-weighted features. The flatness of the uniform-opponent prior is well-known to be a quality compromise (early Libratus features used hand-strength rollouts against uniform opponents; later refinements weight by preflop range). For v1 it's good enough and avoids the chicken-and-egg of needing a preflop solve to build the abstraction.

**Reuse existing equity machinery:** `poker_solver/equity.py::equity()` already computes Monte Carlo equity against uniform opponents. PR 4 will use a **deterministic enumeration** path (not the Monte Carlo path) at build time, because per-hand-per-board feature accuracy matters and we want bit-identical reruns. For each (hole, board), we enumerate all 990 (or 1892) future card pairs, evaluate the 7-card poker hand for both players via `poker_solver.evaluator.evaluate`, and compute exact equity vs the uniform-random opponent hole over each remaining-card pair.

Cost estimate: river is fastest (1 equity per hand, ~990 opponent hole combos per equity); flop is slowest (~990 runouts × ~990 opponent holes = ~10^6 evaluations per hero hand). See Section 7.7 for total time budget.

**Output:** three NumPy float32 arrays, `features_flop.npy`, `features_turn.npy`, `features_river.npy`, each shape `(N_street, H)`. Plus an index file mapping rows to `(board_canonical_id, hand_canonical_id)`.

### Stage 2: EMD distance matrix (computed lazily inside k-means)

We **never materialize** the full pairwise EMD matrix — at 1755 strategically-unique flops × 1326 hole-pair combos ≈ 2.3M flop feature vectors, a dense 2.3M × 2.3M f32 matrix is ~21 TB. Instead, we use **EMD as the in-loop distance inside k-means**: compute EMD only between each hand and the current `K` centroid feature vectors (per-iteration cost: `O(N · K · H)` where `H` is histogram bin count). This is the standard scalable approach.

For 1-D histograms (which our equity-bin distribution is), EMD has the closed-form expression:

```
EMD(p, q) = sum_{i=0..H-1} |CDF_p[i] - CDF_q[i]| / H
```

where `CDF_p` is the cumulative distribution of histogram `p`. This is **O(H)** per distance — extremely fast. (Reference: this is the standard 1-D Wasserstein-1 / "Mallow's metric" formula; same identity used implicitly in `scipy.stats.wasserstein_distance` for 1-D inputs, and explicitly cited in any EMD-bucketing tutorial.) Because our feature vectors are 1-D histograms, **we do not need a general LP-based EMD solver** (which would be `O(H^3 log H)` per call).

**Implementation note:** the closed form has known edge-case behavior when the two histograms have different total mass; since we L1-normalize all features to sum to 1, this is not an issue.

### Stage 3: K-means clustering on EMD

Standard Lloyd's-iteration k-means with EMD-on-CDFs as the distance, **kmeans++ initialization** (deterministic via a fixed seed; reference: `references/code/slumbot2019/src/kmeans.cpp::SeedPlusPlus`), and standard convergence criterion (max iterations OR no assignments change in a full pass).

Centroid update: for L1-normalized histograms with EMD, the optimal centroid of a cluster is the L1-normalized mean of the cluster members (`centroid[i] = mean_of_cluster_members[i]`). This is **not** the Fréchet mean for general EMD, but for 1-D histograms with CDF-EMD, the per-bin arithmetic mean of L1-normalized inputs is L1-normalized and is a good-enough centroid in practice — Slumbot's `kmeans.cpp` uses arithmetic mean per-feature, validated by their bucket quality. (A more principled alternative is **k-medoids** using actual cluster members as centroids, but that's slower; pick simple arithmetic mean for v1.)

Bucket count per street (locked targets, from PLAN.md): **256 flop / 128 turn / 64 river**.

Stopping rule: max **200 iterations** *or* fewer than **0.1%** of points changing assignment. (References: Slumbot uses 200 iterations as a default in `build_kmeans_buckets.cpp` usage strings.)

Seed: `--seed` flag on the CLI; default `42` so reruns are reproducible.

### Stage 4: Bucket lookup table

After clustering, each (board, hand) instance has an integer bucket id. We persist this as a lookup table keyed by `(board_canonical_id, hand_canonical_id)`:

- **Board canonicalization:** sort the board cards in `(rank, suit)` ascending order. Suit-isomorphism (where suits are interchangeable on a non-flushed board) is **explicitly not applied at this layer**. PR 6's Rust solver may add isomorphic suit reduction (postflop-solver pattern — see `docs/pr3_prep/postflop_solver_tree_notes.md` Section "Isomorphic suit reduction"); but the abstraction artifact itself stores one entry per actual board (1755 unique flops after card-canonicalization-by-sort = the "strategically-unique flops" number quoted across the literature; ~22100 unordered 3-card flops total). The bucket-lookup table will use **all 1755 canonical flops** (the rank-isomorphism-reduced count); turn/river boards are extended from these. Suit symmetry is left to a separate PR.

  - **Why 1755 flops, not 22100:** of the C(52,3) = 22100 ordered-cards-not-equal flops, many are *suit-equivalent* — e.g., As-Ks-Qs vs. Ah-Kh-Qh play identically because no preflop-range information has been conditioned on suits. Standard count: 1755 strategically-unique flop classes (under suit-permutation isomorphism). Reference: this is a well-known number in the OSS solver community; `references/code/postflop-solver` materializes it via `card.rs::isomorphism`. We use 1755 to size our flop bucket table.
  - **Caveat:** the 1755 figure assumes opponent range is suit-symmetric (uniform random IS suit-symmetric; full preflop ranges typically also are post-flop). If we ever condition on an asymmetric preflop range, we'd need to fall back to the 22100-flop count.

- **Hand canonicalization:** within a board, the two hole cards are an unordered pair. We canonicalize to sorted-tuple `((r0, s0), (r1, s1))` with `(r0, s0) <= (r1, s1)`. Per-board, ~990 to 1081 hole-card pairs are valid (after excluding any pair conflicting with the board).

- **Storage:** a flat array indexed by `(board_canonical_id * max_hands_per_board) + hand_canonical_id`. Bucket ids fit in a `u8` for flop (256 < 256), `u8` for turn (128 < 256), `u8` for river (64 < 256) — total per-street is one byte per (board, hand) entry. Could compress further (e.g., 6 bits per entry packed) but bytes-per-entry is plenty.

### Stage 5: Serialization

A single `.npz` file (NumPy compressed archive) with five arrays per street and a metadata dict:

```
abstraction_v1.npz
  flop_assignments   : uint8[N_flop_hands]            # bucket id per (canonical_board, canonical_hand)
  flop_board_index   : uint32[1755]                   # offset into flop_assignments for board i
  flop_hand_lookup   : packed structure mapping canonical_hand_key -> within-board index
  turn_assignments   : uint8[N_turn_hands]
  turn_board_index   : uint32[N_unique_turn_boards]
  turn_hand_lookup   : ...
  river_assignments  : uint8[N_river_hands]
  river_board_index  : uint32[N_unique_river_boards]
  river_hand_lookup  : ...
  metadata           : { schema_version: 1, bucket_counts: [256, 128, 64],
                         feature_bins: H, seed: int, build_timestamp: str,
                         build_duration_sec: float, lossless_streets: [] }
```

`.npz` chosen because: (a) NumPy ecosystem is the existing dependency; (b) it's a single file (atomic); (c) it's portable across Python versions; (d) we get gzip compression for free; (e) PR 6's Rust port can read NPY via the `ndarray-npy` crate. **Alternative considered:** SQLite (would offer per-board lookup without loading the whole file; rejected because 16 GB MacBook can hold all three tables in RAM trivially — see size estimate in Section 7.6 — and `.npz` is simpler).

Schema versioning: `schema_version: 1`. If the lookup format changes in a future PR, bump this and have the loader check it. Loaders error with a clear message on version mismatch.

## 5. Files to create

- `poker_solver/abstraction/__init__.py` — exports `lookup_bucket`, `AbstractionTables`, `load_abstraction`, `save_abstraction`, plus the per-stage builders for testability.
- `poker_solver/abstraction/equity_features.py` — Stage 1. Functions: `compute_river_features(boards, hands, H) -> np.ndarray`, `compute_turn_features(...)`, `compute_flop_features(...)`. Plus a helper `equity_distribution(board, hole_cards, num_runouts) -> np.ndarray` that wraps `poker_solver.evaluator.evaluate` in a deterministic enumeration loop.
- `poker_solver/abstraction/emd_clustering.py` — Stages 2 + 3. Functions: `emd_1d(p, q) -> float`, `kmeans_emd(features, K, seed, max_iter) -> (assignments, centroids, history)`. The k-means implementation is custom NumPy (we **do not** add `scikit-learn` as a dependency — see Decision 7.4); it uses vectorized CDF computation for the EMD-vs-centroids step.
- `poker_solver/abstraction/buckets.py` — Stage 4 + Stage 5 lookup. Functions: `class AbstractionTables` (dataclass holding the three per-street tables + metadata), `load_abstraction(path: Path) -> AbstractionTables`, `save_abstraction(tables: AbstractionTables, path: Path) -> None`, `lookup_bucket(tables, board, hole_cards, street) -> int`. Includes a fall-through path: if `street == Street.PREFLOP`, return `-1` (no preflop bucket; caller uses the lossless preflop infoset).
- `poker_solver/abstraction/precompute.py` — CLI entry point. Function `build_abstraction(out_path, bucket_counts, seed, H, max_iter) -> AbstractionTables`. Calls Stages 1 → 2 → 3 → 4 → 5 with progress reporting (tqdm or plain `print` — see Decision 7.6).
- `tests/test_abstraction_emd.py` — Stage 2/3 tests (EMD math + k-means convergence on synthetic data).
- `tests/test_abstraction_buckets.py` — Stage 4/5 tests (canonicalization, lookup correctness, serialization round-trip).
- `tests/test_abstraction_integration.py` — end-to-end smoke test on a tiny config (e.g., 8 flops × N hands, bucket counts 4/2/2) verifying the full pipeline runs and the produced file plumbs through `HUNLPoker.infoset_key`.

## 6. Files to modify

- `poker_solver/hunl.py`:
  - `HUNLConfig` gains an optional `abstraction: Optional[AbstractionRef] = None` field.
    - **Forward-looking note (consistency review B2 resolution).** `AbstractionRef` is a small dataclass declared in `poker_solver/abstraction/buckets.py` alongside `AbstractionTables`:
      ```python
      @dataclass(frozen=True)
      class AbstractionRef:
          source_path: str   # absolute path to the .npz on disk
          version: str       # e.g. "v1"; matches metadata['schema_version']
      ```
      Callers that need the in-memory bucket tables call `load_abstraction(ref.source_path)` themselves. PR 6's Rust solver consumes only `(source_path, version)` over the PyO3 boundary and calls its own `abstraction::load_abstraction` to materialize the tables Rust-side; this avoids serializing the entire (up to 750 MB) bucket table across the FFI boundary. PR 9's preflop solver does the same.
    - **PR 4's CLI builder** (`build_abstraction(...)`) writes the `.npz` and returns an `AbstractionTables` for in-process callers; `AbstractionTables` carries `source_path: str` (set by `save_abstraction`) so callers can construct an `AbstractionRef` trivially.
  - `HUNLPoker.infoset_key(state, player)` checks `state.config.abstraction`: if present and `state.street >= Street.FLOP`, the engine has already loaded the tables (via `solve(...)` ensuring `load_abstraction(ref.source_path)` was called and the result attached as `state.config._loaded_abstraction`); emit `f"b{bucket_id}|{street_token}|{betting_history}"` (board + hole-cards collapsed into bucket id); otherwise emit the lossless PR 3 form unchanged. Preflop is always lossless.
- `poker_solver/__init__.py` — re-export `AbstractionTables`, `load_abstraction`, `save_abstraction`, `lookup_bucket`, `build_abstraction`.
- `poker_solver/cli.py`:
  - New subcommand `precompute-abstraction` with flags `--output PATH` (default `abstraction_v1.npz`), `--bucket-counts 256,128,64`, `--feature-bins 50`, `--seed 42`, `--max-iter 200`, `--street {flop,turn,river,all}` (default `all` so users can build one street at a time for testing).
  - New flag on the `solve` subcommand: `--abstraction PATH` — when supplied, loads the file and attaches it to the `HUNLConfig`. Defaults to None (preserves PR 3 lossless behavior).
- `tests/test_hunl_core.py` (PR 3 file) — **not modified.** PR 3's lossless tests must continue to pass unchanged; the abstraction is opt-in.
- `pyproject.toml` — verify `numpy` is already a dependency (it is, per PR 3 spec). No new third-party deps added (per Decision 7.4). Add `[project.scripts]` entry if not already covered by the existing `poker-solver` console script.

## 7. Critical design decisions (defaults locked; user may override before implementation)

Each item lists the spec's default and the rationale. If user disagrees, redirect before agents launch.

### 7.1 Equity-distribution histogram resolution (number of bins H)

**Default: H = 50.**

Rationale: Slumbot uses 1–4 percentiles per street (`wmls4.a` config — see `references/code/slumbot2019/notes/abstraction`) but those are summary statistics, not full histograms. For full histogram features 50 bins is the canonical choice in academic EMD-bucketing papers (cited indirectly by `gto_poker_survey_2024.pdf`'s discussion of "7 buckets per round" being an early simplification; modern work uses denser histograms). 50 bins → each bin is 2% equity wide, sufficient resolution to distinguish hand-strength shape (nut vs draw vs marginal pair). Memory cost is trivial at 50 (50 floats × ~10^6 hands × 3 streets ≈ 600 MB f32 transient build cost, freed after clustering).

Override candidates: H = 30 (faster build) or H = 100 (sharper shape distinction).

### 7.2 EMD distance computation library

**Default: custom NumPy implementation in `emd_clustering.py`** using the 1-D closed form `EMD(p, q) = mean(|cumsum(p) - cumsum(q)|)`.

Rationale: scipy's `wasserstein_distance` is general-purpose and adds a scipy dependency we don't otherwise need. The 1-D closed-form is 3 lines of NumPy:

```python
def emd_1d(p, q):
    return np.mean(np.abs(np.cumsum(p) - np.cumsum(q)))
```

and is straightforwardly vectorizable across batches (compute `cumsum` once per centroid update, broadcast over points). No external dep needed.

Override candidates: scipy (if user prefers a well-tested library).

### 7.3 K-means library

**Default: custom NumPy implementation** in `emd_clustering.py`.

Rationale: same as Decision 7.2 — avoid pulling in scikit-learn for a 200-line Lloyd's loop. The implementation is straightforward:

```python
def kmeans_emd(features, K, seed, max_iter):
    rng = np.random.default_rng(seed)
    # kmeans++ seeding via EMD distances
    centroids = _kmeans_plusplus_init(features, K, rng)
    for it in range(max_iter):
        # vectorized distance from every point to every centroid
        dists = _batch_emd(features, centroids)  # (N, K) array
        assignments = dists.argmin(axis=1)
        new_centroids = np.array([features[assignments == k].mean(axis=0)
                                   for k in range(K)])
        # convergence check (fraction changed)
        if (assignments == prev_assignments).mean() > 0.999:
            break
        centroids = new_centroids
    return assignments, centroids
```

Override candidates: scikit-learn (if user wants the maturity and we accept the dependency).

### 7.4 New dependency policy

**Default: no new third-party deps.** Stick with numpy (already a dep per PR 1). Optionally add `tqdm` for CLI progress bars; this is small, MIT, and trivially removable.

Rationale: each dep added means another macOS distribution surface to test (PR 11 packaging). Custom NumPy code is ~400 LOC total; manageable.

Override candidates: add `scikit-learn` + `scipy` if user prefers maturity over minimal deps.

### 7.5 Bucket file format

**Default: `.npz` (NumPy compressed archive).**

Rationale per Section 4 Stage 5. Single file, atomic, NumPy-native, gzip-compressed, portable to Rust via `ndarray-npy`.

Override candidates: SQLite (per-board lazy load), HDF5 (richer metadata; adds `h5py` dep), custom binary (smallest on disk; least portable).

### 7.6 Storage size estimate (target: <100 MB)

Per-street size estimate (assuming u8 bucket ids):

- **Flop:** 1755 canonical boards × ~1081 hole-pairs/board (after blocking) ≈ 1.9M entries × 1 byte = **~1.9 MB**.
- **Turn:** ~16,432 canonical turn boards (1755 flops × ~10 unique turn cards under suit-iso, rough) × ~1035 hole-pairs ≈ **~17 MB**. (Upper bound: 1755 × 49 × 1035 ≈ 89 MB if no turn-suit iso applied.)
- **River:** ~755K canonical river boards × ~990 hole-pairs ≈ **~750 MB** uncompressed. **This blows the 100 MB target on river.**

**Implication: we must apply suit-isomorphism at the river layer** — the river layer is too big otherwise. Practical mitigation: at build time, compute river bucket assignments only for *strategically-unique* river boards under full suit isomorphism (a much smaller set), and at lookup time canonicalize the input board to that smaller set. This adds complexity but is necessary.

**Alternative**: store the river layer at coarser granularity (e.g., 1 byte per *equity bin* rather than per exact (board, hand)), trading lookup fidelity for size. Defer that choice — it's a PR 5 follow-up after we have actual size measurements.

**Decision for PR 4:** ship without river suit-iso for the first pass; let the actual on-disk size be the data point. **Set a hard guard rail: if the build artifact exceeds 1 GB, the CLI exits with an error** asking the user to reduce bucket counts or add suit-iso. Don't silently ship multi-GB files.

(Decision flagged for user review: **the spec assumes suit-iso is not implemented in PR 4**. If the user wants to pre-empt the river-size issue, suit-iso lands in PR 4 too — adds ~1–2 days, ~300 LOC.)

### 7.7 Precompute time budget

Stage 1 equity-distribution enumeration is the dominant cost. Order-of-magnitude estimates on the M-series MacBook (using existing `poker_solver.evaluator.evaluate` — pure Python, ~200K evals/sec):

- **River:** 1.9M hands × 1 equity evaluation × 990 opponent holes ≈ **1.9B `evaluate()` calls** = ~2.6 hours single-threaded.
- **Turn:** 1.7M hands × 44 future cards × 990 opponent holes ≈ **~74B calls** = ~4 days single-threaded.
- **Flop:** 1.9M hands × ~990 turn-river pairs × 990 opponent holes ≈ **~1.9T calls** = ~110 days single-threaded.

**The naive single-threaded Python build is infeasible for flop.** Mitigations (combined):

1. **Multiprocessing across boards** via `concurrent.futures.ProcessPoolExecutor` — 8 cores → 8× speedup (M-series have ~8 perf cores). Reduces flop to ~14 days.
2. **Replace `evaluator.evaluate()` with a vectorized NumPy / pre-cached 7-card lookup.** Slumbot's `build_hand_value_tree.cpp` builds an exact lookup table over all 7-card hand classes — at ~133M classes, fits in RAM. A pre-cached table reduces per-call cost from ~5 microseconds (Python evaluator) to ~50 nanoseconds (table indexing) → 100× speedup. Reduces flop to ~3 hours.
3. **Monte Carlo with high iteration count** instead of exact enumeration — `iterations=100_000` per (board, hand) instead of full enumeration. Approximate equity to ~0.3% accuracy. Reduces flop to ~10 hours single-threaded, ~1.5 hours on 8 cores.

**Spec choice for PR 4:**
- River + Turn: **exact enumeration** (acceptable cost).
- Flop: **Monte Carlo** with `iterations=200_000` per (board, hand) as the *default*; expose `--flop-mode {exact,mc}` flag with `mc` default. Document the ~0.2% equity error in features as acceptable for clustering (k-means is robust to feature noise at this level).

**Acceptable build time (one-time, on user's MacBook):** target ≤8 hours overnight for the full `precompute-abstraction --bucket-counts 256,128,64`. If the actual build exceeds 24 hours, that's a "ship a Rust-side preprocessor" PR-5-or-later follow-up.

(Decision flagged: **MC-on-flop is the spec default**. User may override to demand exact enumeration; that pushes the build into multi-day territory and likely requires Rust acceleration.)

### 7.8 Equity-distribution feature design refinement

**Default: per-street feature is the hand's equity-vs-uniform-opponent histogram over all future board runouts**, with `H = 50` bins.

There are subtler feature designs in the literature (EHS², OCHS, potential-aware histograms), but they all share the same shape: a fixed-length per-hand feature vector. The pipeline is feature-agnostic — only `equity_features.py` knows the specific feature.

**For v1, we use the simplest:** "equity vs uniform random" histogram, bucketed into 50 bins. Rationale: it's the standard baseline; debuggable; matches `equity.py` semantics.

Future feature variants (out-of-scope for PR 4, but the pipeline is structured to allow them):
- **OCHS:** equity-vs-K-clustered-opponent-buckets histogram (K typically 8). Captures "how does this hand do against tight ranges vs loose ranges" — more discriminating than uniform.
- **EHS² (hand strength squared):** mean of (equity)² rather than histogram of equity. Two scalars per hand. Older / less discriminating but cheap.
- **Potential-aware EHS:** EHS plus the "drawing potential" — equity histogram entropy.

### 7.9 Imperfect recall vs perfect recall on lower streets

Spec assumes **imperfect recall on all three postflop streets** — turn bucket doesn't see flop bucket, river bucket doesn't see turn bucket. This is the locked PLAN.md decision and is the only way 256/128/64 buckets keep memory in budget.

Caveat: imperfect recall introduces "abstraction pathologies" — hands that look equivalent on the turn under the feature may actually have different optimal strategies because of how the flop went. Standard Libratus mitigation: keep some perfect-recall structure at the flop (e.g., the action history alone). PR 4 inherits this from PR 3's `betting_history` which is preserved in the infoset key.

### 7.10 Future-runout ordering (flop features)

The flop feature considers all (turn, river) pairs to come. Two options:

- **Ordered:** treat (T_card, R_card) and (R_card, T_card) as distinct — 44 × 43 = 1892 pairs per flop. Matters if we ever want to model order-dependent abstractions (we don't).
- **Unordered:** treat them as the same — 44 × 43 / 2 = 946 pairs per flop. Equivalent for equity computation (the river is the river regardless of which came when).

**Default: unordered (946 pairs).** Half the compute, identical resulting feature.

### 7.11 Histogram bin scheme

**Default: equal-width bins on equity in [0, 1].** Bin `i` covers `[i/H, (i+1)/H)`.

Alternative considered: **quantile bins** (each bin contains ~1/H of the overall equity distribution). Slumbot uses percentile-based summary features (`wmls4.a` config). Quantile bins are more discriminating in regions with high hand density but harder to interpret. v1 sticks with equal-width for debuggability; PR 4 can revisit if cluster quality is poor.

### 7.12 Preflop handling

**Default: preflop infosets remain lossless.** PLAN.md confirms preflop is not bucketed in v1. The lookup function returns `bucket_id = -1` for preflop, and `HUNLPoker.infoset_key` keeps the lossless preflop format.

The lossless preflop key already canonicalizes 1326 → 169 strategically-unique starting hands by suit-isomorphism. That fits memory at the preflop layer; bucketing further is unnecessary.

## 8. Three-agent fan-out plan

Same pattern as PR 3: write tight per-agent specs against the interfaces in Section 5, launch concurrently, integrate at the end.

### Agent A — equity features + EMD clustering

**Owns:** `poker_solver/abstraction/equity_features.py`, `poker_solver/abstraction/emd_clustering.py`.

**Does NOT touch:** `buckets.py`, `precompute.py`, `hunl.py`, `cli.py`, any test file.

**Deliverables:**
- `equity_distribution(board: tuple[Card, ...], hole_cards: tuple[Card, Card], H: int, mode: Literal["exact", "mc"], mc_iterations: int = 200_000, rng: np.random.Generator | None = None) -> np.ndarray` — returns an H-element histogram (sum to 1.0) of equity vs uniform-random opponent over all (or sampled) future runouts. Internally calls `poker_solver.evaluator.evaluate`.
- `compute_river_features(boards: list[tuple[Card, ...]], hands_per_board: dict, H: int) -> np.ndarray` — Stage 1 entry for river.
- `compute_turn_features(...)`, `compute_flop_features(...)` — same shape; flop uses MC by default per Decision 7.7.
- `emd_1d(p: np.ndarray, q: np.ndarray) -> float` — 1-D closed-form EMD.
- `batch_emd(points: np.ndarray, centroids: np.ndarray) -> np.ndarray` — vectorized `(N, K)` distance matrix in O(N·K·H).
- `kmeans_emd(features: np.ndarray, K: int, seed: int = 42, max_iter: int = 200, change_tolerance: float = 0.001) -> KMeansResult` where `KMeansResult` is a dataclass `(assignments: np.ndarray[uint8 or uint16], centroids: np.ndarray, history: list[float])` (history = per-iteration mean assignment-distance, for convergence diagnostics).
- kmeans++ initialization (deterministic given seed).
- Pure NumPy; no scipy / sklearn. Type-hinted; `mypy --strict` clean.

### Agent B — bucket lookup + persistence + HUNL integration

**Owns:** `poker_solver/abstraction/buckets.py`, `poker_solver/abstraction/precompute.py`, `poker_solver/abstraction/__init__.py`. Also: the edits to `poker_solver/hunl.py`, `poker_solver/__init__.py`, `poker_solver/cli.py`.

**Does NOT touch:** `equity_features.py`, `emd_clustering.py`, any test file.

**Deliverables:**
- `AbstractionTables` dataclass with the per-street arrays + metadata dict per Section 4 Stage 5.
- `lookup_bucket(tables: AbstractionTables, board: tuple[Card, ...], hole_cards: tuple[Card, Card], street: Street) -> int` — canonicalizes board + hole, computes the lookup. Returns `-1` for preflop.
- `save_abstraction(tables: AbstractionTables, path: Path) -> None`, `load_abstraction(path: Path) -> AbstractionTables` — `.npz` format, schema version check.
- `_canonical_board_id(board: tuple[Card, ...]) -> int` — sort-by-(rank, suit) board; map to an integer index in [0, 1755) for flops, [0, N_turn) for turns, [0, N_river) for rivers. **Suit-iso NOT applied** per Decision 7.6.
- `_canonical_hand_key(hole_cards: tuple[Card, Card]) -> int` — sort-by-(rank, suit) hole-pair; map to an index in [0, 1326).
- `build_abstraction(out_path: Path, bucket_counts: tuple[int, int, int] = (256, 128, 64), seed: int = 42, H: int = 50, max_iter: int = 200, streets: list[Street] = [FLOP, TURN, RIVER], flop_mode: Literal["exact", "mc"] = "mc", mc_iterations: int = 200_000, progress: bool = True) -> AbstractionTables` — orchestrates Stages 1–4 by calling Agent A's functions, then Stage 5 save.
- Modifies `HUNLConfig` (adds `abstraction: AbstractionRef | None = None` field — NOT `AbstractionTables`, per §3.5 and §6 amendments) and `HUNLPoker.infoset_key` per Section 6. **Crucial:** PR 3's lossless behavior must be preserved when `abstraction is None`.
- Modifies `cli.py` to add the `precompute-abstraction` subcommand and the `--abstraction PATH` flag on `solve`.

### Agent C — tests (written from spec alone)

**Owns:** `tests/test_abstraction_emd.py`, `tests/test_abstraction_buckets.py`, `tests/test_abstraction_integration.py`.

**Does NOT touch:** any non-test file.

**Deliverables:**

**`test_abstraction_emd.py` (~12 tests):**
1. `test_emd_zero_for_identical_histograms` — `emd_1d(p, p) == 0`.
2. `test_emd_one_for_opposite_extremes` — `emd_1d(delta_at_0, delta_at_1) ≈ 1.0` (mean of CDF differences).
3. `test_emd_symmetric` — `emd_1d(p, q) == emd_1d(q, p)`.
4. `test_emd_triangle_inequality` — for three random histograms, `emd_1d(p, r) <= emd_1d(p, q) + emd_1d(q, r)`.
5. `test_batch_emd_matches_loop` — `batch_emd(points, centroids)[i, j] == emd_1d(points[i], centroids[j])` for all i, j.
6. `test_kmeans_separates_clearly_distinct_clusters` — synthetic 4 well-separated histogram blobs, K=4, kmeans assigns each blob a different cluster.
7. `test_kmeans_reproducible_with_seed` — same seed → identical assignments.
8. `test_kmeans_converges_within_max_iter` — on synthetic data, history shows mean distance decreasing then plateau.
9. `test_kmeans_handles_empty_cluster` — adversarial init that produces an empty cluster on iter 1; kmeans recovers (e.g., re-seeds the empty cluster from the farthest point).
10. `test_kmeans_centroid_is_l1_normalized` — every returned centroid sums to ~1.0.
11. `test_kmeans_assignments_in_range` — every assignment in [0, K).
12. `test_kmeans_plusplus_init_deterministic` — same seed → same initial centroids.

**`test_abstraction_buckets.py` (~14 tests):**
1. `test_canonical_board_id_sorts_input` — board `[Kh, As, 2c]` canonicalizes to same id as `[2c, As, Kh]`.
2. `test_canonical_board_id_in_range` — for 100 random 3-card flops, id is in `[0, 22100)` (or `[0, 1755)` if suit-iso applied; spec default uses 22100 since suit-iso is not applied — TIGHTEN ONCE DECISION 7.6 RESOLVES).
3. `test_canonical_hand_key_sorts_input` — hand `(Ah, Kh)` and `(Kh, Ah)` produce same key.
4. `test_lookup_bucket_returns_minus_one_for_preflop` — `street == PREFLOP` → `-1`.
5. `test_lookup_bucket_returns_in_range_for_postflop` — flop bucket in `[0, 256)`, turn in `[0, 128)`, river in `[0, 64)`.
6. `test_lookup_bucket_deterministic` — same input → same output.
7. `test_save_load_round_trip` — write tables, read back, assert array equality.
8. `test_save_load_schema_version_check` — corrupt the `schema_version` field on disk, loader raises clear error.
9. `test_save_load_size_under_guard_rail` — built test artifact (tiny config) is <100 KB; spec's full artifact size is checked separately.
10. `test_lookup_bucket_handles_unknown_board_gracefully` — board not in the table (e.g., a turn lookup on a flop-shaped board): raises a clear `KeyError` or `ValueError` with a message pointing at the user-error.
11. `test_abstraction_tables_metadata_includes_bucket_counts` — saved tables expose `metadata['bucket_counts']`.
12. `test_lookup_bucket_handles_blocking` — board includes one of hero's hole cards → raises `ValueError` (this is a caller bug; we want it loud, not silent).
13. `test_canonical_hand_key_in_range` — for 1000 random hole-pairs, key is in `[0, 1326)`.
14. `test_build_abstraction_writes_file` — with tiny synthetic config (bucket_counts=(4, 2, 2), H=10, streets=[RIVER] only on 3 boards), the function produces a valid `.npz`.

**`test_abstraction_integration.py` (~8 tests):**
1. `test_pr3_tiny_subgame_still_passes_without_abstraction` — re-run PR 3's default-tiny-subgame solve with `HUNLConfig(abstraction=None)`; assert it still converges, infoset keys are still lossless strings.
2. `test_tiny_subgame_with_abstraction_produces_bucketed_infosets` — same subgame but with a synthetic 3-bucket-per-street artifact loaded; assert infoset keys now start with `b<digit>|` not raw card strings.
3. `test_abstraction_collapses_strategically_similar_hands` — construct two hands on a dry board with similar feature vectors (e.g., AhKh and AhQh on As7c2d board); after build with K=4 buckets, assert they end up in the same bucket. (Decision tolerance: if they don't, the test is allowed to fail — it's a soft sanity check, not a hard guarantee.)
4. `test_end_to_end_build_loadback_solve` — build a tiny abstraction (4/2/2 buckets), load it, plumb it through a tiny subgame, run 100 DCFR iterations, assert no crash + finite exploitability.
5. `test_abstraction_lookup_speed_under_1us` — measure: 1000 lookups in <1ms (i.e., O(1) lookup as designed).
6. `test_build_abstraction_seed_reproducibility` — same `--seed` twice → identical artifact bytes.
7. `test_cli_precompute_abstraction_smoke` — call `poker-solver precompute-abstraction --output /tmp/test.npz --bucket-counts 4,2,2 --feature-bins 10 --street river` (only river to keep it fast); assert file exists, schema valid, river bucket count = 2.
8. `test_cli_solve_with_abstraction_loads_file` — `poker-solver solve --game hunl --hunl-mode tiny_subgame --abstraction /tmp/test.npz` runs without crash.

Agent C writes from the spec alone; does not see A/B code while writing. Allowed to surface ambiguities — those round-trip to spec edits, not silent test tweaks.

## 9. Risks and mitigations

- **EMD computation may be slow at scale.** With 2.3M flop feature vectors and K=256 centroids, the in-loop EMD-vs-centroids step is `2.3M × 256 × 50` = ~29B floating-point ops per k-means iteration. NumPy vectorization gets us to ~50M ops/sec on a single CPU thread → ~10 minutes per k-means iteration → ~30 hours per street for 200 iterations. **Mitigation:** (a) implement `batch_emd` carefully (`np.cumsum` once per centroid update, broadcast over points); (b) early-stop on convergence (rare to need full 200 iter); (c) accept multi-hour build times for the v1 artifact (one-time cost).

- **K-means initialization may produce unstable bucket assignments across runs.** Seeded init (kmeans++) plus a fixed `--seed` flag gives reproducibility. We also lock the seed in the metadata so a future developer can reproduce the exact artifact.

- **Serialized bucket files become a hidden dependency for the solver.** Once PR 5 lands, full-HUNL solves *require* the abstraction artifact to be built first. Mitigation: (a) document in `README.md` that running a full solve requires `poker-solver precompute-abstraction` first; (b) the solver errors with a clear "no abstraction file loaded; either pass `--abstraction PATH` or run `precompute-abstraction` first" if the user tries to run full HUNL without one; (c) PR 11 packaging may bundle a default `abstraction_v1.npz` in the wheel (small enough at ~100 MB after compression).

- **Feature-vector design is the real abstraction-quality lever, and we're picking the simplest one for v1.** Equity-vs-uniform-opponent histograms is a known-baseline; OCHS / potential-aware would be better. Mitigation: the pipeline is feature-agnostic (Agent A's interface takes feature vectors of any shape); a follow-up PR can swap in OCHS without rewriting clustering or lookup.

- **River file size may blow the 100 MB target.** Per Section 7.6, river layer alone is ~750 MB uncompressed without suit-iso. Mitigation in spec: hard guard rail of 1 GB; if exceeded, CLI errors with "consider --skip-river or implement suit-iso (PR follow-up)." Decision flagged for user review.

- **`HUNLPoker.infoset_key` change is a load-bearing modification.** PR 3's 97 tests must still pass when `abstraction is None`. Mitigation: Agent B writes the integration test `test_pr3_tiny_subgame_still_passes_without_abstraction` first; if it fails, the impl is wrong.

- **Build time on flop is multi-hour even with Monte Carlo + multiprocessing.** Mitigation: ship the CLI with a checkpoint-and-resume capability (Stage 1 feature arrays are saved to `.npy` files in a temp dir; if `precompute-abstraction` is interrupted, the rerun skips already-computed streets). This is ~50 LOC in Agent B's `precompute.py`.

- **Imperfect-recall pathologies.** Standard known issue; not a regression. Documented in code comments. PR 5's per-street profiler will tell us whether the abstraction is good enough or needs tightening.

## 10. Out-of-scope follow-ups

- **Lossless cards revisit** (PLAN.md commitment): after PR 5 ships the memory profiler, revisit whether river or turn can go lossless. If river is <30% of total solver memory, the abstraction artifact's river layer drops out and `lookup_bucket(..., Street.RIVER)` returns `-1` (caller falls back to lossless).
- **OCHS / EHS² / potential-aware features** — alternate `compute_*_features` functions in `equity_features.py`. Pipeline already feature-agnostic; just need new feature module + a CLI flag.
- **Suit-isomorphism reduction at the lookup layer** — reduces river table size 4× to 16×. Required if user wants to fit a fully-lossless-on-turn artifact. ~300 LOC. Could land as PR 4.5.
- **Range-aware features** — replace uniform-random opponent with a fixed preflop range (e.g., a "tight HU 100 BB SB range"). Requires PR 9's preflop range parser to be wired in. Better feature quality at the cost of dependency on PR 9.
- **Vectorized / Rust-side equity feature builder** — moves Stage 1 from Python to Rust for 100× speedup. PR 6 candidate (Rust port).
- **Bucket-quality benchmark vs PioSolver** — generate a fixed test set of flops, run our abstracted solver against PioSolver outputs, measure strategy-difference. Wait until PR 7 (river diff vs noambrown) lands the diff-test scaffolding.
- **Live abstraction reload on solver-running process** — currently the abstraction is baked into `HUNLConfig` at solver-instantiation time. Hot-reload could allow swapping abstractions mid-session; not a v1 requirement.
- **Schema migration tool** — if `schema_version` bumps, write a one-shot converter from v1 to v2 so users don't have to rebuild from scratch. PR 11 polish-tier task.

## 11. Success criteria

- All new tests pass (~34 new tests across the three test files).
- All PR 3 tests pass unchanged (lossless behavior preserved when `abstraction is None`).
- `ruff check poker_solver tests` clean (no new warnings on the new module).
- `mypy poker_solver/abstraction/` strict-clean (new code).
- `poker-solver precompute-abstraction --output /tmp/abstraction_v1.npz --bucket-counts 256,128,64 --street river` completes overnight on the MacBook (river-only build is fast).
- A river-only build with bucket count = 64 produces an artifact that can be plumbed into `HUNLPoker.infoset_key` and shows infoset-count compression ratio ≥ 100× vs lossless (1326 hands × N boards collapsed to 64 buckets — the smoke proves the abstraction is actually shrinking the state space).
- Pipeline is observable: `kmeans_emd` returns a `history` of per-iteration mean-distance values, plottable by the user post-build.

## 12. Open questions flagged for user clarification before launch

The defaults are locked; the user may redirect on any of these:

- **Q1 (Decision 7.6 / Risk):** Should PR 4 implement suit-isomorphism at the river layer? Without it, the river bucket file is ~750 MB uncompressed (~150 MB compressed in `.npz` after gzip — but still above the 100 MB ideal). With suit-iso, it drops to ~50 MB. Cost: ~1–2 days, ~300 LOC. Default spec says **no** (defer to a PR 4.5); guard rail catches it.

- **Q2 (Decision 7.7):** Acceptable to use Monte Carlo (200K iterations per board × hand) for the flop equity-feature stage? It introduces ~0.2% noise per feature value. Default spec says **yes**; user may want exact enumeration (multi-day build).

- **Q3 (Decision 7.4):** OK to keep the "no new dependencies" stance (custom NumPy k-means + EMD), or pull in scikit-learn + scipy for maturity? Default spec says **custom NumPy**; ~400 LOC across the two impl files.

- **Q4 (Decision 7.5):** `.npz` format OK, or prefer SQLite / HDF5 / custom binary? Default spec says **`.npz`**.

- **Q5:** Build the **per-street profiler** in PR 4 (lightweight: emit a JSON report after each clustering with per-street avg cluster size, max-cluster size, EMD silhouette score), or wait for PR 5? Default spec says **wait for PR 5** — PR 4 only emits the `history` list. User may want richer telemetry.

- **Q6:** Should the abstraction artifact be committed to the repo (so users don't have to rebuild) or always built locally? Compressed `.npz` is ~100 MB which is large for a git repo but manageable with Git LFS. Default spec says **always built locally**; never commit the artifact.
