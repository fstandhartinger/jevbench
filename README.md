# JevBench

Combination experiments (confidence cascades, committees, and real-sample best-of-n) are
reported in [RESULTS-COMBINATIONS.md](RESULTS-COMBINATIONS.md). None changed the ranked board.

A benchmark for **Jev-class decision models**: you hand the model a piece of state
and a bounded rubric, and it hands back a typed answer, ideally with a probability for
every option. No prose, no parsing, no "as an AI language model".

JevBench is [Benchmark Heaven](https://benchmarkheaven.com)'s own benchmark. It is not
affiliated with or endorsed by TypeSafe AI, whose Jev model is one of the systems
measured here.

## v1.4.0: fresh sealed decisions and a Jev-class score (current)

**[Live board](https://benchmarkheaven.com/jev-models)** · [v1.4 method](docs/METHOD-v1.4.md) ·
[aggregate results](results/v1.4/jevbench-v1.4-results.json) · [changelog](CHANGELOG.md)

The official score blends 20% chance-corrected Intelligence from 308 fresh sealed decisions with 80% of the v1.3.0 Intelligence axis. Calibration is blended toward the sealed-inclusive measurement. The four axes use an equal-weight harmonic mean. A public-to-sealed accuracy gap above 25 percentage points reduces Intelligence; the existing low-Intelligence penalty remains, and Speed and Cost each receive a quadratic gate below 50. Their underlying measurements are unchanged from v1.3.0.

| Rank | System | JevBench Score |
|---:|---|---:|
| 1 | Jev 1.13.0 (TypeSafe AI) | 63.29 |
| 2 | JevK5 v0.2.0 | 62.04 |
| 3 | Hopper | 59.43 |
| 4 | Winnow-12B Q8 | 55.58 |
| 5 | reflex 4B (kshetrajna12) | 53.99 |

Only aggregates are published for the sealed items. Rows with an **API** flag identify operator endpoints that received the item text without answer keys. swanOne remains visible without a v1.4 rank because its sealed run was not completed. The public half can be trained on or selected against, so the held-out private part will need to evolve as the field changes.

## v1.3.0: previous scoring release

**[Results -> `RESULTS-v1.2.md`](RESULTS-v1.2.md)** · artifact [`results/v1.2/jevbench-v1.2-results.json`](results/v1.2/jevbench-v1.2-results.json) ·
interactive: [benchmarkheaven.com/jev-models](https://benchmarkheaven.com/jev-models) · how the hard tier was made: [`datasets/HARD-TIER.md`](datasets/HARD-TIER.md)

**JevBench Score** = chance-corrected Intelligence, Calibration, Speed, Cost — 25 % each, geometric mean. Below 50 Intelligence, multiply the score by `(Intelligence / 50)²`.

| Axis | Score 0-100 |
|---|---|
| **Intelligence** | `(accuracy - chance) / (1 - chance)` per tier, clipped at 0; hard 30 %, easy 14 %, standard 28 %, judge 28 % |
| **Calibration** | hard tier: ECE + fidelity to exact gold distributions (label-only systems: none, counts as 0) |
| **Speed** | mean of score(p50), score(p95); score(s) = 100 - 20 log10(s / 0.1 s): 0.1 s = 100, each 10x slower -20 |
| **Cost** | 100 - 30 log10($ per 1,000 decisions / $0.001): $0.001 = 100, each 10x more expensive -30 |

> **The Cost column is US dollars per 1,000 DECISIONS, not per 1,000 tokens.** One decision is a whole question: its
> state, its rubric and its options — hundreds to thousands of input tokens.
> Jev 1.13.0 reads 950 input tokens per decision on average over the 534 v1.2 decisions. At its public tariff of $0.042 per MILLION input tokens (output tokens are free, https://docs.typesafe.ai/models), 1,000 decisions therefore cost 950 x 1,000 x $0.042 / 1,000,000 = $0.0399. That is what the Cost column shows: $0.0399 per 1,000 decisions, not per 1,000 tokens.

> Latency of self-hosted and demo endpoints is adjusted ×2 (+0.15 s on our own servers) to approximate production load —
> an assumption, not a measurement; raw measurements are in [`RESULTS-v1.2.md`](RESULTS-v1.2.md) and the artifact.
> Why, and its limits: [Limits, stated plainly](#limits-stated-plainly).

- **Accuracy by subject topic** (math, coding, rules & law, finance, support & operations, everyday language, safety &
  security): [`datasets/TOPICS.md`](datasets/TOPICS.md) and `results/v1.2/jevbench-v1.2-topics.json` — aggregates only,
  not part of the score.

- **220 hard decisions** (111 public in `datasets/public/hard.jsonl`, 109 held out), written by Claude Opus 5 and GPT-5.6 Sol,
  cross-reviewed, frozen and hashed before any system ran; 534 decisions per system in total.
- Top of the ranking (48 ranked rows): **Jev 1.13.0 (TypeSafe AI) 74.4** · SemIf, formerly OpenJev (Qwen3.5-4B, TheoLeeCJ) 73.1 · djev (Maisa, diffusion-gemma) 73.0 · Winnow-12B Q8 71.2 · reflex 4B (kshetrajna12) 70.3. Qwen3.8 27B and Needle 3 (both modes) are partial runs, shown without a rank.
- djev is self-hostable: [`Davipar/djev-dev`](https://github.com/Davipar/djev-dev) is Apache-2.0 code over Google's Apache-2.0 DiffusionGemma weights. It is an inference method, not a separately trained model, and adds no weights of its own. `djev-spark` is another DiffusionGemma structured-read runtime, not another model row.
- **Honorable mention, not ranked: classifier.dev (fast tier) 83.6.** A service that runs another entrant's model is
  listed with all of its scores and axes, but is not ranked against the models — its fast tier *is* Jev
  ("The fast tier is Jev, TypeSafe's decision model", [classifier.dev/benchmark](https://classifier.dev/benchmark)), so
  ranking it would rank Jev's model against Jev's model at a different price. See
  [Honorable mentions](RESULTS-v1.2.md#honorable-mentions--services-built-on-another-entrants-model).
- Scoring code: [`jevbench/composite_v13.py`](jevbench/composite_v13.py); the final artifact is rebuilt from the frozen measurements by
  [`scripts/v1.2/finalize.py`](scripts/v1.2/finalize.py), charts by [`scripts/v1.2/charts.py`](scripts/v1.2/charts.py).
  Per-task outcomes (public items): [`results/v1.2/jevbench-v1.2-per-task.json`](results/v1.2/jevbench-v1.2-per-task.json).
- open-alternative-jev is ranked with the author's own option order (`A. yes, B. no`). With the options in reverse order
  (`A. no, B. yes`) the same model scored 21 % instead of 72 % on answer-judging items — small models are very sensitive to
  option order. Both runs: [`results/v1.2/runs/open-alternative-jev/`](results/v1.2/runs/open-alternative-jev/).

### Other mentions and diagnostics

- [stuntdouble](https://github.com/ReallyArtificial/stuntdouble) is an independent shadow-proxy and replay companion
  that can import JevBench's public hard items to compare local decision models. It is a tool, not a JevBench entrant;
  its [example report](https://github.com/ReallyArtificial/stuntdouble/tree/main/reports/2026-09-22-m3pro-kev0.8b-vs-laya)
  is not an official JevBench result.
- The [option-order robustness analysis in issue #40](https://github.com/fstandhartinger/jevbench/issues/40) is a
  separate diagnostic on public choice items. It does not change the canonical task order or official scores.

![JevBench v1.3.0 — JevBench Score](results/v1.2/charts/main-score.png)

### What changed in the score

A system that is cheap and fast but barely better than guessing could rank high; intelligence is now measured above
chance, and systems below half-way get a growing penalty. The task set, Calibration, Speed, Cost and who is eligible
for a rank are unchanged.

**Revision log of v1.2 (19 Sep 2026; items and answers never changed after the freeze):**
v1.2-wip (tag `v1.2-wip`) hard tier + calibration sub-score, Balanced 33:33:33 Main Score with hard 50 % of Capability;
**v1.2 final (tag `v1.2`): 4 axes, geometric mean** — Intelligence (hard 30 %), Calibration, Speed, Cost at 25 % each; Speed 20 points
and Cost 30 points per decade; latency of non-production endpoints adjusted ×2 (+0.15 s on our own servers, an assumption);
one open-alternative-jev row (author's option order); Needle 3 options-as-tools priced on Needle 3's per-token basis ($0.0162 est.).
The earlier weightings are kept as views, recomputed the same way, and are not the JevBench Score.
**v1.2.1 (tag `v1.2.1`): added djev** (Maisa's diffusion-gemma Jev implementation, api.djev.dev) — all 534 decisions including the
held-out items, one request at a time through its production API (no latency adjustment), scored with the unchanged v1.2 rules.
Cost uses djev's announced price ($0.035 per million input tokens, output free), which is not charged yet (free preview).
Adapter: [`jevbench/adapters/djev.py`](jevbench/adapters/djev.py); row: [`results/v1.2/additions/djev.json`](results/v1.2/additions/djev.json).
No other row changed; ranks below #2 move down one.

**v1.2.2 (tag `v1.2.2`): five systems readers asked for** — [Laya](https://huggingface.co/convaiinnovations/laya) (Convai Innovations,
ModernBERT-large 421M), [jeff](https://github.com/logan-markewich/jeff) (Logan Markewich, GLiFormer 400M),
[GLiNER2](https://github.com/fastino-ai/GLiNER2) (Fastino, gliner2.5-base), [openJev Verdict](https://github.com/Heman10x-NGU/openJev-verdict-2.0)
(heman10x, 151M) and [classifier.dev](https://classifier.dev) (fast tier). Each ran all 534 decisions including the held-out ones, with the
unchanged v1.2 scoring. The four open systems ran on our CPU (4 threads) and carry the usual ×2 + 0.15 s latency adjustment; classifier.dev is a
production API and carries none. Every mapping — above all GLiNER2's label scores → one distribution — was written down before the runs:
[`docs/v1.2-additions.md`](docs/v1.2-additions.md). Adapters: [`jevbench/adapters/`](jevbench/adapters/) (`laya_local`, `gliner2_local`,
`verdict_local`, `classifier_dev`; jeff uses the existing `typesafe` adapter against its own server). Rows:
[`results/v1.2/additions/`](results/v1.2/additions/). No other row changed.
ProgramAsWeights was also requested and is prepared (`paw_local`), but its hosted compiler only keeps a program private for a signed-in
account, and compiling 223 held-out rubrics into public programs would publish them; it is therefore not in this revision.

**v1.2.3 (tag `v1.2.3`): cost correction.** Every row's price was recomputed so that each of the 534 decisions is counted once and
priced once. Three arithmetic mistakes were fixed — the 242-decision standard+judge run was averaged twice in the v1.1-tier price
(556 rows instead of 314); rows priced from the gemini-3.1-flash-lite token counts used that run's standard+judge-only average
(452 input tokens per decision) for all 314 v1.1 decisions instead of its average over all 314 (383); and requests whose answer came
back unparseable were left unpriced although the provider billed them (9 DeepSeek V4.1 Flash decisions).
**No tariff was wrong**, no measurement, item or answer changed, and no rank changed. Fifteen rows become 1.5–11 % cheaper
(JevBench Score up by at most 0.2 points); DeepSeek V4.1 Flash becomes 2.6 % more expensive. The correction also spells the unit out
everywhere: the Cost column is dollars **per 1,000 decisions**, never per 1,000 tokens. Per-row figures and their derivation:
[`results/v1.2/cost-correction-v1.2.3.json`](results/v1.2/cost-correction-v1.2.3.json); check:
[`tests/test_cost_correction.py`](tests/test_cost_correction.py).

**v1.2.4 (tag `v1.2.4`): classifier.dev leaves the ranking and becomes an honorable mention.** New general rule: *a
service that runs another entrant's model is listed, but not ranked against the models.* classifier.dev is not its own
model — its own pages say "The fast tier is Jev, TypeSafe's decision model"
([classifier.dev/benchmark](https://classifier.dev/benchmark), read 20 Sep 2026) and the API answers with
`"model": "jev-1.13.0"` — so ranking it put the same model in the list twice, once at TypeSafe's per-token tariff and
once at classifier.dev's flat plan. What it adds is that price and, on its **smart** tier (which we did not measure),
an orchestration layer: "The smart tier is Jev plus a reasoning model re-asking only the answers Jev put under 0.7
confidence" — escalation on low confidence, a model cascade, not best-of-N, self-consistency or a committee.
Its row keeps every number, axis, cost basis, radar and per-task outcome and carries no rank; **Jev 1.13.0 is #1** and
every other row moves up one place. No measurement and no score changed. The full note, with the price caveat and the
one place where the fast tier measurably differs from Jev, is in
[`RESULTS-v1.2.md`](RESULTS-v1.2.md#honorable-mentions--services-built-on-another-entrants-model); check:
[`tests/test_honorable_mentions.py`](tests/test_honorable_mentions.py).

**v1.2.5 (tag `v1.2.5`): the kev family.** Added [kev](https://github.com/jaredpalmer/kev) 0.5B and its 0.6B, 4B and 8B research previews. Each ran all 534 frozen decisions through the author's native TypeSafe-compatible endpoint in BF16 on one RTX 3090, with zero failed requests. kev 0.6B enters highest at #9 with 66.7; 0.5B is #15 with 63.1, 4B #16 with 62.2, and 8B #18 with 58.3. The larger checkpoints improve Intelligence but lose points on calibration and estimated hosted cost. No earlier row changed. Full method: [`docs/v1.2-additions.md`](docs/v1.2-additions.md); rows: [`results/v1.2/additions/`](results/v1.2/additions/).

**v1.2.6:** Added openJev Verdict 1.4 as its own row (same weights, fixed author engine) and the reachable, identified SimpleJev public-demo configurations. Every entrant ran the unchanged 534 frozen decisions including the hard tier; earlier Verdict and all other rows remain unchanged. Full method and endpoint conditions: [`docs/v1.2-additions.md`](docs/v1.2-additions.md).

**v1.2.7 (tag `v1.2.7`): two more GLiNER2 checkpoints, and a submitted endpoint measured on the public items.**
Added [GLiNER2.5 small](https://huggingface.co/fastino/gliner2.5-small-v1) at 62.1 (#21) and [GLiNER2.5 multi](https://huggingface.co/fastino/gliner2.5-multi-v1) at 63.1 (#19) — both ran all 534 frozen decisions on our CPU with the same mapping as the existing GLiNER2 row
(gliner2.5-base), re-checked on each checkpoint before its run. Also added **jqv** at 67.2, a stock
[Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B) read as a decision model, submitted with a public endpoint in
[issue #6](https://github.com/fstandhartinger/jevbench/issues/6): it is a **partial row, shown but not ranked**,
because its endpoint runs on the submitter's own machine and this round stopped sending held-out items to an
endpoint a submitter operates. It answered 425 of 534 decisions — everything except the 109 held-out hard items —
and on the public items it reproduced the submitter's own numbers exactly (easy 1.000, standard 0.958, hard 0.622).
Mappings, endpoint conditions and cost bases were committed before any row was aggregated and before the published
GLiNER2.5 runs started ([`docs/v1.2-additions-run3.md`](docs/v1.2-additions-run3.md)); jqv's run had begun about ten
minutes earlier, because its endpoint was temporary, but it needs no mapping and is priced at its base model's public
tariff. No other row changed.

**v1.2.8 (tag `v1.2.8`): 10 more requested systems, and jqv complete.** Every entrant ran all 534 frozen decisions
through its author's own server, one request at a time, scored with the unchanged rules: [reflex 4B](https://github.com/kshetrajna12/reflex) 71.7 (#5), [decision-machine-1](https://www.milliseconds.ai) 71.5 (#6), [jqv](https://github.com/Octalab-Inc/jqv) 70.1 (#8), [decider-35b-a3b](https://huggingface.co/Mapika/decider-35b-a3b) 68.9 (#10), [OpenDecision](https://github.com/deepanwadhwa/OpenDecision) 67.0 (#14), [decider-2b](https://huggingface.co/Mapika/decider-2b) 64.6 (#20), [reflex-27b](https://github.com/kshetrajna12/reflex) 64.2 (#22), [jev-local](https://github.com/us/jev-local) 63.8 (#23), [LitJev](https://github.com/zhengxuyu/litjev) 63.7 (#25), [Bespoke Nimble 9B (re-run)](https://github.com/bespokelabsai/nimble) 61.8 (#30), [GLiNER2 large](https://huggingface.co/fastino/gliner2-large-v1) 50.5 (#36). decision-machine-1
is a closed decision model behind milliseconds.ai's production API and gets its own class ("closed decision model");
the rest ran on our RunPod GPUs, GLiNER2 large on our CPU. jqv (issues #6 and #9) was re-run in full on our own GPU from
its now-public serving code, so its v1.2.7 partial row is replaced by a complete, ranked one. Bespoke Nimble 9B was re-run
after Bespoke Labs raised its prompt limit to 8,192 tokens: hard tier 43.6 % → 65.5 %, yet its score fell from 63.7 to
61.8, because the long items that used to fail are now answered and priced, and its pod was farther from our server.
Every GPU pod this round was in Canada, so those rows' Speed includes a transatlantic network path from Germany. Mappings, endpoint
conditions and cost bases were pushed before the runs: [`docs/v1.2-additions-run4.md`](docs/v1.2-additions-run4.md),
[`docs/v1.2-additions-run4b.md`](docs/v1.2-additions-run4b.md). Not measurable this round: Werr (its server imports a
module missing from the public repository) and DIY Jev (the repository answers 404). No earlier measurement changed.

**v1.2.9 (tag `v1.2.9`): Certo v1.** At AltSlate Labs' request, the public MIT
[`altslate/certo-decision-model`](https://huggingface.co/altslate/certo-decision-model) checkpoint ran all 534 frozen
decisions through its author's `DecisionModel`, serially on our RunPod RTX 3090. The mapping, endpoint condition,
published 64-token state and 48-token option limits, and hosted-price cost basis were pushed before the run
([`docs/v1.2-additions-certo.md`](docs/v1.2-additions-certo.md)). No earlier result or task changed.

**v1.2.15 (tag `v1.2.15`): Zefan Cai's Open-Jev 2B and 9B.** Both pinned Apache-2.0 adapter packages ran all 534 frozen decisions through the author's MIT server on our RunPod H100: **Open-Jev 9B (Zefan Cai)** scored **56.7 (#39)** and **Open-Jev 2B (Zefan Cai)** scored **53.8 (#41)**. Their full names distinguish them from the other unrelated OpenJev projects already measured. An exact normalized-text audit found no public JevBench state or instruction in the 79,116-row public training projection, and on the held-out diagnostic both score slightly higher on held-out than on public hard items (gaps -2.6 and -2.9 points, field mean -0.7). Endpoint, revisions, licences, cost basis, the overlap check and the held-out figures are in [`docs/v1.2-additions-zefan-open-jev.md`](docs/v1.2-additions-zefan-open-jev.md). No earlier result or task changed.

**v1.2.16 (tag `v1.2.16`): rerankers.** Added zerank-2, Qwen3-Reranker-4B,
BAAI bge-reranker-v2-m3, Mixedbread mxbai-rerank-base-v2, and Alibaba GTE
Reranker ModernBERT-base as a new `reranker` class. All ran the complete 534
frozen decisions through one neutral, preregistered option-ranking adapter.
Temperature and yes/no threshold grids were fitted on public items only and
then frozen; the public no-instruction baseline and complete sensitivity curves
are embedded in each result row. See
[`docs/v1.2-additions-rerankers.md`](docs/v1.2-additions-rerankers.md).

**v1.2.13 (tag `v1.2.13`): OpenJev (thinking, BF16).** OpenJev's native typed-API `think=512` switch ran all 534 frozen decisions on the same H200. See [`docs/v1.2-additions-openjev-thinking.md`](docs/v1.2-additions-openjev-thinking.md).

**v1.2.12 (tag `v1.2.12`): djev (thinking).** An experimental full-generation path over the same open DiffusionGemma checkpoint ran all 534 frozen decisions with thinking enabled and a fixed 8,192-token cap. Current djev-dev itself hard-codes thinking off, one denoising step and read-only inference, so this is not described as a switch in its published typed API. See [`docs/v1.2-additions-djev-thinking.md`](docs/v1.2-additions-djev-thinking.md).

**v1.2.11 (tag `v1.2.11`): djev openness correction.** The djev score and all measurements are unchanged; its row now links the Apache-2.0 self-hostable runtime and identifies the Apache-2.0 Google base weights and absence of djev-specific weights.

**v1.2.10 (tag `v1.2.10`): smalljev semantic-v9.** At Aditya's request, the public Apache-2.0
[`isHeSatoshi/smalljev`](https://github.com/isHeSatoshi/smalljev) MiniCPM5-2B-Base LoRA and native decision heads
ran all 534 frozen decisions serially on our lium.io A6000, scoring **62.4 (#29)**. The mapping, endpoint condition,
non-zero hosted-reference cost basis and allowed public-benchmark-directed training disclosure were committed before
the run ([`docs/v1.2-additions-smalljev.md`](docs/v1.2-additions-smalljev.md)). No earlier result or task changed.

## v1.1.3: the GPU round

**[Results -> `RESULTS-v1.1.3.md`](RESULTS-v1.1.3.md)** · artifact
[`results/v1.1.3/jevbench-v1.1.3-results.json`](results/v1.1.3/jevbench-v1.1.3-results.json)

The v1.1 task set and v1.1.2 scoring, unchanged, plus six rows for open rebuilds that need a GPU, each run
the way its author serves it on a rented RunPod GPU: OpenJev on DiffusionGemma 26B-A4B (razorback16),
SemIf on Qwen3.5-4B, open-alternative-jev (complete this time; plus a marked post-hoc mode), system-one on
Qwen3-8B, and Bespoke Nimble 9B. Speed is measured from Germany over the internet to the GPU, like every
remote entrant. v1.1.2 rows are unchanged; only ranks move. Their hard-tier runs feed v1.2.

## v1.1: three sub-benchmarks and one Main Score (superseded by v1.2)

**[Results -> `RESULTS-v1.1.md`](RESULTS-v1.1.md)** · artifact
[`results/v1.1/jevbench-v1.1-results.json`](results/v1.1/jevbench-v1.1-results.json)

![JevBench v1.1 Main Score](results/v1.1/charts/main-score.png)

| Sub-benchmark | What it measures | Score 0-100 |
|---|---|---|
| **Capability** | accuracy on 314 decisions in three tiers - easy (72, new in v1.1), standard (96), judge (146) | mean of the three tier accuracies |
| **Speed** | median and p95 latency, serial, network included | log scale: 0.1 s = 100, 1 s = 50, 10 s = 0 |
| **Cost** | $ per 1,000 decisions: public tariff x measured tokens, or (no tariff) a labelled estimate at hosted-provider prices for the same weights or size class ([table](results/v1.1/pricing/jevbench-hosted-price-table.json)) | log scale: $0.001 = 100, $0.01 = 75, $0.10 = 50, $1 = 25, $10 = 0 |

**JevBench Main Composite Score = (Capability + Speed + Cost) / 3 - "Balanced 33:33:33"** (v1.1.2).
Three more named weightings are published beside it - *Emphasis on Accuracy (60:20:20)*, the
default until v1.1.1; *Emphasis on Speed (20:60:20)*; *Emphasis on Cost (20:20:60)* - plus
capability-only and a geometric mean. [benchmarkheaven.com/jev-models](https://benchmarkheaven.com/jev-models)
lets you set your own weights. Calibration (Brier, ECE) is reported for
every system with a distribution but is not part of the score - see
[`RESULTS-v1.1.md`](RESULTS-v1.1.md) for why. The rules are pure functions in
[`jevbench/composite.py`](jevbench/composite.py).

The easy tier exists so that small function-calling models are measured, not floored:
clear-cut intent, explicit yes/no facts, enum extraction, one obviously right tool.
48 of its items are public in `datasets/public/easy.jsonl`; 24 are held out.

**Revisions of v1.1 (all 19 Sep 2026; items, answers, Capability and Speed never changed):**
v1.1 (tag `v1.1`) Main Score 60:20:20; v1.1.1 (tag `v1.1.1`) Cost re-priced at hosted-provider
prices for every system without a tariff; **v1.1.2** Main Score weights changed to Balanced 33:33:33
(the previous default is kept as the preset "Emphasis on Accuracy") and the Cost scale widened to
$0.001-$10 per 1,000 decisions, so no system sits at the 100 cap.

v1.1 numbers are never mixed with v1.0's. v1.0 is described below and its results stay in
[`RESULTS.md`](RESULTS.md) as published.

## v1.0

v1.0 scored five axes side by side without a composite: **smart** (is it right), **cheap**
(what 1,000 decisions cost), **fast** (end-to-end latency, network included), **reliable**
(does the stated probability mean anything, does it survive a rephrasing, does it keep to
the schema) and **open** (weights and licence).

## What is in the suite (v1.0; v1.1 adds the easy tier)

242 decisions, six families, three cohorts:

| Cohort | Decisions | Published here? |
|---|---|---|
| `original-public` | 72 (36 paraphrase pairs) | yes, `datasets/public/original.jsonl` |
| `heldout-private` | 24 | no - held back so the suite cannot be trained on in full |
| `imported-public-source` | 146 | no - ground truth is ours, the task text is not ours to redistribute |

Families: request **routing**, answer **adequacy** judging, **policy** yes/no checks,
**intent** classification, **ordinal** severity scoring and enum **extraction**.
Every item states its exact label set; the model answers over that set and nothing else.

The 146 imported decisions come from our own auto-router experiment: 78 routing requests
with human-assigned categories, and 68 answer-adequacy judgements whose ground truth is a
deterministic grader's verdict on a saved answer. See [`THIRD-PARTY.md`](THIRD-PARTY.md).

## How a model is asked

Every system sees the same state, the same instructions, the same rubric and the same
exact label set. Only the transport differs, and each adapter uses the interface the
author published:

| Adapter | For |
|---|---|
| `typesafe` | TypeSafe's `/v1/systemone`, and the open rebuilds that implement the same wire format |
| `systemone_list` | the list-shaped `/decide` flavour some rebuilds ship |
| `gradio_space` | a rebuild whose only public interface is its Hugging Face Space demo |
| `local_openjev` | open weights loaded in-process, no network |
| `openai_compat` | ordinary instruction models, JSON-schema-constrained |

The first four read the model's **own** probability distribution. The last one asks the
model to **write** probabilities out under a schema. Those are different objects and are
labelled `native` and `verbalized` everywhere. Token-level logprobs are not used
anywhere, for anyone.

## Reproduce

The optional [`qwen_flash_linear` adapter](docs/qwen-flash-linear.md) connects to the
Qwen3.8 Flash Next compact BF16 linear runtime. Its pinned deployment instructions
and repeatability limitations are documented separately; no scored row is added.

Python 3.10+. The HTTP adapters need only the standard library.

```sh
python -m unittest discover -s tests -v

# Jev, the published 72-decision cohort
python -m jevbench.cli run --tasks datasets/public/original.jsonl \
  --adapter typesafe --model jev-latest --key-env TYPESAFE_API_KEY \
  --price-in-per-m 0.042 --price-out-per-m 0 \
  --results RUN/results.jsonl --raw-dir RUN/raw \
  --ledger RUN/ledger.jsonl --cap-usd 15 --manifest RUN/manifest.json

# an open rebuild on its author's public endpoint - note the empty key
python -m jevbench.cli run --tasks datasets/public/original.jsonl \
  --adapter typesafe --endpoint https://SOME-PUBLIC-ENDPOINT --key-env '' \
  --model jev-latest --cost-basis no_billable_account_public_endpoint \
  --reserve-usd 0 --delay-s 0.2 \
  --results RUN2/results.jsonl --raw-dir RUN2/raw --ledger RUN/ledger.jsonl

python -m jevbench.cli summarize --tasks datasets/public/original.jsonl \
  --results RUN/results.jsonl --public-export RUN/summary.json
```

Keys live in the environment and are named, never written into a config file, a result
or a log. `--key-env ''` sends no `Authorization` header at all, which is what a
stranger's public endpoint should get from us.

House rules the harness enforces rather than documents:

- **One budget for everything.** A file-locked ledger reserves the worst-case cost
  *before* a request goes out and settles the real cost after. The cap is shared across
  every run, not granted per model. A crashed run's reservation stays charged.
- **Every run directory is new.** Results and raw responses are created exclusively;
  a rerun can never overwrite paid evidence.
- **Stop means stop.** A 401, 403 or 429, or three consecutive infrastructure errors,
  ends the run. The rest stays unattempted and is reported as unattempted - never as
  answers the model got wrong. There are no retries.
- **No invented numbers.** An unknown price is `null`, not `0`. An empty metric is
  `null` with `n = 0`, not a flattering `0.0`. A malformed distribution is a schema
  failure and counts as wrong; it is never repaired into a distribution.

## What gets measured

- **Accuracy** - argmax over the exact label set. Every block also reports
  `majority_class_accuracy`, the score of always answering with the commonest label,
  because some cohorts are skewed and an accuracy has to be read against its floor.
  95 % confidence intervals resample whole scenarios, since paraphrases of one scenario
  are not independent draws.
- **Valid answers** - a distribution has to cover exactly the label set, sit in [0,1]
  and sum to 1. v1 froze a 0.001 sum tolerance; the run showed that this mostly catches
  three-decimal rounding (0.999 on a nine-option question), so the headline renormalizes
  anything inside a 2 % band and both columns are published: `schema_validity` under that
  rule and `schema_validity_strict` under the frozen one. Outside the band the answer is
  invalid and counts as wrong.
- **Brier** - the multi-class sum `sum_k (p_k - y_k)^2` over the exact label set. Binary
  questions use the matching two-class convention, so the numbers are comparable.
- **ECE** - top-label confidence, 10 equal-width bins. Empty bins are absent, not zero.
  The calibration denominator is reported next to it.
- **Ordinal MAE** - for score questions, the probability-weighted level against the
  reference level, reported beside argmax accuracy rather than instead of it.
- **Paraphrase consistency** - both the same-answer rate and the both-correct rate.
  Agreement alone rewards a model that is consistently wrong.
- **Latency** - caller wall time including the network, one request at a time, no
  concurrency. The first request is reported separately because a scale-to-zero endpoint
  bills its cold start to whoever knocks first.
- **Cost** - measured token usage times the provider's own published tariff, marked
  `derived_usage_times_tariff`. A route with no billable account - a public demo, our own
  CPU, a flat-rate subscription - reports `null` and says which, because unmetered is not
  free.
- **Openness** - code licence, weight availability and weight licence are three separate
  facts, and a permissive repository licence is not a licence for the base model.

## Limits, stated plainly

- 242 decisions is a pilot, not a census. It is English-only, and the original cases are
  short and hand-written.
- The adequacy cohort is 61 `yes` to 7 `no`; its majority-class floor is 82 %. Read that
  family's accuracy against that floor. Some of the judged answers were produced by
  models that also appear as baselines here, so two baselines judge some of their own work.
- The held-out split is sent to the services being evaluated in order to get predictions.
  Not public is not the same as not seen, and this is not a contamination proof.
- Latency comes from one origin (a Hetzner server in Germany) at one time of day. A
  hosted endpoint and a local CPU are not the same kind of latency and should not be
  read as one ranking.
- Public demo endpoints are shared with everyone else using them. Their numbers describe
  that deployment on that day, not the model's ceiling on your hardware.
- **The latency adjustment (×2, +0.15 s) is an assumption, not a measurement.** We ran self-hosted and demo endpoints one
  request at a time (parallelism 1, no other load), so their latency is likely better than the same model on a busy
  production server; the official Jev API presumably runs under high load, given the public interest. Serving under load
  trades per-user speed for throughput: in the NVIDIA chart shown by [SemiAnalysis](https://newsletter.semianalysis.com/p/nvidia-blackwell-perf-tco-analysis),
  moving to the throughput-maximising setting cuts per-user tokens/s by far more than 2×. That chart is a 1.8T MoE on GPU
  clusters, not a 4B model on one GPU, so it supports the direction and size of the effect, not our exact factor. The
  +0.15 s stands for infrastructure our self-hosted tests lacked: authentication, load balancing, logging, billing, API
  gateway. Raw p50/p95 are in [`RESULTS-v1.2.md`](RESULTS-v1.2.md) and the artifact; a measurement under load is planned.
- Several projects could not be run at all - no GPU, gated weights, Apple-Silicon-only,
  browser-only. They are listed with the concrete reason, and an exclusion is an
  availability fact, never a quality verdict.

## Licence

MIT for this harness and the 72 original public decisions. Everything else - model
weights, other projects' code, upstream datasets - keeps its own licence. See
[`THIRD-PARTY.md`](THIRD-PARTY.md).

## Support

This is a one-person hobby project, and the servers and model calls are paid out of pocket. If it is useful to you, you can **[support this project](https://donate.stripe.com/fZu00i9ro0wmdF88sg1Jm01)** with whatever amount you like. Payments go to productivity-boost.com Betriebs UG (haftungsbeschränkt) & Co. KG, the one-person company behind these projects.
