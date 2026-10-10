# Reproducing the published v1.4.2.x scores

`tests/test_published_reproduction.py` recomputes the published numbers in

- `results/v1.4.2.2/jevbench-v1.4.2.2-results.json`
- `results/v1.4.2.2/base-live-v1.4.2.1-results.json`
- `results/v1.4.2.1/jevbench-v1.4.2.1-results.json`
- `results/v1.4.2.1/base-live-v1.4.2-results.json`

from fields stored in the same file, using `jevbench/composite_v14.py` (protocol
`jevbench::v1.4`) and the v1.3 helpers it reuses. The stated tolerance is 0.01
points; today every checked value agrees to about 1e-14.

## Reproduced from stored fields

| Published field | Recomputed from |
| --- | --- |
| `jevbench_score`, every `presets[...]` | `axes` with `composite_v14.harmonic` and the file's preset weights (gates included) |
| `rank`, `rank_under[...]` | the recomputed scores of the `ranked` rows |
| `axes.intelligence` | `tiers` (easy, standard, judge, hard) via `composite_v13.intelligence`, then `sealed_accuracy` and `public_accuracy` via `composite_v14.intelligence` |
| `public_minus_sealed_gap_pp` | `public_accuracy`, `sealed_accuracy` |
| `speed.p50_s_adjusted`, `p95_s_adjusted` | raw latency and `endpoint_kind` via `composite_v13.adjusted_latency` |
| `axes.speed` | adjusted p50/p95 via `composite_v13.speed_point` |
| `axes.cost` | `cost.usd_per_1000` via `composite_v13.cost` |
| file constants | `axis_weights`, `tier_weights`, `presets`, `sealed_chance`, `sealed_weight` match the module constants |

## Gaps (not reproducible from the published files alone)

1. **Calibration axis.** `composite_v14.calibration` blends the v1.3 calibration
   with the v1.4 candidate calibration. The v1.3 calibration value is not stored in
   these files, so the blend cannot be recomputed. The test checks only that
   `axes.calibration` equals `calibration.score`.
2. **Speed without latency.** Four rows (`jevk5-v02`,
   `opensourcejev-qwen35-4b-q4km`, `qwen35-9b-jev-data-mix-v2`, `von-395m`) have
   `endpoint_kind: "unknown"` and no latency fields. Their speed axis is carried
   forward and cannot be recomputed. Their scores and ranks are still checked from
   the stored axes.
3. **Hard tier for the v1.4.2.2 addition.** Rows that publish only `hard_public`
   and `hard_heldout` (currently `imajev_4b`) are pooled with the 111/109 item
   counts from the published hard-tier description. That weighting is inferred from
   those counts. No file states it as a formula, but it matches to 1e-14.
4. **Tie order.** Where two ranked rows have exactly equal preset scores (the two
   `ninfer-qwen3.8-27b` rows under the no-calibration presets), the published order
   is not a documented rule. Ordering by key does not explain every file. The test
   accepts either order among exact ties.
5. **Unscored rows.** Label-only rows (`needle-3`, `needle-3-tools`) publish
   `axes: null` and no score. The test checks only that they are unranked.
6. **Not covered.** The `*-family-supplement.json` files, `sealed_aggregate`
   internals (ECE, TVD, per-family counts) and `v130_comparison_*`. These need
   per-item or v1.3-axis data that is not published.
