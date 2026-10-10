# JevBench command line

The CLI lives in `jevbench/cli.py`. After `pip install -e .` it is available as
`jevbench`; without installing, `python -m jevbench.cli` is equivalent.

```
jevbench {run,summarize} ...
jevbench --help | jevbench run --help | jevbench summarize --help
```

There are two subcommands:

| subcommand  | does |
|-------------|------|
| `run`       | runs one adapter over task files, one request per task, serially and with no retries; writes per-item results, raw evidence and budget ledger entries |
| `summarize` | aggregates a results file into overall, per-family and per-split metrics and prints them as JSON |

A local run on the public split is a smoke test, not a published result.

## Where files go

The runner refuses to write per-item results or raw responses inside the
repository (`ValueError`), and it never overwrites: the results file and each
raw response file are opened in exclusive-create mode. Use a fresh directory
outside the repo for every run, e.g. `/tmp/jb-<date>/`.

## `jevbench run`

```
jevbench run --tasks <jsonl[,jsonl...]> --adapter <name> --results <out.jsonl> [options]
```

| flag | default | meaning |
|------|---------|---------|
| `--tasks` | required | task JSONL file(s), comma-separated. Public split: `datasets/public/easy.jsonl`, `hard.jsonl`, `original.jsonl` |
| `--adapter` | required | one of `typesafe`, `systemone_list`, `gradio_space`, `local_openjev`, `openai_compat`, `needle_local`, `semif_direct`, `so1_decider`, `remote_inproc`, `sg_system_one`, `djev`, `laya_local`, `gliner2_local`, `verdict_local`, `paw_local`, `classifier_dev`, `certo_local`, `qwen_flash_linear` |
| `--endpoint` | none | base URL of the system under test; for local-checkpoint adapters (e.g. `local_openjev`, `laya_local`) the local snapshot path. Required except for `typesafe`, `djev`, `needle_local`, `semif_direct`, `so1_decider`, `sg_system_one`, `classifier_dev` (exit status 2 if missing) |
| `--model` | none | model name to request; `openai_compat` sends `""` if unset |
| `--key-env` | `TYPESAFE_API_KEY` | **name** of the environment variable holding the API key. The key is never printed or logged |
| `--results` | required | per-item results JSONL to create (must not exist; outside the repo) |
| `--ledger` | `<repo>/../private/ledger.jsonl` | shared budget ledger JSONL, appended to |
| `--raw-dir` | `<repo>/../private/raw_responses` | raw request/response evidence, one JSON file per task (outside the repo) |
| `--cap-usd` | `15.0` | budget cap in USD; if the ledger already records a lower cap, the lower one applies. A request that would exceed it is not sent and the run stops |
| `--reserve-usd` | `0.02` | minimum USD reserved per request before it is sent; an adapter's own estimate is used when it is larger |
| `--price-in-per-m` | none | USD per million input tokens |
| `--price-out-per-m` | none | USD per million output tokens. With both prices set, `cost_usd` is derived from reported usage; with both `0`, `cost_usd` is `0`; otherwise it stays `null` (unmetered is not free) |
| `--limit` | none | only run the first N tasks |
| `--delay-s` | `0.0` | pause between requests, for someone else's free public demo |
| `--request-options` | none | JSON object of extra request body fields, e.g. `'{"reasoning_effort": "low"}'`; recorded in the manifest |
| `--revision` | none | pinned revision of a local checkpoint (local-checkpoint adapters only) |
| `--run-label` | `--model`, else `--adapter` | label stored in the manifest |
| `--cost-basis` | none | why this route's per-decision cost is what it is, e.g. `no_billable_account_public_demo` |
| `--manifest` | none | write the run's exact settings as JSON to this path |

Environment: `JEVBENCH_WARM_LOAD=1` makes adapters that have a `load()`
method load their weights before the clock starts; the load time is printed.

The run stops early on a budget stop, on HTTP 401/403/429, or after 3
consecutive infrastructure failures (a 422 counts as a wrong answer, not a
failure). Remaining tasks are left unattempted.

**Exit status:** `0` every task attempted, `3` run stopped early, `2` usage
error (bad flags or missing `--endpoint`).

**Output files:**

* `--results`: one JSON object per attempted task (`task_id`, `family`,
  `split`, `status`, `valid`, `correct`, `predicted`, `probs`,
  `probs_as_returned`, `probs_source`, `model`, `latency_s`, `usage`,
  `cost_usd`, `cost_basis`, `charged_usd`, `raw_sha256`, ...).
* `--raw-dir`: `<sha256(task_id)>.json` holding the request body, the raw
  response and the HTTP status; its hash is the record's `raw_sha256`.
* `--ledger`: `cap`, `reserve` and `settle` events.
* `--manifest` (optional): adapter, endpoint, requested and resolved models,
  request options, prices, cost basis, `dataset_hash`, planned/attempted
  counts, charged USD, start and finish times.

## `jevbench summarize`

```
jevbench summarize --tasks <jsonl[,jsonl...]> --results <jsonl> [options]
```

| flag | default | meaning |
|------|---------|---------|
| `--tasks` | required | the same task JSONL file(s) the run used, comma-separated |
| `--results` | required | per-item results JSONL written by `jevbench run` |
| `--ledger` | none | if given and the file exists, its total is reported as `ledger_charged_usd` (else `0.0`) |
| `--public-export` | none | also write an allowlisted aggregate JSON (no item text or labels, `ledger_charged_usd` null, plus `dataset_hash`) |
| `--include-excluded` | off | passed to `summarize()` as `headline_only=False`, which the function currently does not use: the output is identical with or without it |

The summary JSON goes to stdout. Items with an `exclude_reason` or no
expected answer are never scored; they still count as attempted. It fails
with `ValueError` on duplicate records or records for tasks not in `--tasks`.

## End-to-end example on the public split, offline

None of the built-in adapters is a dummy, and the CLI has no plug-in hook for
custom adapters (for that, see the Python example in
[ADAPTERS.md](ADAPTERS.md#6-minimal-worked-example)). To try the full CLI
path offline, run `openai_compat` against a tiny local stand-in server that
answers every request with a uniform distribution. Save this **outside** the
repo, e.g. as `/tmp/stub_server.py`:

```python
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        keys = body["response_format"]["json_schema"]["schema"]["properties"]["probabilities"]["required"]
        content = json.dumps({"probabilities": {k: 1 / len(keys) for k in keys}})
        out = json.dumps({"model": "uniform-stub", "choices": [{"message": {"content": content}}],
                          "usage": {"prompt_tokens": 0, "completion_tokens": 0}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 8765), H).serve_forever()
```

```sh
python /tmp/stub_server.py &
STUB_KEY=offline jevbench run --tasks datasets/public/easy.jsonl --adapter openai_compat \
  --endpoint http://127.0.0.1:8765/v1 --model uniform-stub --key-env STUB_KEY \
  --price-in-per-m 0 --price-out-per-m 0 --cost-basis local_stub_no_tariff \
  --results /tmp/jb/results.jsonl --ledger /tmp/jb/ledger.jsonl \
  --raw-dir /tmp/jb/raw --manifest /tmp/jb/manifest.json
jevbench summarize --tasks datasets/public/easy.jsonl --results /tmp/jb/results.jsonl \
  --ledger /tmp/jb/ledger.jsonl --public-export /tmp/jb/public.json
kill %1
```

Real output (summary abridged):

```
[jevbench] adapter=openai_compat endpoint=http://127.0.0.1:8765/v1 tasks=48 cap=$15.0 ledger=/tmp/jb/ledger.jsonl
10/48 completed
...
[jevbench] done: 48/48 attempted, 0 failed; charged=$0.0000
[jevbench] public export -> /tmp/jb/public.json
{'n_attempted': 48, 'accuracy': 0.2708..., 'schema_validity': 1.0, 'brier_mean': 0.7156...,
 'price_per_1000_decisions_usd': 0.0, 'cost_basis': ['local_stub_no_tariff'],
 'probability_sources': ['verbalized'], 'ledger_charged_usd': 0.0, 'complete': True}
```

The uniform baseline gives the same accuracy and Brier score as the Python
example in ADAPTERS.md. Delete `/tmp/jb` before running again.
