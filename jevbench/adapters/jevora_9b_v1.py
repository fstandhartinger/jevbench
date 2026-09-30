"""Local package adapter for the pinned public ``jevora-9b-v1`` release.

The adapter deliberately imports neither torch nor Jevora at module import
time.  A maintainer installs the pinned public Jevora checkout separately;
the first local decision then loads its verified release package through that
checkout's public ``jevora.model`` loader.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path
from typing import Any

from .base import DecisionResult


JEVORA_MODEL = "kadirbekovvv/jevora-9b-v1"
JEVORA_HF_REVISION = "c644b9c7a3b67b7acc3279523e3bee69a4be473d"
JEVORA_CODE_REPOSITORY = "https://github.com/doxanocap/jevora-9b-v1"
JEVORA_CODE_REVISION = "50027755772570d13bde8ec07503ec90ab893e01"
JEVORA_PACKAGE_MANIFEST_SHA256 = "5fdc127bfee88aa2c722c12194a045f18599ff6eb44b171a3551921735cc51b5"
JEVORA_MAX_LENGTH = 1024
JEVORA_MAX_OPTIONS = 255
PROBABILITY_SUM_TOLERANCE = 1e-6
OVERLENGTH_ERROR = re.compile(r"input has \d+ tokens, exceeds max_length=\d+")


class InputLimitExceeded(ValueError):
    """A valid task exceeds a documented, fixed package input limit."""


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_task(task) -> tuple[str, list[str]]:
    """Render only model-visible fields while preserving exact label order."""
    question = task.question
    labels = task.labels
    if not isinstance(question, dict):
        raise ValueError("task question must be an object")
    if not isinstance(labels, list) or not labels or any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("task labels must be a non-empty list of strings")
    if len(labels) != len(set(labels)):
        raise ValueError("task labels must be unique")

    kind = question.get("type")
    if kind not in {"choice", "noul", "score"}:
        raise ValueError(f"unsupported task type: {kind!r}")
    if kind == "noul" and labels != ["no", "yes"]:
        raise ValueError("Noul labels must be ordered exactly as ['no', 'yes']")
    if kind == "score" and labels != [str(index) for index in range(len(labels))]:
        raise ValueError("Score labels must be contiguous ordered level indices starting at '0'")
    if len(labels) < 2:
        raise ValueError("tasks require at least two options")
    if len(labels) > JEVORA_MAX_OPTIONS:
        raise InputLimitExceeded(f"over-options:{len(labels)}>{JEVORA_MAX_OPTIONS}")

    instructions = question.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("task question instructions must be a non-empty string")
    context = f"State:\n{_text(task.state)}\n\nQuestion:\n{instructions}"

    criteria = question.get("criteria")
    if kind == "noul":
        if criteria is not None and not isinstance(criteria, dict):
            raise ValueError("Noul criteria must be a map or null")
        criteria = criteria or {}
        options = [
            f"no: {_text(criteria.get('false', 'No'))}",
            f"yes: {_text(criteria.get('true', 'Yes'))}",
        ]
    elif isinstance(criteria, dict):
        if set(criteria) != set(labels):
            missing = sorted(set(labels) - set(criteria))
            extra = sorted(set(criteria) - set(labels))
            raise ValueError(f"criteria labels differ: missing={missing} extra={extra}")
        options = [f"{label}: {_text(criteria[label])}" for label in labels]
    elif isinstance(criteria, list):
        if len(criteria) != len(labels):
            raise ValueError("criteria list length must match ordered labels")
        options = [f"{label}: {_text(criteria[index])}" for index, label in enumerate(labels)]
    elif criteria is None:
        options = list(labels)
    else:
        raise ValueError("question criteria must be a map, list, or null")
    if any(not option.strip() for option in options):
        raise ValueError("rendered options must be non-empty")
    return context, options


def validate_probabilities(values: list[float], option_count: int) -> list[float]:
    """Reject incomplete or malformed native distributions instead of repairing them."""
    if not isinstance(values, list) or len(values) != option_count:
        actual = len(values) if isinstance(values, list) else "not-list"
        raise ValueError(f"probability-count:{actual}!={option_count}")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError("invalid-probability:value-must-be-finite-number-in-[0,1]")
    probabilities = [float(value) for value in values]
    if abs(sum(probabilities) - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise ValueError("invalid-probability:distribution-not-normalized")
    return probabilities


def _is_overlength(error: Exception) -> bool:
    return isinstance(error, ValueError) and OVERLENGTH_ERROR.fullmatch(str(error)) is not None


class Jevora9BV1Adapter:
    """Load only the verified nested Jevora package, never a raw checkpoint."""

    name = "jevora_9b_v1"
    price_input_per_m = None
    price_output_per_m = None
    cost_basis = "self_hosted_cost_not_priced"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, revision=None,
                 device="cuda"):
        if revision is not None and revision != JEVORA_HF_REVISION:
            raise ValueError(f"revision must be the pinned HF revision {JEVORA_HF_REVISION}")
        self.path = endpoint
        self.model = model or f"{JEVORA_MODEL}@{JEVORA_HF_REVISION}"
        self.revision = JEVORA_HF_REVISION
        self.device_name = device
        self.price_input_per_m = price_input_per_m
        self.price_output_per_m = price_output_per_m
        self._loaded = False

    def load(self):
        if self._loaded:
            return self._model
        if self.path is None:
            raise FileNotFoundError("--endpoint must point to the nested jevora-9b-v1 package directory")
        package = Path(self.path)
        manifest = package / "manifest.json"
        if not package.is_dir() or not manifest.is_file():
            raise FileNotFoundError(f"verified nested Jevora package is required: {package}")
        # Only the manifest published at the pinned HF revision crosses this trust boundary.
        if _sha256(manifest) != JEVORA_PACKAGE_MANIFEST_SHA256:
            raise ValueError("release package manifest does not match the pinned Jevora HF revision")
        try:
            import torch
            from jevora.model import PROMPT_V1, decision, load_release_package
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "install the pinned public Jevora checkout and add its src/ to PYTHONPATH"
            ) from error
        self._device = torch.device(self.device_name)
        self._model, self._tokenizer, self._metadata, self._temperature = load_release_package(package, self._device)
        if int(self._metadata.get("max_length", 0)) != JEVORA_MAX_LENGTH:
            raise ValueError("release package max_length differs from jevora-9b-v1 pin")
        if int(self._metadata.get("max_options", 0)) != JEVORA_MAX_OPTIONS:
            raise ValueError("release package max_options differs from jevora-9b-v1 pin")
        self._prompt_version = self._metadata.get("prompt_version", PROMPT_V1)
        self._decision = decision
        self._loaded = True
        return self._model

    def reserve_estimate(self, task):
        return None

    def run(self, task) -> DecisionResult:
        request_body = {"task_id": getattr(task, "id", None)}
        try:
            context, options = render_task(task)
            request_body.update({"context": context, "options": options})
            self.load()
            started = time.perf_counter()
            choice, values, input_tokens = self._decision(
                self._model, self._tokenizer, context, options,
                self._metadata["max_length"], self._device,
                self._prompt_version, self._temperature,
            )
            latency = time.perf_counter() - started
            probabilities = validate_probabilities(values, len(task.labels))
            if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < len(task.labels):
                raise ValueError("invalid-choice:index-out-of-range")
            if choice != max(range(len(probabilities)), key=probabilities.__getitem__):
                raise ValueError("invalid-choice:does-not-match-native-probability-argmax")
            mapped = dict(zip(task.labels, probabilities, strict=True))
            return DecisionResult(
                adapter=self.name,
                ok=True,
                probs=mapped,
                probs_source="native",
                model=self.model,
                latency_s=latency,
                usage={"input_tokens": input_tokens, "output_tokens": 0},
                request_body=request_body,
                raw={"choice": task.labels[choice], "probabilities": mapped,
                     "runtime": {"hf_revision": self.revision,
                                 "code_revision": JEVORA_CODE_REVISION,
                                 "probability_origin": "native_jevora_decision_head_softmax",
                                 "temperature_source": "verified_package_calibration"}},
            )
        except Exception as error:
            # JevBench treats documented input limits as 422, not infrastructure failures.
            over_limit = isinstance(error, InputLimitExceeded) or _is_overlength(error)
            return DecisionResult(
                adapter=self.name,
                ok=False,
                probs_source="native",
                model=self.model,
                status=422 if over_limit else None,
                error=f"{type(error).__name__}: {error}",
                request_body=request_body,
            )
