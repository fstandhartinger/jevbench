"""In-process adapter for gnumanth/nullspan's public System One weights.

Nullspan (ModernBERT-large 395M + ParallelSpanDecisionHead) scores all options
of a typed `noul`, `choice`, or `score` decision in a single bidirectional
encoder forward pass with 0 generated output tokens. Imports of `nullspan` and
its ML dependencies are lazy so the standard JevBench test suite runs offline
without downloading model weights.
"""

from __future__ import annotations

import hashlib
import json
import time

from .base import DecisionResult


class NullspanLocalAdapter:
    name = "nullspan_local"
    cost_basis = "self_hosted_gpu"
    DEFAULT_MODEL = "gnumanth/nullspan"
    DEFAULT_REVISION = "51acf9e097ade3fb1068b3511490ef2756485927"

    def __init__(
        self,
        endpoint=None,
        model=None,
        key_env="",
        timeout_s=None,
        price_input_per_m=None,
        price_output_per_m=None,
        revision=None,
    ):
        self.endpoint = endpoint or model or self.DEFAULT_MODEL
        self.model = model or endpoint or self.DEFAULT_MODEL
        if revision is not None:
            self.revision = revision
        elif self.endpoint == self.DEFAULT_MODEL:
            self.revision = self.DEFAULT_REVISION
        else:
            self.revision = None
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self._loaded = None
        self.load_s = 0.0

    def load(self):
        if self._loaded is None:
            from nullspan.systemone import NullspanSystemOneEngine

            started = time.perf_counter()
            self._loaded = NullspanSystemOneEngine.load_from_dir(
                self.endpoint, revision=self.revision
            )
            self.load_s = time.perf_counter() - started
        return self._loaded

    @staticmethod
    def build_request(task) -> dict:
        qtype = task.question["type"]
        instructions = task.question["instructions"]
        criteria = task.question.get("criteria")
        if qtype == "noul":
            q: dict = {"type": "noul", "instructions": instructions}
            if criteria is not None:
                q["criteria"] = criteria
        elif qtype == "score":
            if isinstance(criteria, list) and len(criteria) == len(task.labels):
                levels = [criteria[int(label)] for label in task.labels]
            else:
                levels = [f"Level {label}" for label in task.labels]
            q = {"type": "score", "instructions": instructions, "criteria": levels}
        else:
            cdict = criteria if isinstance(criteria, dict) else {}
            q = {
                "type": "choice",
                "instructions": instructions,
                "criteria": {label: (cdict.get(label) or label) for label in task.labels},
            }
        return {"state": task.state, "questions": {"decision": q}}

    def run(self, task) -> DecisionResult:
        result = DecisionResult(
            adapter=self.name,
            ok=False,
            probs_source="native",
            model=self.model,
        )
        row = self.build_request(task)
        state_bytes = (
            row["state"]
            if isinstance(row["state"], str)
            else json.dumps(row["state"], ensure_ascii=False, sort_keys=True)
        ).encode("utf-8")
        result.request_body = {
            "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
            "questions": row["questions"],
        }
        started = time.perf_counter()
        try:
            engine = self.load()
            infer_t0 = time.perf_counter()
            out = engine.decide(row["state"], row["questions"])
            result.latency_s = time.perf_counter() - infer_t0
            ans = (out.get("answers") or {})["decision"]
            usage = out.get("usage") or {}
            qtype = task.question["type"]
            if qtype == "noul":
                p = float(ans["noul"])
                if not (0.0 <= p <= 1.0):
                    raise ValueError(f"noul probability out of range: {p}")
                probs = {"yes": p, "no": 1.0 - p}
            else:
                raw_probs = ans["probabilities"]
                probs = {label: float(raw_probs[label]) for label in task.labels}
            if not (0.999 <= sum(probs.values()) <= 1.001):
                raise ValueError("probabilities do not sum to one")
            result.probs = probs
            result.usage = {
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": 0,
            }
            result.raw = {
                "answer": ans,
                "runtime": {
                    "checkpoint": self.endpoint,
                    "revision": self.revision,
                    "generated_tokens": 0,
                    "probability_origin": "native-parallel-span-softmax",
                    "load_s": self.load_s,
                },
            }
            result.ok = True
        except Exception as exc:  # noqa: BLE001
            result.latency_s = time.perf_counter() - started
            result.error = f"{type(exc).__name__}: {str(exc)[:300]}"
        return result

    def reserve_estimate(self, task) -> float:
        return 0.0
