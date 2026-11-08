# jevora-9b-v1 local adapter

`jevora_9b_v1` is an offline package adapter. It does not call a hosted API,
does not include weights, and does not implement JevBench scoring. It preserves
the exact task-label order and returns Jevora's native probability distribution.

## Pins and limits

- Weights: `kadirbekovvv/jevora-9b-v1` at HF revision
  `545549b8e8104f1780966ef1c13136abb32712b4`.
- Public inference code:
  `doxanocap/jevora-9b-v1@84864f9a8e8a6642a7b7bc1ab57ee0d5f5297cd2`.
- The package manifest must have SHA256
  `483a5398d29b48f252d0aa6349946433b1c0b291bad81ce66d47f1f94ea3c6db`.
- This V1.6 package uses BF16 and uncalibrated temperature `1`.
- The adapter returns HTTP-like status `422` for more than 8,192 rendered
  tokens or more than 255 options. It never truncates. Runtime and inference
  errors remain failed attempts without a synthetic status.

Choice uses the exact ordered labels. Noul requires `['no', 'yes']` and
returns native `P(no)` and `P(yes)`. Score requires `['0', '1', ...]` and
returns a probability for every ordered level. Thresholds, expected values and
all scores are the official runner/scorer's responsibility.

## Maintainer setup

From the JevBench checkout root, these commands are instructions, not a
claimed benchmark run:

```sh
JEVBENCH_DIR="$(pwd -P)"
WORK_DIR="$(cd .. && pwd -P)"
CODE_REPO=https://github.com/doxanocap/jevora-9b-v1
CODE_REVISION=84864f9a8e8a6642a7b7bc1ab57ee0d5f5297cd2
CODE_DIR="$WORK_DIR/jevora-public"
git clone "$CODE_REPO" "$CODE_DIR"
git -C "$CODE_DIR" checkout --detach "$CODE_REVISION"
(cd "$CODE_DIR" && uv sync --locked)

HF_REPO_ID=kadirbekovvv/jevora-9b-v1
HF_REVISION=545549b8e8104f1780966ef1c13136abb32712b4
MODEL_DIR="$WORK_DIR/models/jevora-9b-v1"
"$CODE_DIR/.venv/bin/hf" download "$HF_REPO_ID" --revision "$HF_REVISION" --local-dir "$MODEL_DIR"
PACKAGE="$MODEL_DIR/jevora-9b-v1"
make -C "$CODE_DIR" verify-package PACKAGE="$PACKAGE"
```

`PACKAGE` is the nested `jevora-9b-v1/` directory, not the Hugging Face
repository root. Run the adapter with the public Jevora environment and the
JevBench source checkout on `PYTHONPATH`:

```sh
TASKS=/path/to/maintainer-authorized-tasks.jsonl
RUN_DIR=/path/out/jevora-9b-v1-smoke
mkdir -p "$RUN_DIR"
JEVBENCH_WARM_LOAD=1 PYTHONPATH="$JEVBENCH_DIR:$CODE_DIR/src" \
  "$CODE_DIR/.venv/bin/python" -m jevbench.cli run \
  --tasks "$TASKS" --adapter jevora_9b_v1 --endpoint "$PACKAGE" \
  --revision "$HF_REVISION" --device cuda --limit 1 \
  --cost-basis self_hosted_cost_not_priced --reserve-usd 0 --cap-usd 0 \
  --results "$RUN_DIR/results.jsonl" --ledger "$RUN_DIR/ledger.jsonl" \
  --raw-dir "$RUN_DIR/raw" --manifest "$RUN_DIR/manifest.json"
```

`JEVBENCH_WARM_LOAD=1` loads the package and model before JevBench starts the
decision clock.

For an official invocation, omit `--limit 1` and use the maintainer-pinned
task bundle, runner, scorer and storage policy. This repository does not ship
the historical v1.5.2 task bundle or its compatible scorer, so this adapter
does not claim an official JevBench result.
