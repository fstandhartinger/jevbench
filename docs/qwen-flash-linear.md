# Qwen3.8 Flash Next: original BF16 linear choice runtime

This is an adapter submission for independent evaluation, not a scored leaderboard
entry. It submits only the compact linear-head runtime. No benchmark results or
existing ranks are changed by this PR.

## Identity and reproducible deployment

- Runtime: [WIlfLin/JEV-Qwen3.8-Flash-Next-Linear-Runtime](https://huggingface.co/WIlfLin/JEV-Qwen3.8-Flash-Next-Linear-Runtime/tree/690c62e07b984777ed054cdd9b3eb19437736669),
  revision `690c62e07b984777ed054cdd9b3eb19437736669`.
- Backbone: [primitive-ai/Qwen3.8-Flash-Next-mixed-NVFP4-FP8](https://huggingface.co/primitive-ai/Qwen3.8-Flash-Next-mixed-NVFP4-FP8/tree/07915ee79ec217c117e8a57bf2557a4a1418c10f),
  revision `07915ee79ec217c117e8a57bf2557a4a1418c10f` (about 184 GB on disk).
- Output head: 86 original BF16 rows, shape `(86, 2560)`, SHA256
  `90a4b3ea59a2f16046ac754d1c55893cf04e84a3590efb32b1ed87bd1f4f161f`.
  It is an exact row extraction, with no head fitting, fine-tuning or temperature
  fitting. The backbone is unchanged from the pinned quantization.
- Container: `vllm/vllm-openai@sha256:0aea30240f3e3d9ffae8526643950e170eb5fa07fc427016a9dd90892afa2aa3`.
- Model/head licence: Qwen Community License 1.0, included in the runtime repo;
  this is not an Apache/MIT claim about model weights. The adapter follows this
  benchmark repository's MIT licence.

The author tested an RTX PRO 6000 Blackwell 96 GB with more than 100 GiB available
host RAM for CPU-offloaded PLE. The plugin imports version-specific vLLM internals;
other GPUs, smaller RAM budgets and other vLLM builds are not verified. This is not
a claim of H100 support. Keep the endpoint on the evaluator's own machine so the
submitter cannot observe held-out inputs.

```sh
hf download WIlfLin/JEV-Qwen3.8-Flash-Next-Linear-Runtime \
  --revision 690c62e07b984777ed054cdd9b3eb19437736669 --local-dir flash-linear
cd flash-linear
python download_weights.py
bash serve_backend.sh
# In a second shell with transformers, fastapi, uvicorn, httpx and pydantic:
python serve_choice.py
```

The supplied backend script sets `VLLM_PLUGINS=jev_linear`,
`JEV_LINEAR_HEAD=/head/head.safetensors`, `VLLM_USE_V2_MODEL_RUNNER=0`,
`VLLM_PLE_CPU_OFFLOAD=1`, `VLLM_PLE_OFFLOAD_READY_TIMEOUT=1800`, and
`VLLM_GDN_DECODE_KERNEL=triton`. The model performs an 86-row BF16 projection, then
scatters logits to the original token-ID space for the existing one-token vLLM
scoring transport. No vocabulary-sized output matrix multiplication remains.

## Frozen mapping and scoring

Each task is one `/v1/choice` request. The question text contains state (JSON when
structured), type and instructions. Options preserve the canonical label order
and include each label's complete description. `noul` includes both yes/no
criteria; `score` includes every ordered level. No expected answers, task IDs,
provenance, rationale, truncation, answer repair or retry is inserted.

The runtime renders its fixed choice template, restricts vLLM to the supplied
label token IDs, requests their native log probabilities at temperature 1, and
normalizes over those labels. The adapter only maps the indexed probabilities
back to canonical labels. These are native conditional option probabilities,
not generated probability text or a calibration guarantee.

Limits: 2–86 options; a 4096-token context including one output token. Oversized
requests fail rather than silently truncating the state or dropping options.

From the benchmark checkout, with the local runtime ready:

```sh
python -m jevbench.cli run \
  --adapter qwen_flash_linear --endpoint http://127.0.0.1:8239 --key-env '' \
  --model WIlfLin/JEV-Qwen3.8-Flash-Next-Linear-Runtime@690c62e \
  --tasks datasets/public/easy.jsonl,datasets/public/original.jsonl,datasets/public/hard.jsonl \
  --cost-basis local_existing_gpu_compute_unpriced --reserve-usd 0 --cap-usd 0 \
  --results ../private/flash-linear/results.jsonl \
  --raw-dir ../private/flash-linear/raw --ledger ../private/flash-linear/ledger.jsonl \
  --manifest ../private/flash-linear/manifest.json
```

No provider tariff exists: cost stays `null`, not zero. An official hosted-cost
reference and production-load latency adjustment are left to the maintainers'
existing methodology. Hardware price or throughput has not been invented here.

## Repeatability disclosure and verification scope

The author observed different probabilities on repeated identical inputs, and
prediction changes between full public-set runs in the same process, even with
a fixed request seed. A paired diagnostic on actual hidden states found matching
full-head and compact-head label logits; that does not establish end-to-end
repeatability. The exact nondeterminism source has not been isolated. Please
retain repetitions/dispersion if evaluating this submission, rather than treating
one run as a definitive score. Public benchmark conclusions were withdrawn from
the model card; this PR deliberately contains no accuracy or rank claim.

The pinned runtime completed two full 231-item local public runs with the
connection-reuse wrapper. The benchmark CLI also completed a live request through
this adapter. Validation additionally replays recorded native responses and tests
task mapping, malformed responses and error propagation. It does not constitute a maintainer-run full-suite result.
No held-out data is requested or supplied in this PR.
