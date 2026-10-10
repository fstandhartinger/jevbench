import pytest

from jevbench.adapters import TacetLocalAdapter
from jevbench.tasks import Task


def task(question_type, criteria, labels):
    return Task(id="t", family="f", state="The item state.", labels=labels,
                expected=labels[0], split="public",
                question={"type": question_type, "instructions": "Decide this.", "criteria": criteria})


class FakeModel:
    device = "cpu"
    max_length = 4096

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def decide(self, state, questions):
        self.requests.append((state, questions))
        return {"answers": {"decision": self.answer}, "usage": {"input_tokens": 12}}


def adapter_with(answer):
    adapter = TacetLocalAdapter(endpoint="codepawl/tacet-sonata")
    adapter._model = FakeModel(answer)
    return adapter


def test_request_carries_the_question_and_never_the_answer():
    body = TacetLocalAdapter.build_request(task("choice", {"a": "Alpha", "b": "Beta"}, ["a", "b"]))
    assert body["state"] == "The item state."
    assert body["questions"]["decision"]["criteria"] == {"a": "Alpha", "b": "Beta"}
    assert "expected" not in str(body)


def test_noul_maps_to_yes_and_no():
    result = adapter_with({"type": "noul", "noul": 0.8, "confidence": 0.8}).run(task("noul", None, ["no", "yes"]))
    assert result.ok
    assert result.probs == pytest.approx({"yes": 0.8, "no": 0.2})
    assert result.probs_source == "native"


def test_choice_and_score_probabilities_are_used_as_returned():
    choice = adapter_with({"type": "choice", "choice": "b", "probabilities": {"a": 0.3, "b": 0.7}})
    assert choice.run(task("choice", {"a": "A", "b": "B"}, ["a", "b"])).probs == {"a": 0.3, "b": 0.7}
    score = adapter_with({"type": "score", "score": 1.4, "probabilities": {"0": 0.2, "1": 0.2, "2": 0.6}})
    assert score.run(task("score", ["low", "mid", "high"], ["0", "1", "2"])).probs == {"0": 0.2, "1": 0.2, "2": 0.6}


def test_a_mistyped_answer_is_a_failed_attempt():
    result = adapter_with({"type": "choice", "probabilities": {"a": 1.0}}).run(task("noul", None, ["no", "yes"]))
    assert not result.ok
    assert "answer parse failed" in result.error
