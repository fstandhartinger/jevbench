from jevbench.adapters.jevora_9b_v1 import Jevora9BV1Adapter, render_task, validate_probabilities
from jevbench.tasks import Task


def task(qtype, criteria, labels, state="A short state."):
    return Task(id="t", family="f", state=state, labels=labels, expected=labels[0], split="public",
                question={"type": qtype, "instructions": "Decide this.", "criteria": criteria})


def adapter_with_mocked_inference(monkeypatch, outcome):
    adapter = Jevora9BV1Adapter(endpoint="/unused", device="cpu")
    adapter.load = lambda: None
    adapter._model = object()
    adapter._tokenizer = object()
    adapter._metadata = {"max_length": 1024}
    adapter._device = object()
    adapter._prompt_version = "jevora-v0.2-lm-head-codes"
    adapter._temperature = 1.0
    monkeypatch.setattr(adapter, "_decision", outcome, raising=False)
    return adapter


def test_choice_noul_and_score_preserve_order_and_native_probabilities(monkeypatch):
    def answer(*_):
        return 1, [0.25, 0.75], 19

    adapter = adapter_with_mocked_inference(monkeypatch, answer)
    choice = adapter.run(task("choice", {"b": "Beta", "a": "Alpha"}, ["b", "a"]))
    assert choice.ok and choice.probs == {"b": 0.25, "a": 0.75}
    assert "expected" not in choice.request_body

    noul = adapter.run(task("noul", {"true": "T", "false": "F"}, ["no", "yes"]))
    assert noul.ok and noul.probs == {"no": 0.25, "yes": 0.75}
    assert noul.request_body["options"] == ["no: F", "yes: T"]

    score = adapter.run(task("score", ["low", "high"], ["0", "1"]))
    assert score.ok and score.probs == {"0": 0.25, "1": 0.75}


def test_over_options_and_overlength_are_422(monkeypatch):
    many = [str(index) for index in range(256)]
    over_options = Jevora9BV1Adapter(endpoint="/unused").run(task("choice", None, many))
    assert not over_options.ok and over_options.status == 422

    def overlength(*_):
        raise ValueError("input has 1025 tokens, exceeds max_length=1024")

    adapter = adapter_with_mocked_inference(monkeypatch, overlength)
    result = adapter.run(task("choice", {"a": "A", "b": "B"}, ["a", "b"]))
    assert not result.ok and result.status == 422


def test_runtime_errors_have_no_synthetic_status(monkeypatch):
    def crash(*_):
        raise RuntimeError("CUDA failure")

    adapter = adapter_with_mocked_inference(monkeypatch, crash)
    result = adapter.run(task("choice", {"a": "A", "b": "B"}, ["a", "b"]))
    assert not result.ok and result.status is None and "RuntimeError" in result.error


def test_unrelated_value_errors_are_not_misclassified_as_overlength(monkeypatch):
    def malformed_message(*_):
        raise ValueError("input has invalid fields, exceeds max_length=1024")

    adapter = adapter_with_mocked_inference(monkeypatch, malformed_message)
    result = adapter.run(task("choice", {"a": "A", "b": "B"}, ["a", "b"]))
    assert not result.ok and result.status is None


def test_probability_validation_rejects_repairable_but_invalid_values():
    assert validate_probabilities([0.4, 0.6], 2) == [0.4, 0.6]
    for values in ([0.4], [0.4, 0.5], [float("nan"), 1.0], [0.4, 1.2]):
        try:
            validate_probabilities(values, 2)
            raise AssertionError("invalid probabilities accepted")
        except ValueError:
            pass


def test_rendering_does_not_read_gold_and_keeps_label_criteria_order():
    row = task("choice", {"a": "Alpha", "b": "Beta"}, ["b", "a"])
    context, options = render_task(row)
    assert context == "State:\nA short state.\n\nQuestion:\nDecide this."
    assert options == ["b: Beta", "a: Alpha"]
