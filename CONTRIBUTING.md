# Contributing to JevBench

Thanks for helping. JevBench is a small, non-profit, open-source benchmark;
the most useful contributions are adapters, tooling, tests and docs.

## Adding an adapter

Read [docs/ADAPTERS.md](docs/ADAPTERS.md). It describes the adapter contract
(input task kinds, the typed output each kind expects, probability, timing and
cost fields), a minimal worked example, and how to run it on the public split.
Before opening a PR, check your adapter with the conformance kit:

```python
from jevbench.adapters.conformance import check_adapter
print(check_adapter(MyAdapter()).summary())
```

Add a unit test for your adapter under `tests/` that mocks the model or
endpoint; tests must not call paid APIs or download weights.

## Tests

```sh
pip install pytest
python -m pytest -q
```

The suite runs offline in about a second. Please keep it that way.

## Checking task files

```sh
python -m jevbench.cli validate-data datasets/public/*.jsonl
```

`validate-data` is read-only. It loads each file with the loader in
`jevbench/tasks.py`, which runs every task's `validate()`, then checks that ids
are unique across all files given, that each `question.type` is an allowed kind
(`noul`, `choice`, `score`), that `expected` has the type its kind needs (an int
level for `score`, `"no"`/`"yes"` for `noul`, a label string for `choice`) and
that all items sharing a `group` share one expected answer. It prints a
per-file summary and one `PROBLEM` line per issue, and exits 1 if there is
any problem.

## What not to change in a PR

* Benchmark items (`datasets/`) and published results (`results/`) are
  curated by the maintainers; PRs should not add or edit them.
* Scoring formulas, tolerances and published numbers are frozen per release
  (see `docs/METHOD-*.md`); changes go through an issue first.

## Benchmark requests

Want a system benchmarked? File a GitHub issue naming the system, its public
interface (API, checkpoint or demo) and its license or terms. Please do not
open a PR with results for it.
