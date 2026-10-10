"""Offline unit tests for jevbench/adapters/openai_compat.py and remote_inproc.py.

The HTTP layer is mocked: either the module-level `http_post_json` each adapter
imports from `.base`, or `urllib.request.urlopen` underneath it (to pin how a
timeout or an HTTP error status reaches the adapter). No test opens a socket.
The assertions pin today's behaviour exactly, including the absence of retries.
"""
import io
import json
import socket
import urllib.error

import pytest

from jevbench.adapters import base as base_mod
from jevbench.adapters import openai_compat as oc_mod
from jevbench.adapters import remote_inproc as ri_mod
from jevbench.adapters.openai_compat import OpenAICompatAdapter
from jevbench.adapters.remote_inproc import RemoteInprocAdapter
from jevbench.tasks import Task

KEY_ENV = "JEVBENCH_TEST_OPENAI_COMPAT_KEY"


def noul_task():
    return Task(id="t1", family="fam", state={"x": 1},
                question={"type": "noul", "instructions": "decide"},
                labels=["no", "yes"], expected="yes", split="public", group="g1",
                provenance={"source": "secret"})


def completion(content, usage=None, model="served-model"):
    body = {"id": "c1", "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]}
    if usage is not None:
        body["usage"] = usage
    return body


class FakePost:
    """Stand-in for http_post_json: replays canned (status, parsed, latency) or raises."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, body, headers, timeout_s):
        self.calls.append({"url": url, "body": body, "headers": headers, "timeout_s": timeout_s})
        r = self.responses.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.setenv(KEY_ENV, "sk-test")
    return OpenAICompatAdapter("http://llm.invalid/v1/", "req-model", key_env=KEY_ENV,
                               timeout_s=7.5, price_input_per_m=2.0, price_output_per_m=8.0)


def use(monkeypatch, *responses):
    fake = FakePost(*responses)
    monkeypatch.setattr(oc_mod, "http_post_json", fake)
    return fake


# --- normal typed answer --------------------------------------------------

def test_typed_answer_ok(adapter, monkeypatch):
    content = json.dumps({"probabilities": {"no": 0.25, "yes": 0.75}})
    fake = use(monkeypatch, (200, completion(content, {"prompt_tokens": 120, "completion_tokens": 9}), 0.42))
    r = adapter.run(noul_task())
    assert r.ok is True and r.error is None
    assert r.probs == {"no": 0.25, "yes": 0.75}
    assert r.probs_source == "verbalized"
    assert r.status == 200 and r.latency_s == 0.42
    assert r.model == "served-model"  # the served model name wins over the requested one
    assert r.adapter == "openai_compat"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "http://llm.invalid/v1/chat/completions"  # trailing slash stripped
    assert call["headers"] == {"Authorization": "Bearer sk-test", "Content-Type": "application/json"}
    assert call["timeout_s"] == 7.5
    assert r.request_body is call["body"]
    assert call["body"]["model"] == "req-model"
    assert call["body"]["response_format"]["json_schema"]["schema"]["properties"]["probabilities"]["required"] == ["no", "yes"]
    assert "secret" not in json.dumps(call["body"]) and "expected" not in json.dumps(call["body"])


def test_model_falls_back_to_requested_name(adapter, monkeypatch):
    body = completion(json.dumps({"probabilities": {"no": 1, "yes": 0}}))
    del body["model"]
    use(monkeypatch, (200, body, 0.1))
    r = adapter.run(noul_task())
    assert r.ok and r.model == "req-model" and r.probs == {"no": 1, "yes": 0}


def test_missing_key_makes_no_request(monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    fake = use(monkeypatch)
    r = OpenAICompatAdapter("http://llm.invalid", "m", key_env=KEY_ENV).run(noul_task())
    assert fake.calls == []
    assert (r.ok, r.error, r.status, r.probs_source, r.model) == (
        False, f"missing env key {KEY_ENV}", None, "verbalized", "m")


def test_request_options_override_and_remove(adapter, monkeypatch):
    adapter.request_options = {"temperature": None, "response_format": {"type": "json_object"}, "seed": 3}
    fake = use(monkeypatch, (200, completion('{"probabilities": {"no": 0.5, "yes": 0.5}}'), 0.1))
    assert adapter.run(noul_task()).ok
    sent = fake.calls[0]["body"]
    assert "temperature" not in sent
    assert sent["response_format"] == {"type": "json_object"} and sent["seed"] == 3


# --- probability extraction -------------------------------------------------

@pytest.mark.parametrize("content,probs", [
    # visible thought channel before the final JSON
    ('<think>maybe {"draft": 1}</think>\n{"probabilities": {"no": 0.1, "yes": 0.9}}', {"no": 0.1, "yes": 0.9}),
    # several complete candidates: the last one is taken
    ('{"probabilities": {"no": 0.9, "yes": 0.1}} then {"probabilities": {"no": 0.3, "yes": 0.7}}', {"no": 0.3, "yes": 0.7}),
    # markdown fence around the object
    ('```json\n{"probabilities": {"no": 0.4, "yes": 0.6}}\n```', {"no": 0.4, "yes": 0.6}),
    # an object nested under another key is still picked up by the scan
    ('{"answer": {"probabilities": {"no": 0.2, "yes": 0.8}}}', {"no": 0.2, "yes": 0.8}),
    # no label or range validation here; the scorer does that downstream
    ('{"probabilities": {"maybe": 2, "yes": "x"}}', {"maybe": 2, "yes": "x"}),
])
def test_probability_extraction(adapter, monkeypatch, content, probs):
    use(monkeypatch, (200, completion(content), 0.1))
    r = adapter.run(noul_task())
    assert r.ok is True and r.probs == probs and r.error is None


# --- malformed JSON / missing fields --------------------------------------

@pytest.mark.parametrize("content,error", [
    ("not json at all", "verbalized distribution parse failed: Expecting value: line 1 column 1 (char 0)"),
    ('{"probabilities": {"no": 0.5, "yes": 0.5}', "verbalized distribution parse failed: Expecting ',' delimiter: line 1 column 42 (char 41)"),
    ("", "verbalized distribution parse failed: Expecting value: line 1 column 1 (char 0)"),
    ('{"probs": {"no": 0.5, "yes": 0.5}}', "verbalized distribution parse failed: JSON does not match schema"),
    ('{"probabilities": {"no": 0.5, "yes": 0.5}, "note": "x"}', "verbalized distribution parse failed: JSON does not match schema"),
    ('[{"no": 0.5}]', "verbalized distribution parse failed: JSON does not match schema"),
    ('{"probabilities": [0.5, 0.5]}', "verbalized distribution parse failed: probabilities is not an object"),
    ('{"probabilities": null}', "verbalized distribution parse failed: probabilities is not an object"),
])
def test_unparseable_content(adapter, monkeypatch, content, error):
    use(monkeypatch, (200, completion(content, {"prompt_tokens": 10, "completion_tokens": 3}), 0.2))
    r = adapter.run(noul_task())
    assert r.ok is False and r.probs is None and r.error == error
    assert r.status == 200 and r.latency_s == 0.2
    # usage is still recorded for a parse failure
    assert r.usage["input_tokens"] == 10 and r.usage["output_tokens"] == 3


def test_null_content_is_parse_failure(adapter, monkeypatch):
    use(monkeypatch, (200, completion(None), 0.1))
    r = adapter.run(noul_task())
    assert not r.ok and r.error == "verbalized distribution parse failed: Expecting value: line 1 column 1 (char 0)"


def test_list_content_is_parse_failure(adapter, monkeypatch):
    use(monkeypatch, (200, completion([{"type": "text", "text": "{}"}]), 0.1))
    r = adapter.run(noul_task())
    assert not r.ok
    assert r.error == "verbalized distribution parse failed: the JSON object must be str, bytes or bytearray, not list"


@pytest.mark.parametrize("parsed", [{"model": "m"}, {"choices": []}, {"choices": None}])
def test_no_choices(adapter, monkeypatch, parsed):
    use(monkeypatch, (200, parsed, 0.1))
    r = adapter.run(noul_task())
    assert not r.ok and r.error == "no choices in response" and r.usage == {}
    assert r.raw is parsed


def test_choice_without_message(adapter, monkeypatch):
    use(monkeypatch, (200, {"choices": [{"finish_reason": "length"}]}, 0.1))
    r = adapter.run(noul_task())
    assert not r.ok and r.error == "verbalized distribution parse failed: Expecting value: line 1 column 1 (char 0)"


def test_non_dict_choice_raises(adapter, monkeypatch):
    # Current behaviour: escapes as AttributeError; the runner turns that into
    # DecisionResult(error="AttributeError") and drops status and raw body.
    use(monkeypatch, (200, {"choices": [None]}, 0.1))
    with pytest.raises(AttributeError):
        adapter.run(noul_task())


def test_200_with_non_json_body(adapter, monkeypatch):
    use(monkeypatch, (200, "<html>gateway</html>", 0.1))
    r = adapter.run(noul_task())
    assert not r.ok and r.error == "HTTP 200: <html>gateway</html>"
    assert r.model == "req-model" and r.raw == "<html>gateway</html>"


# --- HTTP 429 / 5xx: no retries in this adapter ---------------------------

@pytest.mark.parametrize("status", [400, 401, 429, 500, 502, 503, 529])
def test_error_status_returned_once_without_retry(adapter, monkeypatch, status):
    err = {"error": {"message": "slow down", "type": "rate_limit"}}
    fake = use(monkeypatch, (status, err, 0.3),
               (200, completion('{"probabilities": {"no": 0.5, "yes": 0.5}}'), 0.1))
    r = adapter.run(noul_task())
    assert len(fake.calls) == 1  # the queued 200 is never requested
    assert r.ok is False and r.status == status and r.latency_s == 0.3
    assert r.error == f"HTTP {status}: {str(err)}"
    assert r.probs is None and r.usage == {} and r.raw is err


def test_error_body_truncated_to_300_chars(adapter, monkeypatch):
    use(monkeypatch, (500, "x" * 1000, 0.1))
    r = adapter.run(noul_task())
    assert r.error == "HTTP 500: " + "x" * 300


# --- timeouts / network errors --------------------------------------------

def test_connection_error_from_transport(adapter, monkeypatch):
    fake = use(monkeypatch, ConnectionError("TimeoutError: timed out"))
    r = adapter.run(noul_task())
    assert len(fake.calls) == 1
    assert (r.ok, r.error, r.status, r.latency_s, r.raw, r.request_body) == (
        False, "TimeoutError: timed out", None, 0.0, None, None)
    assert r.probs_source == "verbalized" and r.model == "req-model"


def test_timeout_through_real_http_post_json(adapter, monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["timeout"] = timeout
        seen["url"] = req.full_url
        raise socket.timeout("timed out")

    monkeypatch.setattr(base_mod.urllib.request, "urlopen", fake_urlopen)
    r = adapter.run(noul_task())
    assert seen == {"timeout": 7.5, "url": "http://llm.invalid/v1/chat/completions"}
    assert not r.ok and r.status is None and r.error == "TimeoutError: timed out"


def test_http_error_through_real_http_post_json(adapter, monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {},
                                     io.BytesIO(b'{"error": "rate"}'))

    monkeypatch.setattr(base_mod.urllib.request, "urlopen", fake_urlopen)
    r = adapter.run(noul_task())
    assert not r.ok and r.status == 429 and r.error == "HTTP 429: {'error': 'rate'}"


def test_other_exceptions_propagate(adapter, monkeypatch):
    use(monkeypatch, RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        adapter.run(noul_task())


# --- token / cost accounting ----------------------------------------------

@pytest.mark.parametrize("usage,expected", [
    ({"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
     {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "input_tokens": 100, "output_tokens": 20}),
    ({"input_tokens": 50, "output_tokens": 5},
     {"input_tokens": 50, "output_tokens": 5}),
    # OpenAI-style names win when both are present
    ({"prompt_tokens": 1, "completion_tokens": 2, "input_tokens": 9, "output_tokens": 9},
     {"prompt_tokens": 1, "completion_tokens": 2, "input_tokens": 1, "output_tokens": 2}),
    (None, {"input_tokens": None, "output_tokens": None}),
    ({}, {"input_tokens": None, "output_tokens": None}),
])
def test_usage_normalisation(adapter, monkeypatch, usage, expected):
    use(monkeypatch, (200, completion('{"probabilities": {"no": 0.5, "yes": 0.5}}', usage), 0.1))
    r = adapter.run(noul_task())
    assert r.ok and r.usage == expected


def test_reserve_estimate():
    a = OpenAICompatAdapter("http://x", "m", price_input_per_m=2.0, price_output_per_m=8.0)
    assert a.reserve_estimate(noul_task()) == pytest.approx(100_000 * 2.0 / 1e6 + 4_000 * 8.0 / 1e6)
    assert a.reserve_estimate(noul_task()) == pytest.approx(0.232)
    assert OpenAICompatAdapter("http://x", "m", price_input_per_m=0.0, price_output_per_m=0.0).reserve_estimate(None) == 0.0
    assert OpenAICompatAdapter("http://x", "m", price_input_per_m=1.0).reserve_estimate(None) is None
    assert OpenAICompatAdapter("http://x", "m").reserve_estimate(None) is None
    assert not hasattr(OpenAICompatAdapter, "cost_basis")


@pytest.mark.xfail(strict=True, reason="BUG: run() writes input_tokens/output_tokens into the "
                   "provider's own usage dict, so DecisionResult.raw (the 'preserved response "
                   "body' the runner hashes and stores) is no longer what the provider sent")
def test_raw_response_not_mutated(adapter, monkeypatch):
    parsed = completion('{"probabilities": {"no": 0.5, "yes": 0.5}}', {"prompt_tokens": 7, "completion_tokens": 1})
    original = json.loads(json.dumps(parsed))
    use(monkeypatch, (200, parsed, 0.1))
    r = adapter.run(noul_task())
    assert r.raw == original


def test_raw_usage_currently_mutated(adapter, monkeypatch):
    # Pins today's behaviour behind the xfail above.
    parsed = completion('{"probabilities": {"no": 0.5, "yes": 0.5}}', {"prompt_tokens": 7, "completion_tokens": 1})
    use(monkeypatch, (200, parsed, 0.1))
    r = adapter.run(noul_task())
    assert r.usage is r.raw["usage"]
    assert r.raw["usage"] == {"prompt_tokens": 7, "completion_tokens": 1, "input_tokens": 7, "output_tokens": 1}


# --- remote_inproc: same transport helper, different envelope ---------------

def remote(monkeypatch, *responses):
    fake = FakePost(*responses)
    monkeypatch.setattr(ri_mod, "http_post_json", fake)
    return RemoteInprocAdapter(endpoint="http://gpu.invalid/", model="m0", timeout_s=9.0), fake


def test_remote_ok(monkeypatch):
    a, fake = remote(monkeypatch, (200, {"ok": True, "probs": {"no": 0.2, "yes": 0.8}, "usage": {"input_tokens": 3},
                                         "model": "served", "raw": {"runtime": {"gpu": "L4"}}, "latency_s": 0.02}, 0.5))
    r = a.run(noul_task())
    call = fake.calls[0]
    assert call["url"] == "http://gpu.invalid/run" and call["timeout_s"] == 9.0
    assert call["headers"] == {"Content-Type": "application/json"}
    assert call["body"]["task"]["expected"] is None and call["body"]["task"]["provenance"] == {}
    assert (r.ok, r.probs, r.error, r.status, r.latency_s, r.model, r.probs_source) == (
        True, {"no": 0.2, "yes": 0.8}, None, 200, 0.5, "served", "native")
    assert r.usage == {"input_tokens": 3}
    assert r.raw == {"runtime": {"gpu": "L4", "server_latency_s": 0.02}}
    assert r.request_body is None
    assert a.reserve_estimate(noul_task()) == 0.0 and a.cost_basis == "self_hosted_gpu"


def test_remote_server_reported_failure(monkeypatch):
    a, _ = remote(monkeypatch, (200, {"ok": False, "error": "OOM", "raw": {"runtime": None}}, 0.1))
    r = a.run(noul_task())
    assert (r.ok, r.probs, r.error, r.model, r.usage) == (False, None, "OOM", "m0", {})
    assert r.raw == {"runtime": {"server_latency_s": None}}


def test_remote_missing_fields(monkeypatch):
    a, _ = remote(monkeypatch, (200, {}, 0.1))
    r = a.run(noul_task())
    assert (r.ok, r.probs, r.error, r.raw, r.usage, r.model) == (False, None, None, None, {}, "m0")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_remote_error_status_no_retry(monkeypatch, status):
    a, fake = remote(monkeypatch, (status, "busy", 0.4), (200, {"ok": True}, 0.1))
    r = a.run(noul_task())
    assert len(fake.calls) == 1
    assert (r.ok, r.status, r.latency_s, r.error) == (False, status, 0.4, f"HTTP {status}: busy")


def test_remote_timeout(monkeypatch):
    a, _ = remote(monkeypatch, ConnectionError("TimeoutError: timed out"))
    r = a.run(noul_task())
    assert (r.ok, r.status, r.error) == (False, None, "TimeoutError: timed out")
