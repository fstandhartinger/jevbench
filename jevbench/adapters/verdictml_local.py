"""Verdict (`verdictml`, Manavarya09/verdict) adapter: open weights loaded in-process with the author's package.

Not the same system as `verdict_local.py` (heman10x's openJev Verdict). This one is the PyPI package `verdictml`
(import name `verdict`), Apache-2.0. Which weights: the package's default `verdict-small` checkpoint, which resolves
to the Hugging Face repo Manav2op/verdict-small, a 118M fine-tune of intfloat/multilingual-e5-small. Shipped
temperature is 1.0 and no calibrator is fitted on benchmark items: the distribution is the model's own softmax over
the option embeddings (native).

Interface (`pip install "verdictml[serve]"`, read 2026-09-24): the package's own /v1/systemone server maps Jev's
typed questions with `verdict.server.jev_question_to_verdict` and renders the state with `verdict.server.render_state`;
this adapter calls those two functions and then `Verdict(device=...).compile(question)(text)`, so an in-process run
sees exactly what the HTTP route would. The mapping of answers to exact-label probabilities is the one the `typesafe`
adapter applies to that route's response:
  choice  answer.distribution                    -> used as-is (keys = option labels)
  score   {str(k): p for k, p in distribution}   -> keys = level indices; the Question's scale is (0, n-1)
  noul    answer.probability = P(claim true)     -> {"yes": p, "no": 1-p}
Device is CPU unless the environment variable VERDICTML_DEVICE says otherwise. The encoder budget is 512 tokens;
longer states are truncated by the package itself, as its users would see. `verdict.server` imports FastAPI, so the
`serve` extra is required.

Local weights have no provider tariff: price is null here and estimated later by size class, never 0.
"""

from __future__ import annotations

import os
import time

from .base import NOUL_LABELS, DecisionResult, build_question

DEFAULT_MODEL = "verdict-small"  # the package's registry name for Manav2op/verdict-small


class VerdictMlLocalAdapter:
    name = "verdictml_local"
    cost_basis = "local_cpu_no_provider_tariff"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, threads=4, revision=None):
        self.path = endpoint  # optional local checkpoint directory; the registry name is the default
        self.model = model or endpoint or DEFAULT_MODEL
        self.key_env = key_env
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self.threads = threads
        self.revision = revision
        self.device = os.environ.get("VERDICTML_DEVICE") or "cpu"
        self._v = None
        self._to_question = None
        self._render = None

    def load(self):
        if self._v is None:
            import torch
            from verdict import Verdict
            from verdict.server import jev_question_to_verdict, render_state

            torch.set_num_threads(self.threads)
            self._v = Verdict(model=self.model, device=self.device)
            self._to_question = jev_question_to_verdict
            self._render = render_state
            import verdict
            self.verdict_version = getattr(verdict, "__version__", None)
        return self._v

    def build_request(self, task) -> dict:
        return {"state": task.state, "questions": {"decision": build_question(task)}}

    def run(self, task) -> DecisionResult:
        res = DecisionResult(adapter=self.name, ok=False, probs_source="native", model=self.model)
        body = self.build_request(task)
        res.request_body = body
        try:
            v = self.load()
        except Exception as e:  # noqa: BLE001 - a failed load is a failed attempt
            res.error = f"load failed: {type(e).__name__}: {str(e)[:250]}"
            return res
        t0 = time.perf_counter()
        try:
            q = self._to_question(body["questions"]["decision"])
            text = self._render(body["state"])
            ans = v.compile(q)(text)
        except Exception as e:  # noqa: BLE001
            res.latency_s = time.perf_counter() - t0
            res.error = f"{type(e).__name__}: {str(e)[:300]}"
            return res
        res.latency_s = time.perf_counter() - t0
        res.raw = {"response": ans.model_dump(mode="json") if hasattr(ans, "model_dump") else ans,
                   "runtime": {"device": self.device, "threads": self.threads, "revision": self.revision,
                               "verdictml": getattr(self, "verdict_version", None),
                               "probability_origin": "native-softmax"}}
        res.usage = {"input_tokens": len(text.split()), "output_tokens": 0}
        qtype = task.question["type"]
        try:
            if qtype == "noul":
                p = float(ans.probability)
                if not (0.0 <= p <= 1.0):
                    raise ValueError(f"noul out of range: {p}")
                res.probs = {NOUL_LABELS[1]: p, NOUL_LABELS[0]: 1.0 - p}
            else:
                dist = ans.distribution
                if not isinstance(dist, dict):
                    raise ValueError("missing distribution")
                res.probs = {str(k): float(p) for k, p in dist.items()}
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            res.error = f"answer parse failed: {e}"
            return res
        res.ok = True
        return res

    def reserve_estimate(self, task) -> float:
        return 0.0
