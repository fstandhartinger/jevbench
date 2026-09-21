"""Metask-Jev-4B (wayfind/metask-jev-4b-policy-mix) adapter: open weights loaded
in-process, candidate-logit readout with per-kind temperature calibration.

A Qwen3.5-4B fine-tune (LoRA r16, merged) trained with the official Nimble
candidate cross-entropy objective on 44.8k view-augmented public decisions
plus 390 policy-family decisions with teacher soft labels. Apache-2.0.

Interface: the official Nimble prompt contract (prepare_prompts) and scoring
protocol (CudaCandidateScorer), reused unmodified — the same code path as the
Bespoke Nimble 9B entry, with two configuration differences:

  - max_input_tokens=4096 (the base model natively supports 262,144; the 9B
    pipeline's 2048 limit rejects 36 of the 111 public hard items)
  - per-kind temperature before the final softmax, fit by NLL on a held-out
    validation split (never on eval): choice 1.7875 / noul 2.25 / score 2.05.
    Raw ECE 0.100 -> 0.028.

Requires the vendored `nimble` package (github.com/bespokelabsai/nimble) on
PYTHONPATH and a CUDA GPU with BF16. Local weights have no provider tariff:
price is null here and estimated later by size class, never 0.

Model: https://huggingface.co/wayfind/metask-jev-4b-policy-mix
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time

from .base import DecisionResult

# default: the HF repo id — huggingface_hub resolves and caches it on first load.
# Set METASK_JEV_MODEL_PATH to a local merged-weights dir to skip the download.
DEFAULT_MODEL_PATH = os.environ.get("METASK_JEV_MODEL_PATH",
                                    "wayfind/metask-jev-4b-policy-mix")
_VENDORED = str(Path(__file__).resolve().parent.parent / "vendors" / "metask_jev")
NIMBLE_PACKAGE_PATH = os.environ.get("METASK_JEV_NIMBLE_PACKAGE", _VENDORED)

TEMPERATURE_BY_KIND = {"choice": 1.7875, "noul": 2.25, "score": 2.05}


class MetaskJevAdapter:
    name = "metask_jev"
    cost_basis = "local_gpu_no_provider_tariff"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, revision=None, **kw):
        self.model_path = endpoint or DEFAULT_MODEL_PATH
        self.model = model or "wayfind/metask-jev-4b-policy-mix"
        self.revision = revision
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self._scorer = None

    def load(self):
        if self._scorer is None:
            import torch
            if NIMBLE_PACKAGE_PATH not in __import__("sys").path:
                __import__("sys").path.insert(0, NIMBLE_PACKAGE_PATH)
            from nimble.scoring.cuda_scorer import CudaCandidateScorer
            t0 = time.perf_counter()
            self._scorer = CudaCandidateScorer(
                model_path=self.model_path,
                model_id=self.model,
                revision=self.revision,
                max_input_tokens=4096)
            self.load_s = time.perf_counter() - t0
            self.torch_version = torch.__version__
        return self._scorer

    def _labels_and_rubric(self, task):
        qtype = task.question["type"]
        crit = task.question.get("criteria")
        if qtype == "noul":
            # The official boolean contract keys choice_descriptions by
            # choice_key(choices) = 'false'/'true' (not 'no'/'yes'); the
            # harness maps back to no/yes on the result side.
            crit = crit or {}
            return ["no", "yes"], {"false": crit.get("false", "No"),
                                   "true": crit.get("true", "Yes")}
        if qtype == "score":
            labels = [str(i) for i in range(len(crit))]
            return labels, dict(zip(labels, crit))
        # choice: prepare_prompts assigns A/B/C by choices-list order and
        # requires choice_descriptions keys == choices values. task.labels is
        # the harness scoring order; criteria only supplies descriptions.
        labels = list(task.labels)
        rubric = {k: (crit.get(k) or k) for k in labels} if isinstance(crit, dict) \
            else {k: k for k in labels}
        return labels, rubric

    def run(self, task) -> DecisionResult:
        res = DecisionResult(adapter=self.name, ok=False, probs_source="native",
                             model=self.model)
        labels, rubric = self._labels_and_rubric(task)
        state = task.state if isinstance(task.state, str) else json.dumps(
            task.state, ensure_ascii=False)
        qtype = task.question["type"]
        field = {"description": task.question["instructions"]}
        if qtype == "noul":
            field.update(type="boolean", choices=[False, True], choice_descriptions=rubric)
        else:  # choice and score both map to enum
            field.update(type="enum", choices=labels, choice_descriptions=rubric)
        schema = {"decision": field}

        try:
            scorer = self.load()
        except Exception as e:  # noqa: BLE001
            res.error = f"load failed: {type(e).__name__}: {str(e)[:250]}"
            return res

        t0 = time.perf_counter()
        try:
            result = scorer.score(state, schema)
        except ValueError as e:
            # Over the prompt limit = the system refusing this input (422
            # semantics): scored wrong, does not trip the stop rule.
            res.latency_s = time.perf_counter() - t0
            if "limit is" in str(e):
                res.error = f"422 over context limit: {e}"
                res.status = 422
                res.raw = {"runtime": {"over_context": True, "detail": str(e)[:200]}}
                return res
            res.error = f"ValueError: {e}"
            return res
        except Exception as e:  # noqa: BLE001
            res.latency_s = time.perf_counter() - t0
            res.error = f"{type(e).__name__}: {str(e)[:300]}"
            return res
        res.latency_s = time.perf_counter() - t0

        field_out = result["fields"]["decision"]
        # Per-kind temperature on the raw candidate logits (the scorer's own
        # temperature is 1.0; refit here from logits so the value is explicit
        # in the raw record).
        logits_d = field_out["logits"]
        T = TEMPERATURE_BY_KIND.get(qtype, 1.0)
        mx = max(logits_d.values())
        exps = {k: math.exp(v / T - mx / T) for k, v in logits_d.items()}
        z = sum(exps.values())
        probs = {k: v / z for k, v in exps.items()}

        if qtype == "noul":
            res.probs = {"yes": float(probs["true"]), "no": float(probs["false"])}
        else:
            res.probs = {str(k): float(v) for k, v in probs.items()}
        res.probs = {k: res.probs[k] for k in labels}
        res.ok = True
        res.raw = {"probabilities": probs, "runtime": {
            "device": "cuda", "probability_origin": "native-candidate-softmax",
            "temperature_by_kind": TEMPERATURE_BY_KIND, "temperature_applied": T,
            "torch": getattr(self, "torch_version", None), "revision": self.revision}}
        return res

    def reserve_estimate(self, task) -> float:
        return 0.0