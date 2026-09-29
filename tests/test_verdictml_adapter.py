"""verdictml_local: the answer mapping fixed in the adapter docstring, without loading any model."""
from types import SimpleNamespace

from jevbench.adapters import VerdictMlLocalAdapter
from jevbench.tasks import Task


def _task(qtype, criteria, labels, state="hello"):
    return Task(id="t1", family="f", state=state, labels=labels, expected=labels[0], split="public",
                question={"type": qtype, "instructions": "Q?", "criteria": criteria})


def _adapter(answer, seen):
    a = VerdictMlLocalAdapter()

    class FakeVerdict:
        def compile(self, q):
            seen["question"] = q
            return lambda text: (seen.__setitem__("text", text), answer)[1]

    a._v = FakeVerdict()
    a._to_question = lambda q: ("Q", q)
    a._render = lambda s: f"rendered:{s}"
    return a


def test_choice_distribution_is_used_as_is():
    seen = {}
    ans = SimpleNamespace(distribution={"a": 0.75, "b": 0.25}, model_dump=lambda mode=None: {"distribution": {"a": 0.75, "b": 0.25}})
    r = _adapter(ans, seen).run(_task("choice", {"a": "Alpha", "b": "Beta"}, ["a", "b"], state={"x": 1}))
    assert r.ok and r.probs == {"a": 0.75, "b": 0.25} and r.probs_source == "native"
    assert seen["question"] == ("Q", {"type": "choice", "instructions": "Q?", "criteria": {"a": "Alpha", "b": "Beta"}})
    assert seen["text"] == "rendered:{'x': 1}"
    assert r.raw["runtime"]["probability_origin"] == "native-softmax" and r.latency_s >= 0


def test_score_levels_are_string_indices_from_zero():
    ans = SimpleNamespace(distribution={0: 0.1, 1: 0.6, 2: 0.3}, model_dump=lambda mode=None: {})
    r = _adapter(ans, {}).run(_task("score", ["lo", "mid", "hi"], ["0", "1", "2"]))
    assert r.ok and r.probs == {"0": 0.1, "1": 0.6, "2": 0.3}


def test_noul_probability_is_p_yes():
    ans = SimpleNamespace(probability=0.9, model_dump=lambda mode=None: {})
    r = _adapter(ans, {}).run(_task("noul", {"true": "T", "false": "F"}, ["no", "yes"]))
    assert r.ok and r.probs["yes"] == 0.9 and abs(r.probs["no"] - 0.1) < 1e-12 and set(r.probs) == {"yes", "no"}


def test_bad_answer_is_a_failed_attempt_not_an_exception():
    r = _adapter(SimpleNamespace(model_dump=lambda mode=None: {}), {}).run(_task("noul", None, ["no", "yes"]))
    assert not r.ok and r.error.startswith("answer parse failed")


def test_default_model_and_device():
    a = VerdictMlLocalAdapter()
    assert a.model == "verdict-small" and a.name == "verdictml_local" and a.device == "cpu"
    assert a.reserve_estimate(None) == 0.0
