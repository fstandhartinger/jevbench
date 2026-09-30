import os

from jevbench.adapters.trio_spark import TrioSparkAdapter
from jevbench.tasks import Task


def task(question_type="choice"):
    if question_type == "choice":
        question = {"type": "choice", "instructions": "Route it", "criteria": {"a": "A", "b": "B"}}
        labels = ["a", "b"]
    elif question_type == "noul":
        question = {"type": "noul", "instructions": "Is it true?", "criteria": {"false": "No", "true": "Yes"}}
        labels = ["no", "yes"]
    else:
        question = {"type": "score", "instructions": "Score it", "criteria": ["low", "high"]}
        labels = ["0", "1"]
    return Task("t", "f", "state text", question, labels, labels[0], "public")


def test_builds_all_three_primitives():
    adapter = TrioSparkAdapter(key_env="")
    for kind, expected in (("choice", ["a", "b"]), ("noul", ["no", "yes"]), ("score", ["0", "1"])):
        body = adapter.build_request(task(kind))
        assert [choice["id"] for choice in body["choices"]] == expected
        assert body["state"] == {"observation": "state text"}


def test_choice_order_follows_canonical_labels():
    value = task()
    value.question["criteria"] = {"b": "B", "a": "A"}
    body = TrioSparkAdapter(key_env="").build_request(value)
    assert [choice["id"] for choice in body["choices"]] == ["a", "b"]


def test_parses_native_probabilities(monkeypatch):
    monkeypatch.setenv("TRIO_SPARK_API_KEY", "test-key-not-a-credential")
    monkeypatch.setattr(
        "jevbench.adapters.trio_spark.http_post_json",
        lambda *args, **kwargs: (200, {
            "model": "trio-spark-preview",
            "choice_id": "b",
            "probabilities": [
                {"choice_id": "a", "probability": 0.25},
                {"choice_id": "b", "probability": 0.75},
            ],
            "usage": {"billed_input_tokens": 42},
        }, 0.1),
    )
    result = TrioSparkAdapter().run(task())
    assert result.ok
    assert result.probs == {"a": 0.25, "b": 0.75}
    assert result.probs_source == "native"
    assert result.usage["input_tokens"] == 42
    assert result.usage["output_tokens"] == 0


def test_missing_key_fails_without_network(monkeypatch):
    monkeypatch.delenv("TRIO_SPARK_API_KEY", raising=False)
    result = TrioSparkAdapter().run(task())
    assert not result.ok
    assert "TRIO_SPARK_API_KEY" in result.error
