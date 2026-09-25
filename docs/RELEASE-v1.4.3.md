# JevBench v1.4.3

> Draft: prepared 25 Sep 2026, not published. The top five changes, so the release waits for approval of the preview.

This point release adds sixteen newly measured systems and lists one partial run without ranking it. Every ranked addition was measured on the full protocol: the 534 frozen v1.2 decisions plus the 308 sealed v1.4 decisions. The [v1.4 method](METHOD-v1.4.md), the scoring formula (`jevbench/composite_v14.py`, unchanged) and all 93 v1.4.2 rows are unchanged; only their ranks move. The artifact has 110 systems, 105 of them ranked, and publishes aggregate measurements only.

## Top five

| Rank | System | JevBench Score | Intelligence | Calibration | Speed | Cost |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Decision 4B v1.2 (FlyMyJev, Qwen3.5-4B + LoRA) | 70.96 | 58.6 | 84.6 | 93.5 | 59.5 |
| 2 | Decision 4B v1.1 (FlyMyJev, Qwen3.5-4B + LoRA) | 69.52 | 55.8 | 82.5 | 93.5 | 59.5 |
| 3 | Plumb-4B (crh225, JevK5 v0.2 + LoRA) | 67.09 | 53.0 | 75.5 | 93.5 | 59.5 |
| 4 | imajev-4b (mohit67890, Qwen3.5-4B + LoRA) | 65.79 | 53.4 | 76.4 | 81.7 | 59.7 |
| 5 | decider-4b v2 (Mapika) | 64.13 | 49.4 | 75.0 | 92.9 | 60.9 |

Intelligence among the top five: Decision 4B v1.2 58.6, Decision 4B v1.1 55.8, imajev-4b 53.4, Plumb-4B 53.0, decider-4b v2 49.4. Jev 1.13.0 (53.1, rank 6) is out-reasoned by three of them. Decision 4B v1.2 leads both the JevBench Score and Intelligence among the top five. Rows outside the top five reason better still (up to 97.4, GPT-6 Luna, rank 47), held back by its Speed and Cost. JevBench weighs the four axes equally; sort by Intelligence for raw reasoning.

The v1.4.2 sentence "Jev 1.13.0 out-reasons decider-4b v2" is no longer the whole picture, so it has been replaced. The new sentence is generated from the artifact and checked by the tests. Each new top-five entrant passed an independent check: its cost basis, its public-versus-sealed gap, its overlap with public items and an exact recomputation of its composite score.

## New rows

| Rank | System | Score | Public | Sealed | Cost per 1,000 decisions (USD) |
|---:|---|---:|---:|---:|---|
| 1 | Decision 4B v1.2 (FlyMyJev) | 70.96 | 88.3% | 42.9% | 0.0224 (estimate) |
| 2 | Decision 4B v1.1 (FlyMyJev) | 69.52 | 87.9% | 39.9% | 0.0224 (estimate) |
| 3 | Plumb-4B (crh225) | 67.09 | 89.6% | 38.0% | 0.0224 (estimate) |
| 4 | imajev-4b (mohit67890) | 65.79 | 84.8% | 37.0% | 0.0220 (estimate) |
| 9 | Eikos-4B (caiovicentino1) | 61.16 | 84.8% | 32.5% | 0.0224 (estimate) |
| 12 | RYOTIDE-Gemma (csabag) | 55.07 | 79.7% | 31.2% | 0.0158 (estimate) |
| 13 | blink-4b (thegovind) | 54.30 | 86.1% | 29.5% | 0.0224 (estimate) |
| 15 | imajev-2b (mohit67890) | 53.32 | 78.8% | 29.2% | 0.0147 (estimate) |
| 16 | JPT-4B (kirp) | 53.24 | 88.7% | 32.5% | 0.0214 (estimate) |
| 23 | imajev-9b (mohit67890) | 45.64 | 85.3% | 34.1% | 0.0734 (estimate) |
| 29 | APUS-OpenJev-v1-4B | 41.73 | 79.7% | 25.6% | 0.0219 (estimate, repriced) |
| 35 | RYOTIDE-Qwen (csabag) | 39.65 | 79.7% | 28.6% | 0.0235 (estimate) |
| 51 | Nemotron Diffusion 8B (pst2154) | 31.97 | 75.3% | 23.4% | 0.0317 (estimate) |
| 84 | AutoJev-27B (denis-pplx) | 13.08 | 87.0% | 37.0% | 0.3002 (estimate) |
| 85 | Eikos-27B (caiovicentino1) | 12.92 | 91.8% | 52.6% | 0.3130 (estimate) |
| 100 | VTX-JEV-1 (VTXAI) | 0.55 | 30.7% | 32.8% | 0.0020 (estimate) |
| – | GLiNER2.5-Decide (Fastino), partial run, not ranked | – | – | – | – |

All of these rows ran offline, in a network-disabled, read-only container on an evaluator-owned GPU pod. No operator received the sealed items. GLiNER2.5-Decide is listed without a rank: it did not answer the long hard-tier documents within the 120-second per-request limit, so 524 of its 842 decisions, including every sealed item, were never attempted.

## Prices and corrections

- **APUS-OpenJev-v1-4B** was priced at $0.10/M, the price of its Qwen3.5-9B sibling. It is now priced at the DeepInfra Qwen/Qwen3.5-4B list price of $0.03/M, like every other Qwen3.5-4B row. The same measured prompt tokens give $0.0219 per 1,000 decisions (was $0.0729). That raises its Cost axis from 44.1 to 59.8 and its score from 30.08 to 41.73. DeepInfra marks that listing as deprecated but still lists the price.
- **Instinct** is unchanged. ZooWork now shows US$0.03/M input on its pricing page, but labels it an "announced tariff" for a free preview in which "billing has not yet been enabled". That is not a bookable price, so the base-model estimate ($0.42/M, Qwen3.8-27B) stays. The row will be re-scored when billing starts.
- **Decision 4B v1.1/v1.2 notes**: the measurement row repeated the author's statement that no JevBench item was used for model selection. The package's own `reports/gates.json` shows that its release gates included thresholds on the 231 public items. The notes now say so.
- **JPT-4B** (measured in run 12) was left out of v1.4.2 because its aggregate file was missing. That file is a fixed projection of the measurement row, and it was re-created with the measurement job's own exporter. The row's hash matches the job's manifest, and the score is unchanged at 53.24.

## Method and artifact

`scripts/v1.4.3/build.py` builds `results/v1.4.3/jevbench-v1.4.3-results.json` from the v1.4.2 artifact, `results/v1.4.3/addition-sources.json` and `results/v1.4.3/addition-rows.json`. `results/v1.4.3/input-manifest.json` records the SHA-256 of every source file. No sealed task text, answers or per-item predictions are published.
