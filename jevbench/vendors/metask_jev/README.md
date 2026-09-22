# Vendored: minimal `nimble` package for the metask_jev adapter

These files are a minimal extract of the [Bespoke Labs Nimble](https://github.com/bespokelabsai/nimble)
inference package (Apache-2.0), needed by `jevbench/adapters/metask_jev.py`:

- `nimble/scoring/parallel_schema.py` — official prompt builder (`prepare_prompts`,
  `choice_key`, SYSTEM_PROMPT) and schema validation. Untouched except for the
  module docstring; the prompt contract is byte-identical to the one the model
  was trained on.
- `nimble/scoring/cuda_scorer.py` — self-contained candidate-logit scorer
  (`CudaCandidateScorer`): one forward pass per question, softmax over the
  candidate-token logits, CUDA/MPS/CPU auto-detected. Rewritten for this repo
  so the adapter has no dependency on the full nimble package.

The adapter prefers this vendored copy; point `METASK_JEV_NIMBLE_PACKAGE` at a
full nimble checkout to override.

Nimble is (c) Bespoke Labs, Apache-2.0 — see their repo for the full licence.