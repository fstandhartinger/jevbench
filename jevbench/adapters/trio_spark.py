"""MachineFi Trio-Spark production API adapter.

Trio-Spark exposes one bounded Choice per request and returns native
probabilities for every option. JevBench's Noul and Score primitives are mapped
to choices without changing their labels or order.
"""

from __future__ import annotations

import os
import uuid

from .base import DecisionResult, http_post_json


class TrioSparkAdapter:
    name = "trio_spark"

    def __init__(self, endpoint=None, model=None, key_env="TRIO_SPARK_API_KEY",
                 timeout_s=120.0, price_input_per_m=None,
                 price_output_per_m=0.0):
        self.endpoint = (endpoint or os.environ.get("TRIO_SPARK_ENDPOINT")
                         or "https://platform.machinefi.com/api/spark/v1/decisions")
        self.model = model or os.environ.get("TRIO_SPARK_MODEL") or "trio-spark-preview"
        self.key_env = key_env
        self.timeout_s = timeout_s
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m

    @staticmethod
    def criteria(task) -> dict[str, str]:
        qtype = task.question["type"]
        criteria = task.question.get("criteria") or {}
        if qtype == "noul":
            return {
                "no": criteria.get("false") or "The statement is false",
                "yes": criteria.get("true") or "The statement is true",
            }
        if qtype == "score":
            return {str(i): str(level) for i, level in enumerate(criteria)}
        return {str(key): str(value) for key, value in criteria.items()}

    def build_request(self, task) -> dict:
        criteria = self.criteria(task)
        if not 2 <= len(criteria) <= 8:
            raise ValueError("Trio-Spark accepts 2 to 8 choices")
        state = task.state if isinstance(task.state, dict) else {"observation": task.state}
        return {
            "model": self.model,
            "task": task.question["instructions"],
            "state": state,
            "choices": [
                {"id": label, "description": description}
                for label, description in criteria.items()
            ],
        }

    def run(self, task) -> DecisionResult:
        key = os.environ.get(self.key_env, "") if self.key_env else ""
        if self.key_env and not key:
            return DecisionResult(
                adapter=self.name, ok=False, error=f"missing env key {self.key_env}",
                probs_source="native", model=self.model,
            )
        try:
            body = self.build_request(task)
        except ValueError as exc:
            return DecisionResult(
                adapter=self.name, ok=False, error=str(exc), probs_source="native",
                model=self.model,
            )
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
            "User-Agent": "JevBench/1.4 Trio-Spark adapter",
        }
        try:
            status, parsed, latency = http_post_json(
                self.endpoint, body, headers, self.timeout_s
            )
        except ConnectionError as exc:
            return DecisionResult(
                adapter=self.name, ok=False, error=str(exc), probs_source="native",
                model=self.model, request_body=body,
            )
        result = DecisionResult(
            adapter=self.name, ok=False, status=status, latency_s=latency,
            probs_source="native", model=self.model, raw=parsed,
            request_body=body,
        )
        if status != 200 or not isinstance(parsed, dict):
            result.error = f"HTTP {status}: {str(parsed)[:300]}"
            return result
        raw_probs = parsed.get("probabilities")
        if isinstance(raw_probs, list):
            try:
                probs = {str(item.get("choice_id", item.get("id"))): float(item["probability"])
                         for item in raw_probs}
            except (KeyError, TypeError, ValueError):
                probs = None
        elif isinstance(raw_probs, dict):
            try:
                probs = {str(key): float(value) for key, value in raw_probs.items()}
            except (TypeError, ValueError):
                probs = None
        else:
            probs = None
        if probs is None:
            result.error = "response missing a valid probabilities distribution"
            return result
        expected_labels = set(task.labels)
        if set(probs) != expected_labels:
            result.error = "response probability labels do not match the task"
            return result
        result.probs = probs
        usage = dict(parsed.get("usage") or {})
        if "input_tokens" not in usage and "billed_input_tokens" in usage:
            usage["input_tokens"] = usage["billed_input_tokens"]
        usage.setdefault("output_tokens", 0)
        result.usage = usage
        result.model = parsed.get("model") or self.model
        result.ok = True
        return result

    def reserve_estimate(self, task) -> float:
        price = self.price_input_per_m
        if price is None:
            price = float(os.environ.get("TRIO_SPARK_PRICE_INPUT_PER_M", "0.042"))
        return 100_000 * price / 1e6
