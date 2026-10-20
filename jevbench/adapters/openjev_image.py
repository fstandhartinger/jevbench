"""OpenJev image Decisions transport; normalization is disclosed, never fitted.

Task state: {"text": "An image: <<IMG>>", "image_data": "<base64>"}.
Keeping the image bytes in the task binds them into the existing dataset hash.
Uses the unchanged JevBench scoring/ledger/raw-response path.
"""
from .typesafe import TypeSafeAdapter


class OpenJevImageAdapter(TypeSafeAdapter):
    name = "openjev_image"

    def build_request(self, task):
        state = task.state
        if not isinstance(state, dict) or not isinstance(state.get("image_data"), str):
            raise ValueError("openjev_image requires state.image_data as base64 or a data URI")
        if not isinstance(state.get("text", ""), str):
            raise ValueError("state.text must be text")
        body = super().build_request(task)
        body["state"] = state.get("text", "An image: <<IMG>>")
        body["image_data"] = state["image_data"]
        return body

    def run(self, task):
        result = super().run(task)
        result.probs_source = "normalized_entailment_v1"
        if result.ok and result.raw.get("probability_method") != "normalized_entailment_v1":
            result.ok = False
            result.error = "Endpoint did not declare normalized_entailment_v1"
        return result
