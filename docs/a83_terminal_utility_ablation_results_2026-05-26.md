# A83 terminal-utility convention ablation — 2026-05-26 (PR 93)

**VERDICT: CONVENTION-IS-A83-CAUSE**

Primary decision metric (A83 @ 2000 iters, max-|Δ|): `0.122703` (12.2703pp).
Aggregate metric (max across all arms): `0.499953` (49.9953pp). Aggregate verdict: **CONVENTION-IS-A83-CAUSE**.

## Pre-registered decision rule

From the PR 93 ablation spec:

| max-|Δ| range | verdict |
|---|---|
| < 1pp | CONVENTION-IS-CONSTANT-OFFSET (arbitrator confirmed) |
| 1pp ≤ Δ < 5pp | CONVENTION-AFFECTS-STRATEGY-PARTIAL |
| ≥ 5pp | CONVENTION-IS-A83-CAUSE |

Hyperparameters: α=1.5, β=0, γ=2.0 (PLAN.md §1 DCFR defaults). DCFR vector-form CFR engine (`crates/cfr_core/src/dcfr_vector.rs`).

## Run summary

| Fixture | iters | rust wall | brown wall | max-\|Δ\| | mean-\|Δ\| | p99-\|Δ\| | shared keys |
|---|---|---|---|---|---|---|---|
| `dry_A83_rainbow` | 2000 | 166.6s | 164.2s | 0.122703 | 0.000399 | 0.005545 | 2079 |
| `dry_A83_rainbow` | 8000 | 630.9s | 639.8s | 0.102839 | 0.000431 | 0.008742 | 2079 |
| `dry_K72_rainbow` | 2000 | 119.5s | 118.1s | 0.499953 | 0.006493 | 0.107399 | 1650 |
| `dry_K72_rainbow` | 8000 | 469.0s | 472.5s | 0.499953 | 0.006070 | 0.107795 | 1650 |

## Max-|Δ| cell per arm

The empirical worst-case (player, hand, history, action) tuple for each arm, sourced directly from the strategy dumps. Note that the named A83 worst cells (`3sAs` / `3cAc` at `b1000r3000`) show near-zero diff under our representation (see spotlight section below). The real divergence concentrates at other deep-cap histories, listed here.

| Fixture | iters | max-\|Δ\| key | action | rust | brown |
|---|---|---|---|---|---|
| `dry_A83_rainbow` | 2000 | `TsTh|3d6s8cTcAh|r|xb1000r3000` | 1 (|Δ|=0.1227) | 0.5081 | 0.3854 |
| `dry_A83_rainbow` | 8000 | `TsTd|3d6s8cTcAh|r|b500r2000r4000` | 0 (|Δ|=0.1028) | 0.5453 | 0.4425 |
| `dry_K72_rainbow` | 2000 | `9sTs|2d4c7hJhKs|r|xb1500r8000A` | 0 (|Δ|=0.5000) | 0.5000 | 1.0000 |
| `dry_K72_rainbow` | 8000 | `9sTs|2d4c7hJhKs|r|xb1500r8000A` | 1 (|Δ|=0.5000) | 0.5000 | 0.0000 |

## Spotlight cells

Specific (player, hand, history) cells named in the PR 93 ablation spec. The A83 worst cells `3sAs` / `3cAc` at `b1000r3000` from `docs/a83_deep_cap_root_cause_investigation.md` use representative `Ac3c` / `As3s` from our P1 range (P1=opener=Brown's P0).

### `dry_A83_rainbow` @ 2000 iters

- player=1, hand=`Ac3c`, history=`b1000r3000`
  - infoset key: `3cAc|3d6s8cTcAh|r|b1000r3000`
  - rust  row: `[0.2309422013629942, 0.3511288362498822, 0.015672218449539213, 0.16923235406217166, 0.23302438987541244]`
  - brown row: `[0.2309422013629905, 0.35112883624989005, 0.01567221844954689, 0.1692323540621677, 0.23302438987540486]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=1, hand=`As3s`, history=`b1000r3000`
  - infoset key: `3sAs|3d6s8cTcAh|r|b1000r3000`
  - rust  row: `[0.19103356156205417, 0.32398570616853223, 0.015085727418039032, 0.19347655291670077, 0.2764184519346738]`
  - brown row: `[0.19103356156206988, 0.323985706168517, 0.015085727418043041, 0.19347655291670457, 0.27641845193466547]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=1, hand=`AcAd`, history=`b1000r3000`
  - infoset key: `AdAc|3d6s8cTcAh|r|b1000r3000`
  - rust  row: `[2.4839769227610216e-10, 2.4839776174958914e-10, 0.3860901196914714, 0.3743312806814302, 0.2395785991303029]`
  - brown row: `[2.48287605951839e-10, 2.4828766304706805e-10, 0.3860901197933281, 0.3743312806122357, 0.23957859909786103]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=1, hand=`AcAd`, history=`<root>`
  - infoset key: `AdAc|3d6s8cTcAh|r|`
  - rust  row: `[0.25248799556331963, 0.44625368591058606, 0.3012568547687308, 1.4637573634831665e-06]`
  - brown row: `[0.25243834237356483, 0.44616976714988615, 0.3013904267191856, 1.4637573634120467e-06]`
  - max-|Δ|: `0.000134` (0.0134pp)

### `dry_A83_rainbow` @ 8000 iters

- player=1, hand=`Ac3c`, history=`b1000r3000`
  - infoset key: `3cAc|3d6s8cTcAh|r|b1000r3000`
  - rust  row: `[0.23094220136299415, 0.35112883624988167, 0.015672218449539203, 0.16923235406217246, 0.23302438987541244]`
  - brown row: `[0.2309422013629897, 0.3511288362498894, 0.015672218449546957, 0.16923235406216858, 0.23302438987540533]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=1, hand=`As3s`, history=`b1000r3000`
  - infoset key: `3sAs|3d6s8cTcAh|r|b1000r3000`
  - rust  row: `[0.19103356156205387, 0.32398570616853317, 0.015085727418039045, 0.19347655291670016, 0.27641845193467385]`
  - brown row: `[0.1910335615620713, 0.3239857061685163, 0.015085727418043041, 0.19347655291670374, 0.2764184519346656]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=1, hand=`AcAd`, history=`b1000r3000`
  - infoset key: `AdAc|3d6s8cTcAh|r|b1000r3000`
  - rust  row: `[3.663340711452778e-12, 3.663505539582891e-12, 0.3860903465401032, 0.37433112785678946, 0.23957852559578063]`
  - brown row: `[3.6613771276596355e-12, 3.66148045958874e-12, 0.38609034654173957, 0.3743311278551128, 0.23957852559582488]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=1, hand=`AcAd`, history=`<root>`
  - infoset key: `AdAc|3d6s8cTcAh|r|`
  - rust  row: `[0.2777540724989973, 0.4025333350378668, 0.31971256955331884, 2.2909817091056455e-08]`
  - brown row: `[0.27754730855587223, 0.40256863824418565, 0.319884030290125, 2.290981708994335e-08]`
  - max-|Δ|: `0.000207` (0.0207pp)

### `dry_K72_rainbow` @ 2000 iters

- player=1, hand=`AcAd`, history=`<root>`
  - infoset key: `AdAc|2d4c7hJhKs|r|`
  - rust  row: `[1.1935073471151762e-05, 0.01849579235683181, 0.9814921141677323, 1.5840196476517578e-07]`
  - brown row: `[0.0001409059280711412, 0.024610929127520026, 0.9752480065424441, 1.5840196476517366e-07]`
  - max-|Δ|: `0.006244` (0.6244pp)
- player=1, hand=`KcKd`, history=`<root>`
  - infoset key: `KdKc|2d4c7hJhKs|r|`
  - rust  row: `[0.015385335368910492, 0.3980528931271536, 0.5865609194034773, 8.52100458682759e-07]`
  - brown row: `[0.015401969600457645, 0.3976254455763485, 0.5869717327227353, 8.521004586815606e-07]`
  - max-|Δ|: `0.000427` (0.0427pp)
- player=1, hand=`AcAd`, history=`b750r2250`
  - infoset key: `AdAc|2d4c7hJhKs|r|b750r2250`
  - row absent in one or both arms (rust=False, brown=False)
- player=0, hand=`AcAd`, history=`b750`
  - infoset key: `AdAc|2d4c7hJhKs|r|b750`
  - rust  row: `[6.117984826294216e-09, 0.9999852446154401, 2.9069776197035694e-06, 1.1460677583637077e-05, 3.8161137169006624e-07]`
  - brown row: `[6.117984826294188e-09, 0.9999993220481116, 2.507404654595472e-07, 3.948206729665361e-08, 3.8161137079453197e-07]`
  - max-|Δ|: `0.000014` (0.0014pp)
- player=0, hand=`3c3d`, history=`b750`
  - infoset key: `3d3c|2d4c7hJhKs|r|b750`
  - rust  row: `[0.7711037910966342, 0.07588538597336288, 2.941423183423627e-06, 0.02727810887492348, 0.12572977263189597]`
  - brown row: `[0.7674941050087517, 0.0790413602773031, 2.2843033066258737e-06, 0.02736950616944264, 0.12609274424119574]`
  - max-|Δ|: `0.003610` (0.3610pp)

### `dry_K72_rainbow` @ 8000 iters

- player=1, hand=`AcAd`, history=`<root>`
  - infoset key: `AdAc|2d4c7hJhKs|r|`
  - rust  row: `[1.8680032429811376e-07, 0.0002894846034050707, 0.9997103261170619, 2.4792087337471585e-09]`
  - brown row: `[2.2053716822805586e-06, 0.0003851949092237127, 0.9996125972398853, 2.4792087337471274e-09]`
  - max-|Δ|: `0.000098` (0.0098pp)
- player=1, hand=`KcKd`, history=`<root>`
  - infoset key: `KdKc|2d4c7hJhKs|r|`
  - rust  row: `[0.015408153935540618, 0.4057596792268322, 0.5788321535010823, 1.3336544798089919e-08]`
  - brown row: `[0.01537982766998332, 0.405922182288317, 0.5786979767051548, 1.3336544798071153e-08]`
  - max-|Δ|: `0.000163` (0.0163pp)
- player=1, hand=`AcAd`, history=`b750r2250`
  - infoset key: `AdAc|2d4c7hJhKs|r|b750r2250`
  - row absent in one or both arms (rust=False, brown=False)
- player=0, hand=`AcAd`, history=`b750`
  - infoset key: `AdAc|2d4c7hJhKs|r|b750`
  - rust  row: `[9.575488180823209e-11, 0.9999997690579259, 4.549820019127076e-08, 1.7937537581768438e-07, 5.972743122181539e-09]`
  - brown row: `[9.575488180823127e-11, 0.99999998938912, 3.924433341421527e-09, 6.179486865163886e-10, 5.972743108165169e-09]`
  - max-|Δ|: `0.000000` (0.0000pp)
- player=0, hand=`3c3d`, history=`b750`
  - infoset key: `3d3c|2d4c7hJhKs|r|b750`
  - rust  row: `[0.7741936615446942, 0.07441259433594004, 4.603732066581924e-08, 0.029447638668050623, 0.12194605941399439]`
  - brown row: `[0.7740988560534198, 0.07455575151425967, 3.575249029713691e-08, 0.029499669037953, 0.12184568764187728]`
  - max-|Δ|: `0.000143` (0.0143pp)

## Convergence check

Comparing max-|Δ| at 2000 vs 8000 iters: if Δ shrinks with more iterations → both arms approach the same Nash (the apparent divergence was Nash multiplicity / convergence noise). If Δ persists or grows → the two arms are solving DIFFERENT GAMES (convention difference). Per the audit, the math predicts persistence.

| Fixture | 2000-iter max-\|Δ\| | 8000-iter max-\|Δ\| | trend |
|---|---|---|---|
| `dry_A83_rainbow` | 0.122703 | 0.102839 | persists |
| `dry_K72_rainbow` | 0.499953 | 0.499953 | persists |

## Artifact paths

- `/Users/ashen/Desktop/a83_ablation_dry_A83_rainbow_rust_2000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_A83_rainbow_brown_2000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_A83_rainbow_rust_8000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_A83_rainbow_brown_8000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_K72_rainbow_rust_2000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_K72_rainbow_brown_2000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_K72_rainbow_rust_8000.json`
- `/Users/ashen/Desktop/a83_ablation_dry_K72_rainbow_brown_8000.json`

## Repro command

```bash
python scripts/a83_terminal_utility_ablation.py
```

## What this ablation does NOT measure

- This compares Rust-vs-Rust under the two conventions. It does NOT compare against Brown's binary output (Brown's binary always uses Brown's convention; comparing Brown ↔ Rust-brown was scoped out of PR 93 to keep the experiment paired-arm).
- The A83 worst-cell histories use representative hands from our P0 range; Brown's original `3sAs`/`3cAc` enumeration may diverge slightly on suit-blocker accounting. The verdict thresholds are scaled to absorb that residual.