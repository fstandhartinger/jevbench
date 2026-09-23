# JevBench v1.4.0 method

JevBench measures decision systems on the frozen v1.2 items and a fresh set of 308 sealed decisions. The public artifact contains aggregate accuracy and calibration only. The sealed item text, answer keys and per-item predictions are retained privately for official evaluation. An API flag means the system operator's endpoint received sealed item text, without answers.

## Official score

The four axes remain Intelligence, Calibration, Speed and Cost, each on a 0–100 scale. The Speed and Cost axes retain their v1.3.0 measurements and definitions. v1.3.0 Intelligence is the chance-corrected score on the frozen v1.2 items with weights easy 0.14, standard 0.28, judge 0.28 and hard 0.30.

Let `a` be accuracy on the 308 sealed items, `p` accuracy on the 231 public items, and `I13` the v1.3.0 Intelligence axis. Failed or invalid answers count as incorrect. The sealed chance baseline is 0.293:

```
Isealed = 100 × max(0, (a − 0.293) / (1 − 0.293))
Ibase   = 0.8 × I13 + 0.2 × Isealed
gap     = 100 × (p − a)                         # percentage points
I       = Ibase × (1 − max(0, gap − 25) / 100)
```

Calibration blends the v1.3.0 axis with the earlier v1.4 candidate calibration, which included the sealed items at a reference weight of 0.35:

```
C = C13 + (C14 − C13) × min(1, 0.2 / 0.35)
```

Label-only systems have no probability distribution; their Calibration contribution is zero. A system without a completed sealed measurement has no v1.4 score or rank.

The official composite is the equal-weight harmonic mean of the four axes, the power mean with `p = −1`. A zero axis produces a zero composite. Then apply these three multipliers independently:

```
if I < 50:     score ×= (I / 50)²
if Speed < 50: score ×= (Speed / 50)²
if Cost < 50:  score ×= (Cost / 50)²
```

The Intelligence multiplier keeps barely-above-chance systems from winning through speed and price. The Speed and Cost gates distinguish a Jev-class system from an intelligent but slow or expensive general LLM. The public-to-sealed gap penalty rewards generalization beyond the public items. No model-specific exception is applied.

## Sealed set and exposure

The 308 items span temporal and numeric decisions, subtle answer judgment, long policies, multi-hop lookup, abstention, probability, constrained tradeoffs, safety judgment, paraphrase sensitivity and adversarial traps. They were frozen before the evaluated systems saw them. The set's item text and golds are not part of this repository or the Benchmark Heaven client bundle. The public file reports aggregate accuracy, calibration, family summaries and exposure notes.

Operator APIs and demos necessarily received item text to answer it. Their rows carry a visible **API** flag and an exposure explanation. Self-hosted runs on evaluator-controlled pods do not get that flag. The flag reports exposure, not an allegation about training or use of the items.

The sealed part must be refreshed as the field changes: a static public set can saturate and enter training data. Any future replacement set should be frozen and its difficulty mix declared before entrant results are viewed. Do not treat the current sealed items as development, training or calibration material.

## Reproduction and limits

`results/v1.4/measurement-aggregates.json` is the publication-safe input, and `results/v1.4/round4-aggregate-rows.json` preserves earlier measurement details for newly added systems. Run `python3 scripts/v1.4/build.py` to regenerate `results/v1.4/jevbench-v1.4-results.json`; `pytest tests/test_v14_release.py` checks the selected formula and all rows. The input contains no sealed item text, answer keys, or per-item output.

The sealed set is unusually difficult for one-pass decision models. Small differences in sealed accuracy should not be read as proven pairwise superiority. Speed adjustments for self-hosted endpoints remain assumptions from v1.3.0. swanOne remains visible without a v1.4 rank because its sealed run was not completed; the unranked Needle 3 entries were also not re-measured.
