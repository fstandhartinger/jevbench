"""Offline tests for the domyn_edge_jev_decision adapter: no model download, no GPU.

They pin the contract that matters for scoring — the returned probability keys equal `task.labels` for every
task kind — by exercising the pure label-mapping logic; the model forward is not run here (the conformance kit
and the sealed run do that).
"""
from types import SimpleNamespace

from jevbench.adapters.domyn_edge_jev_decision import DomynEdgeJevDecisionAdapter


def _task(kind, instructions, labels, criteria=None, state="some state"):
    return SimpleNamespace(state=state, labels=labels,
                           question={"type": kind, "instructions": instructions, "criteria": criteria})


def test_attrs_and_defaults():
    a = DomynEdgeJevDecisionAdapter()
    assert a.name == "domyn_edge_jev_decision"
    assert a.model_id == "deshwalmahesh/domyn-edge-jev-decision"
    assert a.reserve_estimate(None) == 0.0
    assert a.price_input_per_m == 0.04 and a.price_output_per_m == 0.0


def test_keys_equal_labels_per_kind():
    a = DomynEdgeJevDecisionAdapter()

    keys, _, _, _ = a._keys_texts(_task("noul", "Is X true?", ["no", "yes"]))
    assert set(keys) == {"yes", "no"}

    keys, texts, _, _ = a._keys_texts(
        _task("choice", "Route it", ["billing", "shipping"], {"billing": "money", "shipping": "parcels"}))
    assert keys == ["billing", "shipping"]
    assert texts[0].startswith("billing")  # label — description rendering

    keys, _, _, _ = a._keys_texts(_task("choice", "Pick", ["a", "b", "c"], None))
    assert keys == ["a", "b", "c"]

    keys, _, _, _ = a._keys_texts(_task("score", "Rate 0-2", ["0", "1", "2"], ["low", "mid", "high"]))
    assert keys == ["0", "1", "2"]


if __name__ == "__main__":
    test_attrs_and_defaults()
    test_keys_equal_labels_per_kind()
    print("ok")
