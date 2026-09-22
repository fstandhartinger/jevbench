"""Native option probabilities from the Qwen3.8 Flash Next BF16 linear runtime.

The author-operated runtime exposes /v1/choice, not TypeSafe's /v1/systemone.
Every task becomes one question with the complete option rubric. Only state,
question type, instructions and option descriptions are sent, never gold data.

The runtime uses an 86-row original BF16 head over a mixed NVFP4/FP8 backbone.
Probabilities are conditional native label probabilities, not generated numbers
or a claim of calibrated correctness. Self-hosted compute has no provider tariff.
See docs/qwen-flash-linear.md for pinned weights, runtime and known limitations.
"""
from __future__ import annotations

import json
import math
import os

from .base import DecisionResult, http_post_json


class QwenFlashLinearAdapter:
    name = "qwen_flash_linear"
    cost_basis = "local_existing_gpu_compute_unpriced"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=120.0,
                 price_input_per_m=None, price_output_per_m=None):
        self.endpoint = (endpoint or "http://127.0.0.1:8239").rstrip("/")
        self.model = model or "WIlfLin/JEV-Qwen3.8-Flash-Next-Linear-Runtime"
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m

    @staticmethod
    def build_request(task) -> dict:
        q = task.question
        criteria = q.get("criteria")
        options = []
        for label in task.labels:
            if q["type"] == "noul":
                description = (criteria or {}).get("true" if label == "yes" else "false")
            elif q["type"] == "score":
                description = criteria[int(label)]
            else:
                description = criteria.get(label) if isinstance(criteria, dict) else None
            text = description if isinstance(description, str) else json.dumps(description, ensure_ascii=False)
            options.append(label if description is None else f"{label}: {text}")
        state = task.state if isinstance(task.state, str) else json.dumps(task.state, ensure_ascii=False)
        return {"question": f'State:\n{state}\n\nQuestion type: {q["type"]}\nInstructions:\n{q["instructions"]}',
                "options": options}

    def run(self, task) -> DecisionResult:
        body = self.build_request(task)
        res = DecisionResult(adapter=self.name, ok=False, probs_source="native", model=self.model,
                             request_body=body)
        if not 2 <= len(body["options"]) <= 86:
            res.error = "Runtime supports 2–86 options; no truncation or fallback"
            return res
        headers = {"Content-Type": "application/json"}
        if self.key_env:
            key = os.environ.get(self.key_env)
            if not key:
                res.error = f"Missing key environment variable: {self.key_env}"
                return res
            headers["Authorization"] = f"Bearer {key}"
        try:
            status, parsed, latency = http_post_json(
                f"{self.endpoint}/v1/choice", body, headers, self.timeout_s)
        except ConnectionError as error:
            res.error = str(error)
            return res
        res.status, res.raw, res.latency_s = status, parsed, latency
        if status != 200 or not isinstance(parsed, dict):
            res.error = f"HTTP {status}: response is not a successful choice result"
            return res
        try:
            options = parsed["options"]
            if not isinstance(options, list) or len(options) != len(task.labels):
                raise ValueError("Response option count does not match the request")
            probs = {}
            for index, (label, option) in enumerate(zip(task.labels, options), 1):
                if not isinstance(option, dict) or type(option.get("index")) is not int or option["index"] != index:
                    raise ValueError("Response option indices must preserve request order")
                value = option["probability"]
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("Invalid native probability")
                probs[label] = float(value)
            # Preserve raw values; the shared harness owns sum validation.
            res.probs = probs
            if type(parsed.get("input_tokens")) is int and parsed["input_tokens"] >= 0:
                res.usage = {"input_tokens": parsed["input_tokens"], "output_tokens": 1}
        except (KeyError, TypeError, ValueError) as error:
            res.error = f"Invalid choice response: {error}"
            return res
        res.ok = True
        return res

    def reserve_estimate(self, task) -> float:
        # Local compute is unpriced, not free. No billed API spend is reserved.
        return 0.0
