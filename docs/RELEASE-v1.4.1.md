# JevBench v1.4.1

This point release adds six systems omitted from the frozen v1.4.0 set. It retains the same 308 sealed decisions, scoring formula, and v1.4.0 measurements. The result artifact contains 82 systems, 77 ranked rows, and aggregate measurements only.

## New rows

| Rank | System | JevBench Score | Public accuracy | Sealed accuracy |
|---:|---|---:|---:|---:|
| 7 | Jev-Omni | 51.34 | 88.7% | 32.1% |
| 13 | spark-s1-4b-v6 | 44.62 | 79.2% | 26.6% |
| 25 | Decision 2B | 35.80 | 75.3% | 26.0% |
| 33 | Decision Fast | 32.49 | 63.2% | 25.6% |
| 37 | lev-350m | 28.50 | 58.4% | 25.0% |
| 60 | Qwen3.5-0.8B Decision Model | 14.54 | 59.3% | 34.7% |

The approved top five is unchanged: Jev 1.13.0 (63.29), JevK5 v0.2.0 (62.04), Hopper (59.43), Winnow-12B Q8 (55.58), and reflex 4B (53.99). All six new systems were measured offline on the sealed items, so none has an API exposure flag.

## Measured artifacts

| System | Weights revision | Inference source |
|---|---|---|
| Decision 2B | `flymy-ai/decision-2b-preview` at `df57b75db927acc9ad91ec8115508c1e487086eb`; base `openbmb/MiniCPM5-2B` at `12a3808a956f869c767195e9266b59c4d21d92e2` | Pinned FlyMy code and local weights |
| Decision Fast | `flymy-ai/decision-fast-preview` at `4225d41c66119fe28e95a2631bb0103decae6d56`; base `Qwen/Qwen3-0.6B-Base` at `da87bfb608c14b7cf20ba1ce41287e8de496c0cd` | Pinned FlyMy code and local weights |
| Jev-Omni | `akhilaaa3/Jev-Omni` at `c050d51354147985d13286cf4acf90f562f2c631` | Pinned model weights |
| spark-s1-4b-v6 | `abhishek085/spark-s1-4b-v6` at `93d49ddbfb29212e3296635a75a3e80cf69da027` | `open-spark-jev` at `30ac6d89b7fa36c644cf86aac68f35c1d276a919` |
| lev-350m | `franckverrot/lev-350m` at `ab08ad8b8f346994d983152917e114224f6adac7`; base `LiquidAI/LFM2.5-350M` at `9e6c6ccf47cd318696e137d381a7ded8fe4df09f` | Lev code at `c48a945dbf629998d7458dcc5c16f58df964db94` |
| Qwen3.5-0.8B Decision Model | `mghafiri/qwen3.5-0.8B-decision-model` at `4a9939034a27006b4b62ad5aed65a90b82d0d350` | JevLite source at `11792cc7cf1a34cf2d7087e4558ffc39f0e81081`; offline CPU inference |

The 66.65 v1.3.0 public result for spark-s1-4b-v6 and this v1.4.1 row use the standard `abhishek085/spark-s1-4b-v6` repository revision above. The run receipt does not identify the separate `abhishek085/spark-s1-4b-v6-nvfp4` repository.

The Qwen row uses the existing completed 534-decision measurement plus its original offline run on the 308 sealed decisions. Its local result was not rerun for this release.

## Method and artifact

The [v1.4 method](METHOD-v1.4.md) is unchanged. The complete [v1.4.1 result artifact](../results/v1.4.1/jevbench-v1.4.1-results.json) includes every row and aggregate field. No sealed task text, answers, or per-item predictions are published.
