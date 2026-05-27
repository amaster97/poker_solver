# v1.8 NEON Vector Kernels Spec — SUPERSEDED

**Status:** SUPERSEDED 2026-05-25 by `docs/pr_proposals/v1_8_cross_platform_simd_spec.md`.

The original draft restricted v1.8 to Apple Silicon NEON. Because this repo is **public OSS**, the user pivoted v1.8 scope to **cross-platform** (NEON + SSE4.2 + AVX2 + scalar fallback) so non-aarch64 users (Intel Mac, Linux x86_64, Windows x86_64) also benefit from the perf release.

**Forward to:** [`v1_8_cross_platform_simd_spec.md`](v1_8_cross_platform_simd_spec.md).

The four kernels, the algorithmic analysis (transpose, sequential-sum parity, vmul+vadd vs FMA tradeoff), the W2.1 acceptance gate, and the M-series persona budget are unchanged. Only the SIMD abstraction (Option C: hand-written cfg-gated intrinsics with scalar fallback — generalized from PR 8 NEON to also cover x86_64 SSE/AVX) and the CI target matrix expand.

The companion roadmap `docs/v1_8_neon_implementation_roadmap.md` remains valid as the per-kernel algorithm reference; the cross-platform spec's §7.1 supplements it with ISA-specific intrinsic tables.

See revised cost (11-16 dev-days, ~2-3 weeks focused; was 7-12 days) and revised acceptance criteria (per-target bit-parity + per-target perf floors) in the new spec.
