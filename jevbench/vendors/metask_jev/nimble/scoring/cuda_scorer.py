"""Minimal CUDA/MPS candidate scorer (vendored for the metask_jev adapter).

Implements the official Nimble scoring contract: build prompts via
prepare_prompts, one forward pass, gather candidate-token logits.
"""
import hashlib
import json
import time

import torch


def choice_key(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def candidate_projection(hidden, head_weight, candidates):
    raise NotImplementedError("vendored scorer uses direct logits, no head projection")


class CudaCandidateScorer:
    def __init__(self, model_path, model_id, revision=None, max_input_tokens=4096,
                 temperature=1.0, **kw):
        from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
        self.model_path = model_path
        self.model_id = model_id
        self.temperature = temperature
        self.max_input_tokens = max_input_tokens
        self.device, self.dtype = ("cuda", torch.bfloat16) if torch.cuda.is_available() \
            else (("mps", torch.bfloat16) if torch.backends.mps.is_available()
                  else ("cpu", torch.float32))
        self.backbone = Qwen3_5ForConditionalGeneration.from_pretrained(
            model_path, dtype=self.dtype, low_cpu_mem_usage=True).to(self.device)
        self.backbone.eval()
        self.tok = AutoTokenizer.from_pretrained(model_path)
        self.tok.padding_side = "left"
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token

    def prepare(self, context, schema):
        from nimble.scoring.parallel_schema import prepare_prompts
        return prepare_prompts(self.tok, context, schema, self.max_input_tokens)

    def score(self, context, schema, mode="independent"):
        if mode != "independent":
            raise ValueError("vendored scorer supports independent mode only")
        prepared = self.prepare(context, schema)
        torch.cuda.synchronize() if self.device == "cuda" else None
        started = time.perf_counter()
        fields, output = {}, {}
        for name, choices, ids, candidates in zip(prepared.names, prepared.choices,
                                                   prepared.full_ids, prepared.candidate_ids):
            if len(ids) > self.max_input_tokens:
                raise ValueError(
                    f"Longest prompt has {len(ids)} tokens; limit is {self.max_input_tokens}. "
                    "Nothing was truncated.")
            tokens = torch.tensor([ids], device=self.device)
            with torch.no_grad():
                out = self.backbone(input_ids=tokens, use_cache=False, logits_to_keep=1)
            logits = out.logits[:, -1, :].float()[0]
            picked = logits[candidates]
            probs = torch.softmax(picked / self.temperature, -1)
            best = int(picked.argmax())
            keys = [choice_key(v) for v in choices]
            output[name] = choices[best]
            fields[name] = {
                "value": choices[best],
                "scores": dict(zip(keys, probs.tolist())),
                "logits": dict(zip(keys, picked.tolist())),
                "prompt_token_count": len(ids),
            }
        elapsed = time.perf_counter() - started
        return {"fields": fields, "output": output, "latency_s": elapsed}
