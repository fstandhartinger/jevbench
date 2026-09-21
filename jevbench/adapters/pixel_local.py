"""Pixel (LivioGama) adapter: the `pixel` CLI's deterministic zero-shot decision.

Pixel is a deterministic code/retrieval tool, not a trained Jev-class model. Its
`pixel classify` command embeds the question text and each option's criterion
with a static Model2Vec model (minishlab/potion-multilingual-128M) and maps
cosine similarities through a fixed-temperature softmax (tau = 0.07, CLIP's
value) — a real probability distribution produced offline with no LLM and no
network call. The mapping below is fixed before any run, per the additions rules.

Interface:
  `pixel classify --jsonl` serves one decision per stdin line:
    in : {"text": str, "labels": [str], "criteria": {label: str}}
    out: {"ok": true, "probs": {label: p}, "predicted": label, ...}
  The model stays resident between lines, matching the "model loaded before
  timing" convention used for the other local rows.

Task -> spec mapping (fixed, all 231 public items):
  text     = instructions + "\\n\\n" + state (state rendered as JSON when it is
             not a string)
  noul     criteria {"true","false"} -> {"yes": criteria["true"], "no": criteria["false"]}
  choice   criteria dict used as-is (keys are the labels)
  score    criteria list -> {"<level index>": level description}
  Missing criterion for a label falls back to the label text itself.

probabilities are the system's own softmax over cosine similarities (native).
Local binary, no provider tariff: cost is unmetered, never claimed as 0;
the row's Cost axis uses the size-class estimate documented in the row.
"""

from __future__ import annotations

import json
import subprocess
import time

from .base import DecisionResult, build_question


class PixelLocalAdapter:
    name = "pixel_local"
    cost_basis = "local_cpu_no_provider_tariff"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, threads=4, revision=None):
        self.binary = endpoint or "pixel"  # path to the pixel CLI
        self.model = model or "minishlab/potion-multilingual-128M"
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self.revision = revision
        self._proc = None

    def _ensure_proc(self):
        if self._proc is None or self._proc.poll() is not None:
            self._proc = subprocess.Popen(
                [self.binary, "classify", "--jsonl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        return self._proc

    def build_request(self, task) -> dict:
        q = build_question(task)
        criteria = {}
        raw = q.get("criteria")
        if q["type"] == "noul" and isinstance(raw, dict):
            criteria = {"yes": raw.get("true", "yes"), "no": raw.get("false", "no")}
        elif isinstance(raw, dict):
            criteria = {str(k): str(v) for k, v in raw.items()}
        elif isinstance(raw, list):
            criteria = {str(i): str(c) for i, c in enumerate(raw)}
        state = task.state if isinstance(task.state, str) else json.dumps(task.state)
        text = f'{q["instructions"]}\n\n{state}'
        return {"text": text, "labels": [str(l) for l in task.labels], "criteria": criteria}

    def reserve_estimate(self, task) -> float:
        return 0.0  # local binary, nothing billed

    def run(self, task) -> DecisionResult:
        res = DecisionResult(adapter=self.name, ok=False, probs_source="native", model=self.model)
        body = self.build_request(task)
        res.request_body = body
        t0 = time.perf_counter()
        try:
            proc = self._ensure_proc()
            proc.stdin.write(json.dumps(body) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
            res.latency_s = time.perf_counter() - t0
            if not line:
                res.error = "pixel classify exited without an answer"
                return res
            doc = json.loads(line)
            if not doc.get("ok"):
                res.error = str(doc.get("error"))[:300]
                return res
            probs = doc.get("probs") or {}
            res.probs = {l: float(probs[l]) for l in body["labels"] if l in probs}
            if len(res.probs) != len(body["labels"]):
                res.error = "probs did not cover the label set"
                res.probs = None
                return res
            res.ok = True
            res.raw = {"response": doc, "runtime": {"device": "cpu", "adapter": "jsonl-serve",
                                                    "revision": self.revision}}
        except Exception as e:  # noqa: BLE001 - a failed call is a failed attempt
            res.latency_s = time.perf_counter() - t0
            res.error = f"{type(e).__name__}: {str(e)[:300]}"
            self._proc = None
        return res
