# JevBench v1.4.3 — unpublished release draft

> Drafted 25 Sep 2026. **Do not merge, tag or publish before final roster, verification and Florian's approval.** Scores and ranks can change while outstanding official runs finish.

## Scope and evidence

The current candidate has **161 unique listings**: 93 carried from v1.4.2 and 68 v1.4.3 additions. It provisionally ranks **139**. Official new full-protocol rows use the frozen 534 decisions plus 308 sealed decisions on evaluator-owned offline pods, or an explicitly flagged API route. Owner aggregate and ROW SHA-256 pins are in `results/v1.4.3/input-manifest.json`; no sealed per-item predictions are included. The released v1.4 scoring implementation and four-axis formula are unchanged. The draft candidate digest is `943d35bbbe154c5b86794fa7142965734299d6de909923bf596a265b6a5e3b51`.

## Provisional public orders

| Rank | Composite | Score | Jev-class Capability headline | Capability |
|---:|---|---:|---|---:|
| 1 | Decision 4B v1.2 | 69.56 | Eikos-27B | 74.95 |
| 2 | Decision 4B v1.1 | 68.19 | Decision 4B v1.2 | 71.60 |
| 3 | JevK5 v0.3 4B | 67.51 | AutoJev-27B | 69.34 |
| 4 | Mica v0.1 4B | 66.62 | Decision 4B v1.1 | 69.15 |
| 5 | Plumb-4B | 65.84 | JevK5 v0.3 4B | 67.57 |

Both orders differ from live v1.4.2. Florian's prior approval does not cover v1.4.3. Independent Devin Opus 5.5 recomputed Eikos-27B and AutoJev-27B's axes, class membership and projected corrected Reka scores; its frozen input predates the corrected candidate, so final digest/order checking remains. Eikos's released training-data overlap screen covered 25,566 rows against 231 public items, leaving 146 other public-source items and any unreleased training data unchecked; the author evaluated public JevBench items and disclosed public results. AutoJev's 73,000-example training corpus is unpublished, so overlap is unverified; its 50-point public-to-sealed gap exceeds the historical 45.78-point median. These limits must appear in the approval preview. Mica and the composite entrants have earlier independent receipts. The local release job will create final interactive preview and screenshots after the roster freezes.

## Pricing and measured listings

The signed [pricing addendum](METHOD-v1.5-ADDENDUM-PRICING.md) (SHA-256 `2fc44459ef801d0627062f7eefd973df40772e8ac117727479748e4be4c220cc`) requires a public, bookable own-system list tariff with 30 days of qualifying history, plus a current public, bookable exact-base-model reference floor computed from measured tokens. The 30-day test applies to the own-system tariff; the base-model floor is a cutoff snapshot. This draft carries unchanged v1.4.2 row prices and scores until those rows are individually re-scored, per the addendum's scope sentence. The Jev tariff-anchor interpretation remains disclosed in the release job's scenario document.

New Qwen3.5-4B, 0.8B and 9B rows use corrected exact-base rates. imajev 2B/4B/9B use an independent tokenizer recount of every inference forward, replacing the undercounted per-item maximum. Exact Gemma 4 12B/26B/E2B/E4B, Ministral 3B, Typical Small, Bosun and Certus rate evidence is pinned in `results/v1.4.3/price-receipts/`. Seven Qwen3.8-27B additions use the active, undiscounted **OpenRouter Reka $0.092/M input/$4.40/M output** route; Bev and DIY each charge 534 owner-reported output tokens. The earlier Darkbloom rate recommendation was superseded by a correction receipt in the release job. The four API holds keep visible API flags and hide unsupported provisional cost, score and rank.

The draft has **17 explicit measured-unranked holds**, including two Gevva provenance holds. The other 15 cover unsupported exact-base rates or NeoJev's cached-prefix usage method. They remain visible as measured listings without a rank. `pricing_review_pending` and `provenance_review_pending` are empty because none of these holds is silently ranked. The older JevK5-9B v0.3 result is superseded by the measured v0.3.3 revision. `results/v1.4.3/pricing-review.json` gives key-level evidence and status.

## Verification and remaining gates

The Qwen3.8 price correction passed an independent focused code review before rebuild. OpenJeff pilot v1 then completed 842/842 on an evaluator-owned offline A100 pod; its frozen 410,384 input and zero output tokens use the paid NanoGPT/Aoru exact Gemma 4 12B base reference at $0.05/M input, yielding a labelled $0.038425468 estimate per 1,000 decisions and provisional rank 35 in this roster. Its owner aggregate/ROW/raw and first-party price receipts are hash-pinned in the builder, with an independent post-build CODE PASS. The release suite passed **41/41** (`PYTHONPATH=. python3 -m pytest -q tests/test_v143_release.py`). The `--final` builder gate refuses to write a publishable result without a receipt for Florian's approval of the changed top five. ProgramAsWeights and later intake, final roster integrity and leak scan, final candidate verification, preview approval, site PR review, merge, tag and live checks remain. No v1.4.3 release has been published.
