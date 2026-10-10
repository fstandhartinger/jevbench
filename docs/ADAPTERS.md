# Writing a JevBench adapter

An adapter connects one decision system (an HTTP API, a local checkpoint, a
demo Space) to the harness. The runner hands it one canonical task at a time
and gets back one `DecisionResult`. Everything below is what the code in this
repository actually does; each rule cites the line that enforces or relies on
it. If the code and this page disagree, the code wins: please open an issue.

Before opening a PR, run the conformance kit (see the end of this page).

## 1. The input: a `Task`

`jevbench/tasks.py` defines the canonical record (`Task`, `tasks.py:35`).
An adapter reads these fields:

| field | meaning | source |
|---|---|---|
| `state` | the content to judge; a string or a JSON object. Never contains the answer: keys `expected`, `label`, `ground_truth`, `answer_key` are rejected at load time | `tasks.py:64-67` |
| `question["type"]` | one of `noul`, `choice`, `score` | `tasks.py:32`, `tasks.py:48` |
| `question["instructions"]` | the question text | `tasks.py:8-9` |
| `question["criteria"]` | per-option descriptions, or `None` (shape per type below) | `tasks.py:9`, `base.py:79-80` |
| `labels` | the ordered, exact label strings the system may answer with | `tasks.py:10-12` |

`expected`, `split`, `group` and `provenance` are for scoring and reporting.
An adapter must not send `expected` to the system.
`build_question(task)` (`base.py:72`) builds the
`{type, instructions, criteria}` object that native typed APIs take.

### Task kinds and the labels they carry

| `type` | `labels` | `criteria` (as existing adapters read it) | `expected` |
|---|---|---|---|
| `noul` (yes/no) | always `["no", "yes"]` (`tasks.py:11`, `base.py:12`) | dict with keys `"true"` / `"false"` (`certo_local.py:44-49`, `openai_compat.py:55`) | `"yes"` or `"no"` |
| `choice` | the option names, e.g. `["billing", "shipping", "other"]` | dict label -> description, or `None` (`certo_local.py:50-53`) | one label string |
| `score` (ordinal) | level indices as strings: `["0", "1", ...]` (`tasks.py:11-12`) | list; `criteria[int(label)]` describes level `label` (`certo_local.py:54`, `openai_compat.py:45`) | an **int** level index (`tasks.py:55-59`) |

## 2. The adapter object

The runner (`jevbench/runner.py`) needs these attributes and methods:

| member | required | contract | source |
|---|---|---|---|
| `name: str` | yes | written to the ledger and to failed results | `runner.py:216`, `runner.py:227` |
| `run(task) -> DecisionResult` | yes | one decision, no retries. If it raises, the runner records a failed attempt with only the exception's class name, so catch errors yourself and return `ok=False` with an `error` | `runner.py:226-227` |
| `reserve_estimate(task)` | yes | `None` or a finite float >= 0 (USD). The runner reserves `max(default_reserve, estimate)` from the shared budget before the call | `runner.py:215`, `budget.py:147-150` |
| `price_input_per_m`, `price_output_per_m` | yes (may be `None`) | USD per million tokens; read directly, so the attributes must exist | `runner.py:232` |
| `cost_basis: str` | optional | why the cost is what it is (`"self_hosted_gpu"`, ...); default `"unknown"` | `runner.py:236-237` |
| `prepare(task)` | optional | per-task setup run **before** the clock starts; its time is recorded as `prepare_s`, its exceptions are printed and ignored | `runner.py:217-224`, `runner.py:246` |
| `load()` | optional | called once by the CLI before the run when `JEVBENCH_WARM_LOAD=1` | `cli.py:283-288` |
| `request_options` | optional | dict set by the CLI's `--request-options` JSON | `cli.py:278-281` |

The CLI constructs built-in adapters with the keyword arguments `endpoint`,
`model`, `key_env`, `price_input_per_m`, `price_output_per_m` (plus `revision`
for some local checkpoints) (`cli.py:266-275`). A new adapter should accept
these; to be selectable with `--adapter` it must also be added to the `kinds`
map and the `choices` list in `cli.py` (`cli.py:252-262`, `cli.py:357-363`).

## 3. The output: `DecisionResult`

Defined at `base.py:16-30`.

| field | contract |
|---|---|
| `adapter` | the adapter's `name` |
| `ok` | `True` when the system answered. `False` means an infrastructure failure: scored invalid and wrong (`runner.py:245`) |
| `probs` | dict over **exactly** `task.labels` (see section 4) |
| `probs_source` | `"native"` (the system's own distribution) or `"verbalized"` (a model wrote numbers in its output); never logprobs (`base.py:20`, `openai_compat.py:3-6`). Label-only systems use `"label_only_no_calibrated_distribution"` (`runner.py:244`) |
| `label` | label-only systems only: one label string, or `None` to abstain (`base.py:28-30`) |
| `model` | the resolved model identity; collected into `model_identities` (`summarize.py:31`) |
| `status` | HTTP status, if any. 401/403/429 stop the run; three consecutive failures stop it; 422 counts as a wrong answer, not toward the stop rule (`runner.py:260-264`) |
| `error` | short message when `ok=False` or when a label-only system abstained |
| `latency_s` | adapter-measured latency. Note the published record uses the runner's own wall clock around `run()` instead (`runner.py:225-228`, `runner.py:246`) |
| `usage` | dict; `input_tokens` / `output_tokens` (numbers) are used for cost (`runner.py:239-241`) |
| `request_body`, `raw` | preserved as private raw evidence; must be JSON-serialisable with no NaN/inf, or the runner raises (`runner.py:229`). If `raw` is a dict, `raw["runtime"]` is copied into the record (`runner.py:246`). `to_public()` drops both (`base.py:32-45`) |

### The typed output per task kind

The runner scores every kind the same way: `probs` keyed by the label strings.
How the system's native answer becomes that dict is the adapter's job; the
TypeSafe adapter shows the mapping (`typesafe.py:8-11`, `typesafe.py:86-102`):

| kind | what to return | example |
|---|---|---|
| `noul` | `{"no": 1-p, "yes": p}`; keys are `"yes"`/`"no"`, not `true`/`false` | `{"no": 0.2, "yes": 0.8}` |
| `choice` | one probability per option label | `{"billing": 0.7, "shipping": 0.2, "other": 0.1}` |
| `score` | one probability per level index, **string** keys | `{"0": 0.1, "1": 0.3, "2": 0.6}` |
| any, label-only | `probs=None`, `probs_source="label_only_no_calibrated_distribution"`, `label=<one of task.labels>` | `label="2"` |

## 4. Probability and calibration rules

All in `jevbench/scoring.py`:

* Keys must equal the label set exactly: no missing, no extra (`scoring.py:36-41`).
* Values must be real numbers (not `bool`), finite, in `[0, 1]` (`scoring.py:44-51`).
* **Strict-valid:** the sum is within `SUM_TOL = 1e-3` of 1 (`scoring.py:11`, `scoring.py:54-55`).
* **Valid (headline):** the sum is within `RENORM_TOL = 2e-2`; the
  distribution is rescaled to sum to 1 and marked `renormalized`
  (`scoring.py:20`, `scoring.py:86-101`). Outside that band the answer is
  invalid and counts as wrong; it is never repaired (`scoring.py:92-94`).
* The prediction is the argmax; ties go to the lexicographically smallest
  label (`scoring.py:59-65`). For `score` the argmax level is compared to
  `str(expected)` and the expected value over levels is recorded as
  `ordinal_ev` (`scoring.py:115-119`).
* Brier and ECE are computed only from records with a distribution
  (`summarize.py:7-10`), so label-only systems get accuracy but no
  calibration metrics (`scoring.py:127-143`). A label-only abstention
  (`label=None`) is valid-but-wrong; a label outside the set is invalid
  (`scoring.py:134-142`).
* Never invent a distribution from a single confidence scalar
  (`needle_local.py:9-10`, `metrics.py:16-17`).

## 5. Timing and cost

* Latency is the runner's wall clock around `run()` only. Model loading
  belongs in `load()` and per-rubric setup in `prepare()`, both outside the
  clock (`runner.py:217-228`, `cli.py:283-288`).
* Cost (`runner.py:232-243`):
  * both prices `0` -> `cost_usd = 0.0`;
  * otherwise, if `ok` and both prices and both token counts are numbers ->
    `cost_usd = in*price_in/1e6 + out*price_out/1e6`, basis
    `derived_usage_times_tariff`;
  * otherwise `cost_usd` stays `null` (unmetered is not free) and the
    ledger keeps the full reservation as the charge.
* `price_per_1000_decisions_usd` is only reported when every record has a
  cost (`summarize.py:14`).

## 6. Minimal worked example

A baseline that puts equal probability on every label. Save it **outside**
the repository's `jevbench/` package, e.g. as `my_adapter.py` at the repo root:

```python
import sys, time
from jevbench.adapters.base import DecisionResult
from jevbench.adapters.conformance import check_adapter
from jevbench.budget import Ledger
from jevbench.runner import Runner
from jevbench.tasks import load_jsonl


class UniformAdapter:
    """Puts equal probability on every allowed label. A baseline, not a model."""
    name = "uniform_example"
    cost_basis = "local_cpu_no_provider_tariff"
    price_input_per_m = None   # no per-token tariff -> cost_usd stays null
    price_output_per_m = None

    def reserve_estimate(self, task):
        return 0.0             # nothing billable; runner still reserves its default

    def run(self, task):
        t0 = time.perf_counter()
        p = 1.0 / len(task.labels)
        probs = {label: p for label in task.labels}
        return DecisionResult(
            adapter=self.name, ok=True, probs=probs, probs_source="native",
            model="uniform-baseline", latency_s=time.perf_counter() - t0,
            usage={"input_tokens": 0, "output_tokens": 0},
            request_body={"labels": task.labels}, raw={"runtime": {"device": "cpu"}},
        )


if __name__ == "__main__":
    out = sys.argv[1]                          # a directory OUTSIDE the repo
    print(check_adapter(UniformAdapter()).summary())
    tasks = load_jsonl("datasets/public/easy.jsonl")
    runner = Runner(UniformAdapter(), Ledger(f"{out}/ledger.jsonl", cap_usd=1.0), raw_dir=f"{out}/raw")
    records = runner.run_all(tasks, results_path=f"{out}/results.jsonl")
    print(len(records), "records written")
```

## 7. Running against the public split locally

The public split lives in `datasets/public/` (`easy.jsonl`, `hard.jsonl`,
`original.jsonl`). Raw evidence and per-item results must be written outside
the repository; the runner refuses paths inside it (`runner.py:212`,
`runner.py:251`), and existing files are never overwritten (`open('x')`,
`runner.py:231`, `runner.py:252`), so use a fresh directory each time:

```sh
PYTHONPATH=. python my_adapter.py /tmp/jevbench-run
python -m jevbench.cli summarize --tasks datasets/public/easy.jsonl \
    --results /tmp/jevbench-run/results.jsonl --ledger /tmp/jevbench-run/ledger.jsonl
```

Real output of the example above (abridged):

```
uniform_example: 4 fixture tasks, 0 violation(s), 0 warning(s)
48 records written
{'n_attempted': 48, 'accuracy': 0.2708..., 'schema_validity': 1.0, 'brier_mean': 0.7156...,
 'price_per_1000_decisions_usd': None, 'cost_basis': ['local_cpu_no_provider_tariff'],
 'probability_sources': ['native']}
```

Built-in adapters run through the CLI instead, e.g.
`python -m jevbench.cli run --tasks datasets/public/easy.jsonl --adapter openai_compat --endpoint ... --results /tmp/out.jsonl`
(`cli.py:197-201`). A local run on the public split is a smoke test, not a
published result.

## 8. Conformance kit

`jevbench/adapters/conformance.py` runs an adapter once on four tiny
synthetic tasks (one per kind, plus one with no ground truth). These are
test fixtures written for the kit, not benchmark items. It reports:

* missing `name`, `run`, `reserve_estimate`, price attributes;
* `reserve_estimate` that is not `None` or a finite non-negative number;
* `run` raising instead of returning `ok=False`;
* a return value that is not a `DecisionResult`;
* `request_body` / `raw` that the runner could not serialise;
* `ok=False` without an `error`;
* `ok=True` with `probs=None` but no label-only marker, or a label outside the set;
* distributions that `score_task` rejects, and a `probs_source` other than
  `native` / `verbalized`;
* as a *warning*: distributions that are only valid after renormalisation.

```python
from jevbench.adapters.conformance import check_adapter
report = check_adapter(MyAdapter())   # optionally: tasks=[...]
print(report.summary()); assert report.ok
```

The kit calls your adapter for real; an adapter that talks to a network
service will make four requests. Passing the kit does not mean the system's
answers are any good, only that the harness can score them.
