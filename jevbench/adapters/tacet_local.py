"""Tacet (CodePawl) adapter: open weights loaded in-process with the author's `tacet` package.

Interface (https://github.com/codepawl/tacet, `pip install "tacet>=0.3"`, Apache 2.0):
  model = tacet.load("codepawl/tacet-sonata", device="cuda")   # 144M packed encoder
  model.decide(state, {"decision": {type, instructions, criteria}})
It takes Jev's typed questions unchanged and answers in Jev's shape, so every JevBench record maps 1:1:
  noul   answer["noul"] = P(true)            -> {"yes": p, "no": 1 - p}
  choice answer["probabilities"]            -> used as-is (keys = options)
  score  answer["probabilities"]            -> used as-is (keys = level indices)
Probabilities are the model's own softmax over option markers (native). tacet 0.3 reads 4,096 tokens by
default, the length the model was trained at; TACET_MAX_LENGTH overrides it (256 to 4096).

Local weights have no provider tariff: price is null here and estimated later by size class, never 0.
"""

from __future__ import annotations

import os
import time

from .base import DecisionResult, build_question


class TacetLocalAdapter:
    name = "tacet_local"
    cost_basis = "local_gpu_no_provider_tariff"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, revision=None):
        self.path = endpoint or "codepawl/tacet-sonata"  # Hub repo id or a local snapshot
        self.model = model or "codepawl/tacet-sonata"
        self.key_env = key_env
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self.revision = revision
        self.device = os.environ.get("TACET_DEVICE", "auto")
        self._model = None

    def load(self):
        if self._model is None:
            import tacet

            options = {"device": self.device, "revision": self.revision}
            if os.environ.get("TACET_MAX_LENGTH"):
                options["max_length"] = int(os.environ["TACET_MAX_LENGTH"])
            self._model = tacet.load(self.path, **options)
            self.tacet_version = getattr(tacet, "__version__", None)
        return self._model

    @staticmethod
    def build_request(task) -> dict:
        return {"state": task.state, "questions": {"decision": build_question(task)}}

    @staticmethod
    def probabilities_from_answer(answer, question_type) -> dict:
        if not isinstance(answer, dict) or answer.get("type") != question_type:
            raise ValueError("missing or mistyped answers.decision")
        if question_type == "noul":
            probability_yes = float(answer["noul"])
            if not 0.0 <= probability_yes <= 1.0:
                raise ValueError(f"noul out of range: {probability_yes}")
            return {"yes": probability_yes, "no": 1.0 - probability_yes}
        probabilities = answer["probabilities"]
        if not isinstance(probabilities, dict):
            raise ValueError("missing probabilities")
        return {str(key): float(value) for key, value in probabilities.items()}

    def run(self, task) -> DecisionResult:
        result = DecisionResult(adapter=self.name, ok=False, probs_source="native", model=self.model)
        body = self.build_request(task)
        result.request_body = body
        try:
            model = self.load()
        except Exception as error:  # noqa: BLE001 - a failed load is a failed attempt
            result.error = f"load failed: {type(error).__name__}: {str(error)[:250]}"
            return result
        started = time.perf_counter()
        try:
            response = model.decide(body["state"], body["questions"])
        except Exception as error:  # noqa: BLE001
            result.latency_s = time.perf_counter() - started
            result.error = f"{type(error).__name__}: {str(error)[:300]}"
            return result
        result.latency_s = time.perf_counter() - started
        result.raw = {"response": response, "runtime": {"device": str(model.device), "max_length": model.max_length,
                                                        "tacet": getattr(self, "tacet_version", None),
                                                        "probability_origin": "native-softmax"}}
        result.usage = dict((response or {}).get("usage") or {})
        answer = ((response or {}).get("answers") or {}).get("decision")
        try:
            result.probs = self.probabilities_from_answer(answer, task.question["type"])
        except (KeyError, TypeError, ValueError) as error:
            result.error = f"answer parse failed: {error}"
            return result
        result.ok = True
        return result

    def reserve_estimate(self, task) -> float:
        return 0.0
