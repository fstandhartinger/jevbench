# ImageJevBench evaluation request: Xor NVFP4

**Status: requested; not yet evaluated on ImageJevBench.** This file requests an official run. It does not claim an ImageJevBench score.

## Candidate

- Name: Xor NVFP4
- Hugging Face: <https://huggingface.co/juspay/xor-nvfp4>
- Pinned revision checked for this request: `8de64b749a858dad95f7087eb69af5c67df3ec3c`
- Access: public and ungated at the pinned revision
- License declared by the model card: Apache-2.0
- Base checkpoints: `Qwen/Qwen3.6-35B-A3B`, `nvidia/Qwen3.6-35B-A3B-NVFP4`, and `juspay/xor`
- Intended use: image-conditioned typed decisions

The model card describes a mixed-precision NVFP4 build with an adapter blend, and documents image data URL support through the serving bundle's TypeSafe-compatible `/v1/systemone` interface. It reports validation on two NVIDIA RTX PRO 6000 Blackwell GPUs. These are model-card claims, not independent ImageJevBench findings.

## Requested evaluation

Please consider evaluating this candidate on the current frozen ImageJevBench protocol, including its core and everyday-photo tracks. The current benchmark page describes 684 scored items (228 public and 456 sealed); we have not run this candidate on the official ImageJevBench split and do not have its runner or item export.

The request is for the benchmark maintainer to run and score the candidate using the official protocol. We will not submit the separate local 2,637-item evaluation as an ImageJevBench result.

## Serving notes from the model card

The model card's supported setup uses its pinned serving bundle and exposes the SystemOne-compatible API at `http://127.0.0.1:30002/v1/systemone`. It requires Linux x86-64, Docker Compose v2, NVIDIA Container Toolkit, and about 60 GB of free disk. The model card's manual SGLang invocation specifies the NVFP4-specific flags `--moe-runner-backend flashinfer_cutlass` and `--kv-cache-dtype bf16`; that raw SGLang process is not by itself the SystemOne wrapper endpoint.

The model card also documents:

- Two-GPU configuration: `CUDA_VISIBLE_DEVICES=0,1`, `DP_SIZE=2`.
- Single-GPU configuration: `CUDA_VISIBLE_DEVICES=0`, `DP_SIZE=1`.
- Image requests use the wrapper's `images` array with image data URLs (up to eight images per request; request body up to 8 MB).
- Use the exact serving bundle and pinned container digest documented in the model card; record the resolved image digest and all runtime settings in the run manifest.

Its manual raw SGLang launch command is:

```bash
docker run -d --name xor-nvfp4-sglang --gpus '"device=0,1"' --network host --ipc host -e HF_HUB_OFFLINE=1 \
  -v "$PWD/xor-nvfp4:/models/xor:ro" \
  prakhar1611/xor-sglang@sha256:94c48d2a6cc98dc456cf93f723707ea7dd81dddfe1061e823b348d68bbe8158f \
  python3 -m sglang.launch_server --model-path /models/xor --trust-remote-code \
  --tp-size 1 --dp-size 2 --port 30000 --host 127.0.0.1 \
  --max-prefill-tokens 250000 --mem-fraction-static 0.85 \
  --moe-runner-backend flashinfer_cutlass --kv-cache-dtype bf16
```

This starts the model-serving process on port 30000. For benchmark requests, use the model card's full serving bundle, which adds the SystemOne-compatible wrapper on port 30002.

## Prior, non-ImageJevBench evidence

The model card reports matching or exceeding Xor 1.1 on public JevBench tiers and the kev transfer-v4 development suite on the authors' stated hardware. Those are not ImageJevBench results and are not offered as evidence of ImageJevBench accuracy.

## Request

Please advise whether this PR is the right intake path for an ImageJevBench candidate, and whether you can run the pinned public checkpoint on the official split. We can provide additional runtime details or coordinate a reproducible serving session if needed.
