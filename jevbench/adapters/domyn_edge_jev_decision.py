"""Domyn-Edge-Jev-Decision adapter: a single-forward-pass typed-decision model built on Domyn-Edge-SFT (3.93B).

The model answers in ONE forward pass with zero generated tokens: the prompt is rendered to the decision position
and the next-token distribution over single-token option codes (A, B, ... at that position) is the native
categorical answer. Weights: deshwalmahesh/domyn-edge-jev-decision (open, loaded in-process). No calibrator is baked in
(temperature 1.0); the raw native distribution is returned.

Rendering (shared by training, eval and here — train == serve):
  "Answer the question ... State:\\n{state}\\n\\nQuestion: {q}\\n\\nOptions:\\n{A: opt0}\\n{B: opt1}... Reply with
  only the option code." via the model's chat template (no thinking), read at the generation position.

Numerics: the LM head and the RoPE angle math run in fp32 even under bf16 (option logits sit ~30-36 where one bf16
step moves a probability by several %); this matches the model's training/eval harness.
"""
from __future__ import annotations

import itertools
import json
import string
import time

from .base import DecisionResult

PROMPT = ("Answer the question about the state with exactly one option code.\n\n"
          "State:\n{state}\n\nQuestion: {question}\n\nOptions:\n{options}\n\nReply with only the option code.")
DEFAULT_MODEL = "deshwalmahesh/domyn-edge-jev-decision"
MAX_CODES = 255


def _opt(label, desc):
    return f"{label} — {desc}" if desc else str(label)


def _fp32_head(model):
    head = model.get_output_embeddings()
    if head is None or getattr(head, "_fp32_wrapped", False):
        return
    head.register_forward_hook(lambda mod, inp, out: out.float())
    head._fp32_wrapped = True


def _fp32_rotary(model):
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    for m in model.modules():
        if any(n == "inv_freq" for n, _ in m.named_buffers(recurse=False)) and not getattr(m, "_fp32_wrapped", False):
            plain = m.forward

            def fwd(*a, _p=plain, **k):
                with torch.autocast(device_type=dev, enabled=False):
                    return _p(*a, **k)
            m.forward = fwd
            m._fp32_wrapped = True


def _option_codes(tok, tail):
    """Single-token codes (A..Z, AA..) that are exactly one token right at the decision position."""
    prefix = tok.encode(tail, add_special_tokens=False)
    codes, seen = [], set()
    for c in list(string.ascii_uppercase) + ["".join(p) for p in itertools.product(string.ascii_uppercase, repeat=2)]:
        ids = tok.encode(tail + c, add_special_tokens=False)
        if ids[:-1] == prefix and len(ids) == len(prefix) + 1 and ids[-1] not in seen:
            codes.append((c, tok.convert_ids_to_tokens(ids[-1])))
            seen.add(ids[-1])
            if len(codes) == MAX_CODES:
                break
    return codes


class DomynEdgeJevDecisionAdapter:
    name = "domyn_edge_jev_decision"
    cost_basis = "self_hosted_gpu"

    def __init__(self, endpoint=None, model=None, key_env="", timeout_s=None,
                 price_input_per_m=None, price_output_per_m=None, revision=None, **_):
        # Cost: open weights, zero generated tokens -> a model-price estimate (DeepInfra Qwen3.5-4B-class input rate),
        # not a GPU bill, consistent with how other open-weight 4B rows are priced on the board.
        self.price_input_per_m = 0.04 if price_input_per_m is None else price_input_per_m
        self.price_output_per_m = 0.0 if price_output_per_m is None else price_output_per_m
        self.model_id = model or endpoint or DEFAULT_MODEL
        self.revision = revision
        self._loaded = False

    def load(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self._torch = torch
        self.tok = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id, revision=self.revision, trust_remote_code=True,
            dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32)
        _fp32_head(self.model)
        _fp32_rotary(self.model)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device).eval()
        tail = self.tok.apply_chat_template([{"role": "user", "content": "x"}], tokenize=False,
                                            add_generation_prompt=True, enable_thinking=False)
        self.codes = _option_codes(self.tok, tail)
        self._loaded = True

    def reserve_estimate(self, task):
        return 0.0

    def _keys_texts(self, task):
        q = task.question
        t, crit = q["type"], q.get("criteria")
        if t == "noul":
            keys = texts = ["yes", "no"]
        elif t == "score":
            texts = [str(c) for c in (crit or task.labels)]
            keys = [str(i) for i in range(len(texts))]
        elif isinstance(crit, dict):
            keys = list(crit)
            texts = [_opt(k, crit[k]) for k in keys]
        else:
            keys = [str(k) for k in (crit or task.labels)]
            texts = list(keys)
        state = task.state if isinstance(task.state, str) else json.dumps(task.state, ensure_ascii=False, sort_keys=True)
        return keys, texts, q["instructions"], state

    def run(self, task):
        if not self._loaded:
            self.load()
        torch = self._torch
        try:
            keys, texts, instr, state = self._keys_texts(task)
            lines = "\n".join(f"{self.codes[i][0]}: {t}" for i, t in enumerate(texts))
            user = PROMPT.format(state=state, question=instr, options=lines)
            text = self.tok.apply_chat_template([{"role": "user", "content": user}], tokenize=False,
                                                add_generation_prompt=True, enable_thinking=False)
            enc = self.tok(text, return_tensors="pt").to(self.device)
            oid = torch.tensor([self.tok.convert_tokens_to_ids(self.codes[i][1]) for i in range(len(keys))],
                               device=self.device)
            t0 = time.perf_counter()
            ctx = torch.autocast("cuda", dtype=torch.bfloat16) if self.device == "cuda" \
                else torch.autocast("cpu", enabled=False)
            with torch.no_grad(), ctx:
                logits = self.model(**enc, logits_to_keep=1, use_cache=False).logits[:, -1, :].float()
            p = torch.softmax(logits[0, oid], -1).tolist()
            return DecisionResult(
                adapter=self.name, ok=True, probs={keys[i]: float(p[i]) for i in range(len(keys))},
                probs_source="native", model=self.model_id, latency_s=time.perf_counter() - t0,
                usage={"input_tokens": int(enc["input_ids"].shape[1]), "output_tokens": 0},
                request_body={"n_options": len(keys)}, raw={"runtime": {"device": self.device}})
        except Exception as e:  # one decision, no retries: surface failures as ok=False, never raise
            return DecisionResult(adapter=self.name, ok=False, error=f"{type(e).__name__}: {e}")
