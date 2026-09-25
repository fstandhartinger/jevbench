# JevBench v1.4.2

This point release adds eleven newly measured systems and completes swanOne's sealed run. Every row was measured on the full protocol: the 534 frozen v1.2 decisions plus the 308 sealed v1.4 decisions. The [v1.4 method](METHOD-v1.4.md), the scoring formula and all v1.4.1 measurements are unchanged. The result artifact contains 93 systems, 89 of them ranked, and publishes aggregate measurements only.

## Top five

| Rank | System | JevBench Score | Intelligence | Calibration | Speed | Cost |
|---:|---|---:|---:|---:|---:|---:|
| 1 | decider-4b v2 (Mapika) | 64.13 | 49.4 | 75.0 | 92.9 | 60.9 |
| 2 | Jev 1.13.0 (TypeSafe AI) | 63.29 | 53.1 | 76.3 | 83.3 | 52.0 |
| 3 | JevK5 v0.2.0 | 62.04 | 48.9 | 74.5 | 91.1 | 59.5 |
| 4 | Cygnet (blockbrain, frozen Gemma-4-12B-it) | 61.76 | 49.5 | 74.9 | 90.7 | 52.8 |
| 5 | Hopper | 59.43 | 48.0 | 79.1 | 86.8 | 58.7 |

Jev 1.13.0 out-reasons decider-4b v2 (Intelligence 53.1 vs 49.4) and is better calibrated; decider-4b v2 leads on speed and cost. JevBench weighs the four axes equally; sort by Intelligence for raw reasoning.

decider-4b v2 passed the independent verification required for a new #1: its cost basis, public-versus-sealed gap, overlap with public items and composite score were checked and recomputed. Its author's private stage-2 training rows could not be audited; the row says so.

## New rows

| Rank | System | Score | Public accuracy | Sealed accuracy | Sealed items | Cost per 1,000 decisions (USD) |
|---:|---|---:|---:|---:|---|---|
| 1 | decider-4b v2 (Mapika) | 64.13 | 83.5% | 34.7% | offline | 0.0201 (estimate) |
| 4 | Cygnet (blockbrain, frozen Gemma-4-12B-it) | 61.76 | 87.9% | 33.8% | offline | 0.0374 (estimate) |
| 16 | Malkuth-4B (newfull5) | 44.45 | 74.9% | 23.4% | offline | 0.0192 (estimate) |
| 24 | Malkuth-2B (newfull5) | 38.93 | 69.7% | 24.4% | offline | 0.0192 (estimate) |
| 34 | swanOne (blockbrain, Qwen3.8-Flash-Next NVFP4) | 33.61 | 88.7% | 38.6% | offline | 0.1110 (estimate) |
| 42 | Kushal Patil — Gemma 4 31B IT (Autoloops) | 29.96 | 92.8% | 45.8% | **API** | 0.1363 (published rate) |
| 43 | Standard One 8B (Standard Thinking) | 29.07 | 76.6% | 26.6% | offline | 0.1044 (estimate) |
| 51 | typecastlm (Mikhail Gribov) | 25.28 | 77.9% | 29.9% | offline | 0.0213 (estimate) |
| 65 | JevAct (einptein, jev1-2b-v2) | 16.93 | 61.9% | 23.4% | **API** | 0.0155 (estimate) |
| 74 | Instinct (ZooWork, Qwen3.8-27B) | 11.45 | 86.6% | 35.1% | **API** | 0.3253 (estimate) |
| 78 | CLM-8B (Contrastive-LM) | 8.57 | 40.7% | 24.0% | offline | 0.0052 (estimate) |
| 82 | verdict-small (Manavarya09) | 5.69 | 53.7% | 28.9% | offline | 0.0013 (estimate) |

"Offline" rows ran in a network-disabled, read-only container on an evaluator-owned GPU pod or on our own CPU; no operator received the sealed items. Rows marked **API** identify operator endpoints that received the sealed item text without answers. The exact weights revisions, serving code and container images are recorded in each row's notes in the artifact.

## Prices

A system without a public, bookable price gets a labelled estimate: its own measured token usage at the public list price of its base model (or the nearest listed size class, named in the row). Author-announced tariffs and free tiers are not used. Instinct has no bookable price, so its Cost uses OpenRouter's model-level Qwen3.8-27B input price ($0.42 per million tokens, zero output for its direct-logit readout). Its free evaluation endpoint receives the standard ×2 latency adjustment for demo endpoints. The row is re-scored when a bookable price is published. Kushal Patil's row uses Autoloops' published per-token rates for the measured usage.

## Consistency correction before publication

The v1.4 Calibration input blends the v1.3 Calibration with the sealed-run Calibration, weighted by the 220 hard and 308 sealed items (308/528). Every v1.4.1 row uses this weight. The preliminary scores for Instinct, JevAct, verdict-small and the Autoloops Gemma row had used the sealed Calibration alone. The release applies the standard weight. Their scores moved by at most 0.51 points, and no rank in the top five is affected.

## Moved to v1.4.3

- imajev-4b, imajev-2b, imajev-9b, blink-4b, RYOTIDE-Qwen and RYOTIDE-Gemma (run 13, measured after this roster was fixed).
- JPT-4B, whose aggregate source file is still missing.
- APUS-OpenJev-v1-4B, whose price basis still has to be aligned with the other Qwen3.5-4B rows.
- VTX-JEV-1, Eikos 4B/27B and AutoJev-27B, which do not yet have official sealed rows.
- A price-basis refresh of earlier rows under the base-model price rule.

## Method and artifact

The complete [v1.4.2 result artifact](../results/v1.4.2/jevbench-v1.4.2-results.json) includes every row and aggregate field; `scripts/v1.4.2/build.py` builds it from `results/v1.4.2/measurement-aggregates.json` with the unchanged `jevbench/composite_v14.py`. No sealed task text, answers or per-item predictions are published.
