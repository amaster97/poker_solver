# GTO Solver Roadmap — Visual

Snapshot generated 2026-05-22. Integration tip: `6c438b8` (v0.5.0). PR 7 in flight.

Legend:
- ✅ shipped (merged to `integration`)
- 🚧 in flight (agents working)
- 📋 staged (spec'd + kickoff prompt ready)
- 📝 spec only (no impl prompts; deferred)

---

## 1. PR dependency graph

```mermaid
graph TD
    PR1["PR 1 ✅<br/>Kuhn + DCFR foundation<br/>maturin/PyO3 + diff test"]
    PR2["PR 2 ✅<br/>Leduc + Game trait"]
    PR3["PR 3 ✅<br/>HUNL tree builder<br/>action abstraction"]
    PR35["PR 3.5 ✅<br/>Push/fold charts<br/>(2-15 BB)"]
    PR35f["PR 3.5-followup ✅<br/>API completeness<br/>+ spec amendments"]
    PR4["PR 4 ✅<br/>Card abstraction<br/>EMD 256/128/64"]
    PR5["PR 5 ✅<br/>HUNL postflop (Python)<br/>+ memory profiler"]
    PR6["PR 6 ✅<br/>HUNL postflop (Rust)<br/>~24x speedup"]
    PR7["PR 7 🚧<br/>River-spot diff test<br/>vs noambrown"]
    PR8["PR 8 📋<br/>NEON SIMD<br/>+ public chance sampling"]
    PR9["PR 9 📋<br/>HUNL preflop<br/>(both tiers)"]
    PR10a["PR 10a 📋<br/>NiceGUI scaffold<br/>+ mock solver"]
    PR10b["PR 10b 📋<br/>UI real-solver bindings"]
    PR11["PR 11 📋<br/>Library mode<br/>+ macOS .dmg packaging"]
    PR12["PR 12 📝<br/>3-handed postflop<br/>(stretch, post-v1)"]

    PR1 --> PR2
    PR2 --> PR3
    PR3 --> PR35
    PR3 --> PR4
    PR35 --> PR35f
    PR4 --> PR5
    PR5 --> PR6
    PR6 --> PR7
    PR6 --> PR8
    PR5 -.types.-> PR10a
    PR8 --> PR9
    PR9 --> PR10b
    PR10a --> PR10b
    PR10b --> PR11
    PR9 --> PR12
    PR10b --> PR12

    classDef shipped fill:#c8e6c9,stroke:#2e7d32,color:#000
    classDef inflight fill:#fff9c4,stroke:#f57f17,color:#000
    classDef staged fill:#bbdefb,stroke:#1565c0,color:#000
    classDef speconly fill:#e0e0e0,stroke:#616161,color:#000

    class PR1,PR2,PR3,PR35,PR35f,PR4,PR5,PR6 shipped
    class PR7 inflight
    class PR8,PR9,PR10a,PR10b,PR11 staged
    class PR12 speconly
```

---

## 2. Version milestone mapping

```mermaid
graph LR
    M03["v0.3.x ✅<br/>PR 1, 2, 3, 3.5, 3.5f<br/>Foundations + tree builder"]
    M04["v0.4.0 ✅<br/>PR 4 + PR 5<br/>Card abstraction + Python postflop"]
    M05["v0.5.0 ✅<br/>PR 6<br/>Rust postflop port"]
    M051["v0.5.1 📋<br/>PR 7 + PR 8<br/>River-diff parity + SIMD perf"]
    M06["v0.6.0 📋<br/>PR 9 + PR 10a<br/>Preflop solver + UI scaffold"]
    M10["v1.0.0 📋<br/>PR 10b + PR 11<br/>Real UI + packaged .dmg"]

    M03 --> M04 --> M05 --> M051 --> M06 --> M10

    classDef shipped fill:#c8e6c9,stroke:#2e7d32,color:#000
    classDef staged fill:#bbdefb,stroke:#1565c0,color:#000

    class M03,M04,M05 shipped
    class M051,M06,M10 staged
```

---

## 3. Timeline estimate (3-4 weeks to v1)

Assumes ~1 PR landing per 2-3 days under autonomous fan-out; UI track runs in parallel with engine perf.

```mermaid
gantt
    title GTO Solver — Roadmap to v1.0.0 (estimate, MacBook-only)
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Shipped
    PR 1-3 foundations (v0.3.x)    :done, p13, 2026-05-15, 2d
    PR 3.5 push/fold + followup    :done, p35, 2026-05-17, 1d
    PR 4 card abstraction          :done, p4,  2026-05-18, 1d
    PR 5 postflop Python (v0.4.0)  :done, p5,  2026-05-19, 1d
    PR 6 Rust port (v0.5.0)        :done, p6,  2026-05-20, 2d

    section In flight
    PR 7 river-diff parity         :active, p7, 2026-05-22, 2d

    section Engine perf
    PR 8 NEON + chance sampling    :p8, after p7, 3d

    section Preflop + UI (parallel)
    PR 9 HUNL preflop              :p9, after p8, 5d
    PR 10a NiceGUI + mock solver   :p10a, after p7, 4d

    section v1 integration
    PR 10b real-solver bindings    :p10b, after p9 p10a, 3d
    PR 11 packaging + .dmg (v1)    :crit, p11, after p10b, 2d

    section Post-v1 stretch
    PR 12 3-handed postflop        :p12, after p11, 5d
```

---

## 4. Critical path notes

The critical path runs PR 7 -> PR 8 -> PR 9 -> PR 10b -> PR 11. PR 10a (UI scaffold) parallelizes with PR 8 + PR 9 because it depends only on PR 5 data types, not on the Rust perf tier or preflop solver.

PR 12 (3-handed) is intentionally past the v1 line — flagged as approximate equilibrium (CFR has no convergence guarantee for >= 3 players), so it stays a stretch goal regardless of timeline slack.

Load-bearing caveat (carried over from PLAN §6): no production-scale HUNL solve has actually been run yet. The ✅ tags through PR 6 reflect code correctness + Rust micro-bench speedup, not the first 200K-iter MC build (~10 hr wall-clock) which is still pending.
