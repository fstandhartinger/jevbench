"""Draft checks for the JevBench v1.4.3 point release."""

import hashlib
import importlib.util
import json
import copy
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

from jevbench import composite_v13 as C13
from jevbench import composite_v14 as C

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "v1.4.3"
PREVIOUS = ROOT / "results" / "v1.4.2" / "jevbench-v1.4.2-results.json"
# Update together with Florian's preview approval whenever appended rows change the top five.
EXPECTED_TOP_FIVE = ["decision-4b-v12", "decision-4b-v11", "jevk5-v0.3-4b", "mica-v01-4b", "plumb-4b"]
FIRST_WAVE = {"imajev-2b", "imajev-4b", "imajev-9b", "blink-4b", "ryotide-gemma", "ryotide-qwen",
              "decision-4b-v12", "decision-4b-v11", "plumb-4b", "nemotron-diffusion-8b", "apus-openjev-4b", "jpt-4b",
              "eikos-4b", "eikos-27b", "autojev-27b", "vtx-jev-1"}
PARTIAL = set()
HELD = {"bonsai-2-27b-pq2-0"}
PENDING_API_PRICE = {"bluusun-decision-1", "simplejev-rwkv-small", "simplejev-rwkv-mid",
                     "simplejev-rwkv-std"}
PENDING_PRICE = PENDING_API_PRICE | {"gliner25-decide", "diffusion-jev-sglang", "this-that-1-2",
                                    "nemotron-diffusion-8b", "nemotron-diffusion-14b", "rwkv-jev",
                                    "jevk5-lite-preview1", "tde-general-v0.1", "tde-general-large", "vtx-jev-1"}
REPRICED_QWEN4B = {"decision-4b-v12", "decision-4b-v11", "jevk5-v0.3-4b", "plumb-4b",
                   "eikos-4b", "blink-4b", "jpt-4b", "compass-0.2.0",
                   "diy-jev-4b", "manchego-v2.1", "rev-qwen3.5-4b", "quire-v0.1.1",
                   "minijev-4b", "ryotide-qwen", "simplejev-qwen3.5-4b", "mica-v01-4b"}
REPRICED_SMALL_QWEN = {"deem-0.8b-v1", "reflex-qwen3.5-0.8b", "jpt-0.8b"}
REPRICED_QWEN9B = {"jpt-9b", "deem-9b-v1", "jevall", "jevk5-9b-v0.3.3"}
REPRICED_GEMMA12 = {"go-system-one", "simplejev-gemma-4-12b"}
REPRICED_GEMMA26 = {"shisa-de-1", "simplejev-gemma-4-26b-a4b"}
REPRICED_FEATHERLESS = {"bosun-v3.1-1.7b", "certus-v0007", "bosun-v3.1-0.6b",
                       "ballot-jev-0.5b", "nanojev-0.6b"}
REPRICED_QWEN38 = {"autojev-27b", "eikos-27b", "bev-v0.1.2", "open-jev-27b-v1.1",
                   "diy-jev-27b", "rev-qwen3.8-27b", "bonsai-llama-jev"}
REPRICED_IMAJEV = {"imajev-2b", "imajev-4b", "imajev-9b"}
PENDING_USAGE = {"neojev-qwen3.8-27b-l56"}
SUPERSEDED_ARCHIVED = {"jevk5-9b-v0.3"}
PENDING_PROVENANCE = {"gevva-e2b", "gevva-e4b"}
REPRICED_TYPICAL = {"typical-small-v3"}


def read(name):
    return json.loads((DATA / name).read_text())


@pytest.fixture(scope="module")
def published():
    return read("jevbench-v1.4.3-results.json")


@pytest.fixture(scope="module")
def rows(published):
    return {r["key"]: r for r in published["systems"]}


def test_inputs_are_pinned():
    assert hashlib.sha256(PREVIOUS.read_bytes()).hexdigest().startswith("ac14e206")
    assert hashlib.sha256((ROOT / "jevbench" / "composite_v14.py").read_bytes()).hexdigest().startswith("33177d06")


def test_every_addition_recomputes_with_the_pinned_v14_scorer(published, rows):
    sources = read("addition-sources.json")["systems"]
    details = {r["key"]: r for r in read("addition-rows.json")}
    assert FIRST_WAVE | PARTIAL <= {s["key"] for s in sources}
    assert len(rows) == 93 + len(sources)
    for source in sources:
        axes, expected = C.score_from_comparison(source)
        row = rows[source["key"]]
        if source["key"] in PENDING_PRICE:
            assert row["listing"] == "pending-price" and row["jevbench_score"] is None and row["rank"] is None
            assert expected is not None  # measurement is complete; the price is the missing part
        elif source["key"] in PENDING_USAGE:
            assert row["listing"] == "pending-usage" and row["jevbench_score"] is None and row["rank"] is None
            assert row["cost"]["usd_per_1000"] is None and expected is not None
        elif source["key"] in REPRICED_IMAJEV | REPRICED_TYPICAL:
            assert row["ranked"] and row["cost"]["usd_per_1000"] > details[source["key"]]["cost"]["usd_per_1000"]
            assert row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
            assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
            assert {k: row["axes"][k] for k in ("intelligence", "calibration", "speed")} == pytest.approx(
                {k: axes[k] for k in ("intelligence", "calibration", "speed")})
        elif source["key"] in SUPERSEDED_ARCHIVED:
            assert row["listing"] == "superseded-version" and row["jevbench_score"] is None
            assert expected is not None
        elif source["key"] in PENDING_PROVENANCE:
            assert row["listing"] == "pending-provenance" and row["jevbench_score"] is None
            assert row["cost"]["usd_per_1000"] > 0 and expected is not None
        elif source["key"] in REPRICED_QWEN4B:
            assert row["cost"]["usd_per_1000"] == pytest.approx(details[source["key"]]["cost"]["usd_per_1000"] * 4 / 3)
            assert row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
            assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
            assert {k: row["axes"][k] for k in ("intelligence", "calibration", "speed")} == pytest.approx(
                {k: axes[k] for k in ("intelligence", "calibration", "speed")})
        elif source["key"] in REPRICED_SMALL_QWEN | REPRICED_QWEN9B | REPRICED_GEMMA12 | REPRICED_GEMMA26 | REPRICED_FEATHERLESS | REPRICED_QWEN38:
            assert row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
            assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
            assert {k: row["axes"][k] for k in ("intelligence", "calibration", "speed")} == pytest.approx(
                {k: axes[k] for k in ("intelligence", "calibration", "speed")})
        elif source["key"] == "apus-openjev-4b":
            assert row["cost"]["usd_per_1000"] == pytest.approx(details[source["key"]]["cost"]["usd_per_1000"])
            assert row["axes"] == pytest.approx(axes)
            assert row["jevbench_score"] == pytest.approx(expected)
        elif source["ranked"]:
            assert row["jevbench_score"] == pytest.approx(expected, abs=1e-12)
            assert row["axes"] == pytest.approx(axes, abs=1e-12)
        else:
            assert expected is None and row["jevbench_score"] is None and row["rank"] is None
    ranked = [r for r in published["systems"] if r["ranked"]]
    assert [r["rank"] for r in ranked] == list(range(1, len(ranked) + 1))
    assert all(a["jevbench_score"] >= b["jevbench_score"] for a, b in zip(ranked, ranked[1:]))
    assert all(r["rank"] is None for r in published["systems"] if not r["ranked"])


def test_v142_measurements_and_prices_carry_until_individual_rescore(rows):
    previous = json.loads(PREVIOUS.read_text())["systems"]
    assert len(previous) == 93
    for old in previous:
        new = rows[old["key"]]
        strip = lambda r: {k: v for k, v in r.items() if k not in ("rank", "rank_under")}  # noqa: E731
        assert strip(old) == strip(new), old["key"]
        assert new["jevbench_score"] == old["jevbench_score"]
    reviews = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for old in previous:
        if old["ranked"]:
            assert reviews[old["key"]]["status"] == "carried-v142-unrescored"


def test_additions_are_labelled(rows):
    for key in FIRST_WAVE:
        row = rows[key]
        assert row["new_in"] == "v1.4.3" and row["api_flag"] is False, key
        assert row["cost"]["kind"] == "estimate", key
        if key in PENDING_PRICE:
            assert not row["ranked"] and row["cost"]["usd_per_1000"] is None, key
        else:
            assert row["ranked"] and row["cost"]["usd_per_1000"] > 0, key
        assert row["cost"]["basis"].startswith("ESTIMATE") and "ESTIMATE: ESTIMATE" not in row["cost"]["basis"], key
        assert row["speed"]["p50_s_adjusted"] == pytest.approx(row["speed"]["p50_s_raw"] * 2 + 0.15), key
        assert row["sealed_aggregate"]["n"] == 308 and row["sealed_aggregate"]["answered_valid"] <= 308, key
        assert all(isinstance(v, float) for v in row["sealed_aggregate"]["by_family"].values()), key
        assert all(isinstance(row.get(f), str) and row[f] for f in ("display", "class", "author")), key
        assert row["release_evidence"]["aggregate_source_sha256"] and row["release_evidence"]["row_sha256"], key
    gliner = rows["gliner25-decide"]
    assert not gliner["ranked"] and gliner["listing"] == "pending-price"
    assert gliner["sealed_aggregate"]["n"] == 308 and gliner["cost"]["usd_per_1000"] is None
    assert gliner["cost"]["measured_input_tokens_frozen"] == 333739
    for key in HELD:
        assert key not in rows


def test_apus_is_repriced_to_the_qwen35_4b_basis(rows):
    apus = rows["apus-openjev-4b"]
    usd = 389142 * 0.04 / 1e6 / 534 * 1000
    assert apus["cost"]["usd_per_1000"] == pytest.approx(usd, rel=1e-12)
    assert apus["axes"]["cost"] == pytest.approx(C13.cost(usd), abs=1e-12)
    assert "$0.04/M" in apus["cost"]["basis"] and "EmpirioLabs" in apus["cost"]["basis"]
    assert apus["cost"]["repriced_from"]["input_usd_per_m"] == 0.1
    for key in ("decider-4b-v2", "typecastlm", "decision-4b-v12", "eikos-4b"):
        assert ("$0.04/M" if key in REPRICED_QWEN4B else "$0.03/M") in rows[key]["cost"]["basis"], key


def test_instinct_keeps_its_base_model_estimate(rows):
    inst = rows["instinct"]
    assert inst["cost"]["kind"] == "estimate" and "0.42" in inst["cost"]["basis"]
    assert inst["cost"]["usd_per_1000"] == pytest.approx(0.3253253932584269)


def test_price_rule_blocks_unverified_api_tariffs(published, rows):
    assert published["status"] == "draft"
    assert published["publication_ready"] is False
    assert published["pricing_review_pending"] == []
    holds = {entry["key"] for entry in published["measured_unranked_holds"]}
    assert PENDING_PRICE <= holds
    for key in PENDING_PRICE:
        row = rows[key]
        assert not row["ranked"] and row["listing"] == "pending-price"
        assert row["cost"]["usd_per_1000"] is None
        if key in PENDING_API_PRICE:
            assert "30-day" in row["not_ranked_because"]
        else:
            assert "exact-base" in row["not_ranked_because"]
    assert {"gevva-e2b", "gevva-e4b"} <= holds
    assert "djev" not in holds  # unchanged published row is carried


def test_deprecated_qwen_quotes_block_only_new_rows_until_individual_rescore(published, rows):
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    # Independently enumerated from the release cost ledger, including variant
    # DeepInfra spelling and the retired 0.8B/2B listings.
    affected = {
        "decider-4b-v2", "reflex-4b", "semif-qwen3.5-4b", "jobe-qwen3.5-4b",
        "spark-s1-4b-v6", "malkuth-4b", "malkuth-2b", "kev-4b",
        "decision-2b", "open-alternative-jev", "decider-2b", "typecastlm",
        "jevact",
        "rwkv-jev", "mghafiri-qwen3.5-0.8b-decision-model",
        "certus-v0007", "bosun-v3.1-1.7b",
    }
    assert len(affected) == 17
    previous_rows = json.loads(PREVIOUS.read_text())["systems"]
    source_affected = {r["key"] for r in previous_rows if
                       "deepinfra" in (r["cost"].get("basis") or "").lower() and
                       "qwen3.5-" in (r["cost"].get("basis") or "").lower() and
                       any(size in (r["cost"].get("basis") or "").lower()
                           for size in ("qwen3.5-0.8b", "qwen3.5-2b", "qwen3.5-4b"))}
    assert affected & {r["key"] for r in previous_rows} == source_affected
    # Parse the first provider/model quote independently from the builder regex.
    first_quote = lambda r: (r["cost"].get("basis") or "").lower().split("deepinfra", 1)[-1][:70]  # noqa: E731
    new_source_4b = {r["key"] for r in read("addition-rows.json") if
                     "deepinfra" in (r["cost"].get("basis") or "").lower() and
                     "qwen3.5-4b" in first_quote(r)}
    assert new_source_4b == REPRICED_QWEN4B | {"imajev-4b", "this-that-1-2"}
    assert all("EmpirioLabs" in rows[key]["cost"]["basis"] for key in new_source_4b - {"this-that-1-2"})
    assert review["this-that-1-2"]["status"] == "withheld-pending-price"
    assert "decider-2b" in next(s for s in read("addition-sources.json")["systems"]
                                if s["key"] == "this-that-1-2")["note"]
    assert all(rows[key]["ranked"] for key in affected - {"rwkv-jev"})
    assert not rows["rwkv-jev"]["ranked"]
    new_affected = affected - {r["key"] for r in previous_rows}
    old_affected = affected - new_affected
    assert not (new_affected - {"rwkv-jev"}) & set(published["pricing_review_pending"])
    assert not old_affected & set(published["pricing_review_pending"])
    assert {review[key]["status"] for key in new_affected - {"rwkv-jev"}} == {"bookable-base-reference"}
    assert review["rwkv-jev"]["status"] == "withheld-pending-price"
    assert {review[key]["status"] for key in old_affected} == {"carried-v142-unrescored"}
    assert all("Featherless" in review[key]["basis"] for key in new_affected - {"rwkv-jev"})
    spec = importlib.util.spec_from_file_location("v143_builder", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    for spelling in ("DeepInfra's Qwen3.5-4B", "DeepInfra: Qwen3.5-2B",
                     "DeepInfra/Qwen/Qwen3.5-0.8B", "deepinfra Qwen/Qwen3.5-4B"):
        assert builder.RETIRED_DEEPINFRA_QWEN35.search(spelling)


def test_small_exact_featherless_base_quotes_recompute_cost_and_score(rows):
    spec = importlib.util.spec_from_file_location("v143_builder", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    assert set(builder.FEATHERLESS_SMALL_EXACT_BASES) == REPRICED_FEATHERLESS
    for key, (row_sha, input_tokens, old_rate, base_id, input_rate, output_rate, receipt, receipt_sha) in builder.FEATHERLESS_SMALL_EXACT_BASES.items():
        assert hashlib.sha256(receipt.read_bytes()).hexdigest() == receipt_sha
        quote = json.loads(receipt.read_text())
        assert quote["id"] == base_id and quote["status"] == "active"
        assert quote["availability"]["tier"] in ("warm", "hot")
        assert (quote["pricing"]["input"], quote["pricing"]["output"]) == (input_rate, output_rate)
        row = rows[key]
        assert row["release_evidence"]["row_sha256"] == row_sha
        assert row["cost"]["previous_price_basis"]["usd_per_1000"] == \
            pytest.approx(input_tokens * old_rate / 1e6 / 534 * 1000)
        assert row["cost"]["measured_input_tokens_frozen"] == input_tokens
        assert row["cost"]["measured_output_tokens_frozen"] == 0
        assert row["cost"]["usd_per_1000"] == pytest.approx(input_tokens * input_rate / 1e6 / 534 * 1000)
        assert row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
        assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
        assert review[key]["status"] == "bookable-base-reference"


def test_new_qwen4b_reprice_runs_from_source_data(rows):
    spec = importlib.util.spec_from_file_location("v143_builder", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = next(r for r in read("addition-rows.json") if r["key"] == "decision-4b-v12")
    row = copy.deepcopy(rows[source["key"]])
    row["cost"] = copy.deepcopy(source["cost"])
    row["axes"]["cost"] = C13.cost(source["cost"]["usd_per_1000"])
    row["jevbench_score"] = C.harmonic(row["axes"])
    footnotes = {row["key"]: "Training note. Cost is a labelled estimate: retired DeepInfra quote."}
    review = builder.apply_pricing_rule([row], footnotes)
    assert review[0]["status"] == "bookable-base-reference"
    assert row["cost"]["usd_per_1000"] == pytest.approx(source["cost"]["usd_per_1000"] * 4 / 3)
    assert row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
    assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
    current_basis_note = footnotes[row["key"]].split("pre-release correction", 1)[0]
    assert "EmpirioLabs" in current_basis_note and "$0.03/M" not in current_basis_note


def test_retired_nemotron_sibling_proxies_block_finalization(published):
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key, date in (("nemotron-diffusion-8b", "11 Jun 2026"),
                      ("nemotron-diffusion-14b", "16 Jul 2026")):
        assert review[key]["status"] == "withheld-pending-price"
        assert date in review[key]["reason"]
        assert key in {item["key"] for item in published["measured_unranked_holds"]}
    spec = importlib.util.spec_from_file_location("v143_builder", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert builder.RETIRED_DEEPINFRA_NEMOTRON.search(
        "DeepInfra nvidia/NVIDIA-Nemotron-Nano-9B-v2 list price")
    assert builder.RETIRED_DEEPINFRA_NEMOTRON.search(
        "DeepInfra nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL list price")


def test_unlisted_diffusion_and_rwkv_bases_are_unranked(rows):
    audit = ROOT.parent / "receipts/DIFFUSION-RWKV-AUDIT-20260925.md"
    assert hashlib.sha256(audit.read_bytes()).hexdigest() == \
        "61176fe3bc1fd4e45aad6ae2b4068c8d111016ccbff2f1543fb39ff136c318b6"
    expected = {"nemotron-diffusion-8b": (421719, 534),
                "nemotron-diffusion-14b": (421719, 534),
                "rwkv-jev": (366273, 0)}
    for key, (inputs, outputs) in expected.items():
        row = rows[key]
        assert not row["ranked"] and row["listing"] == "pending-price"
        assert row["cost"]["usd_per_1000"] is None and row["jevbench_score"] is None
        assert row["cost"]["measured_input_tokens_frozen"] == inputs
        assert row["cost"]["measured_output_tokens_frozen"] == outputs
        assert "exact-base" in row["not_ranked_because"]


def test_new_exact_small_qwen_bases_use_bookable_references(rows):
    spec = importlib.util.spec_from_file_location("v143_builder", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source_rows = {r["key"]: r for r in read("addition-rows.json")}
    source_exact = {key for key, r in source_rows.items()
                    if "deepinfra" in (r["cost"].get("basis") or "").lower()
                    and any(s in (r["cost"].get("basis") or "").lower()
                            for s in ("qwen3.5-0.8b", "qwen3.5-2b"))
                    and any(s in (r["cost"].get("basis") or "").lower()
                            for s in ("exact base weights", "same base model"))}
    assert source_exact == set(builder.SMALL_QWEN_EXACT_BASES) | {"imajev-2b"}
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key in set(builder.SMALL_QWEN_EXACT_BASES):
        old_cost = source_rows[key]["cost"]["usd_per_1000"]
        _, row_sha, input_tokens, output_tokens, old_rate, new_rate, output_rate = builder.SMALL_QWEN_EXACT_BASES[key]
        row = rows[key]
        assert review[key]["status"] == "bookable-base-reference"
        assert source_rows[key]["release_evidence"]["row_sha256"] == row_sha
        assert old_cost == pytest.approx(input_tokens * old_rate / 1e6 / 534 * 1000)
        assert row["cost"]["usd_per_1000"] == pytest.approx((input_tokens * new_rate + output_tokens * output_rate) / 1e6 / 534 * 1000)
        assert row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
        assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
        assert "$0.02/M" not in row["cost"]["basis"] and "$0.01/M" not in row["cost"]["basis"]
        assert row["cost"]["previous_price_basis"]["usd_per_1000"] == pytest.approx(old_cost)
    assert rows["jpt-0.8b"]["cost"]["measured_output_tokens_frozen"] == 534
    assert "$50/month prepaid credits" in rows["imajev-2b"]["cost"]["basis"]
    assert rows["imajev-2b"]["listing"] == "ranked"


def test_imajev_rotation_recount_matches_old_reported_maxima(published, rows):
    audit = read("imajev-usage-audit.json")
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    histogram = {int(k): v for k, v in audit["old_answer_option_histogram"].items()}
    assert sum(histogram.values()) == 534
    # The server adds its unknown choice before running up to four full forwards.
    assert sum(n * min(4, choices + 1) for choices, n in histogram.items()) == 1941
    details = {r["key"]: r for r in read("addition-rows.json")}
    for key in REPRICED_IMAJEV:
        row, usage = rows[key], audit["rows"][key]
        assert usage["raw_results_sha256"] == details[key]["release_evidence"]["raw_results_sha256"]
        assert usage["reported_max_per_request_input_tokens_frozen"] == 391693
        assert usage["full_forward_input_tokens_upper_bound_frozen"] == 1451955
        assert review[key]["status"] == "bookable-base-reference"
        assert row["cost"]["measured_input_tokens_frozen"] == 1451955 and row["ranked"]
        assert key not in published["pricing_review_pending"]
        assert "$0.03/M" not in row["scoring_note"]


def test_superseded_jevk5_9b_is_not_ranked(published, rows):
    row = rows["jevk5-9b-v0.3"]
    source = next(r for r in read("addition-rows.json") if r["key"] == "jevk5-9b-v0.3")
    aggregate = next(r for r in read("addition-sources.json")["systems"] if r["key"] == "jevk5-9b-v0.3")
    assert not row["ranked"] and row["listing"] == "superseded-version"
    assert "d6521a18" in row["not_ranked_because"]
    assert published["version_review_pending"] == []
    for field in ("speed", "tiers", "cost"):
        assert row[field] == source[field]
    assert row["public_accuracy"] == aggregate["public_acc"]
    assert row["sealed_accuracy"] == aggregate["sealed_acc"]
    aggregate_axes, _ = C.score_from_comparison(aggregate)
    assert row["calibration"]["score"] == pytest.approx(aggregate_axes["calibration"])
    assert row["release_evidence"] == source["release_evidence"]


def test_gevva_exact_base_prices_are_recorded_but_provenance_holds_rank(published, rows):
    expected_hashes = {
        "gevva-e2b": ("397cf35bac2e76765643d02d9b469309309c42b140d50827923985b151a8cd6b",
                      "a328ae4853aa7c87fb5013e5aadffb8fdaefcfea70092d27b874952f8763024b"),
        "gevva-e4b": ("9c7943a293700c9fe3e3e5fc19ac4598c1ace65f9e639a4c0f173c1d4f1e086f",
                      "83ecc013924d784949656ad344cfdda4ccf9325ad471129dde9b30009c046405"),
    }
    source_rows = {r["key"]: r for r in read("addition-rows.json")}
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key, input_rate in (("gevva-e2b", 0.04), ("gevva-e4b", 0.02)):
        row = rows[key]
        src = source_rows[key]
        row_sha, raw_sha = expected_hashes[key]
        assert src["release_evidence"]["row_sha256"] == row_sha
        assert src["release_evidence"]["raw_results_sha256"] == raw_sha
        assert src["cost"]["usd_per_1000"] == pytest.approx(1574960 * 0.02 / 1e6 / 534 * 1000)
        assert row["release_evidence"]["row_sha256"] == src["release_evidence"]["row_sha256"]
        assert row["cost"]["measured_input_tokens_frozen"] == 1574960
        assert row["cost"]["measured_output_tokens_frozen"] == 0
        assert row["cost"]["usd_per_1000"] == pytest.approx(1574960 * input_rate / 1e6 / 534 * 1000)
        assert not row["ranked"]
        assert review[key]["status"] == "withheld-provenance"
        assert key in {item["key"] for item in published["measured_unranked_holds"]}
        assert key not in published["provenance_review_pending"] and key not in published["pricing_review_pending"]
        assert "Public gold-labelled JevBench errors" in row["not_ranked_because"]


def test_typical_small_exact_base_price_and_public_selection_disclosure(published, rows):
    key = "typical-small-v3"
    row = rows[key]
    source = next(r for r in read("addition-rows.json") if r["key"] == key)
    review = next(r for r in read("pricing-review.json")["rows"] if r["key"] == key)
    assert row["release_evidence"]["row_sha256"] == source["release_evidence"]["row_sha256"] == \
        "cba551a258fa439bfca0b7751d56c999c4f4c6f79891d4e76ec1124c56d3562c"
    assert row["release_evidence"]["raw_results_sha256"] == \
        "2a67cb173e48d095760e9f900b8f06ae9249efe97cc68276677c3653633cea82"
    assert source["cost"]["usd_per_1000"] == pytest.approx(384149 * 0.02 / 1e6 / 534 * 1000)
    assert row["cost"]["measured_input_tokens_frozen"] == 384149
    assert row["cost"]["usd_per_1000"] == pytest.approx(384149 * 0.32 / 1e6 / 534 * 1000)
    assert row["ranked"] and row["axes"]["cost"] == pytest.approx(C13.cost(row["cost"]["usd_per_1000"]))
    assert review["status"] == "bookable-base-reference"
    assert key not in published["pricing_review_pending"]
    assert "public JevBench results" in row["scoring_note"]
    assert "Featherless" in row["cost"]["basis"] and "$50/month prepaid credits" in row["cost"]["basis"]


def test_imajev_rotation_usage_is_exact_and_priced(published, rows):
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    rates = {"imajev-2b": 0.08, "imajev-4b": 0.04, "imajev-9b": 0.08}
    for key, rate in rates.items():
        receipt = read(f"exact-usage/{key}-EXACT-USAGE.json")
        assert receipt["per_item_max_checks"] == 842 and receipt["counts"]["old_534"] == 1451955
        assert receipt["counts"]["all_842"] == 2553277
        row = rows[key]
        assert row["ranked"] and row["listing"] == "ranked"
        assert row["cost"]["usd_per_1000"] == pytest.approx(1451955 * rate / 1e6 / 534 * 1000)
        assert row["cost"]["measured_input_tokens_frozen"] == 1451955
        assert row["cost"]["reported_max_per_request_input_tokens_frozen"] == 391693
        assert review[key]["status"] == "bookable-base-reference"
        assert key not in published["pricing_review_pending"]


def test_neojev_fixed_prefix_omission_holds_cost_and_rank(published, rows):
    key = "neojev-qwen3.8-27b-l56"
    row = rows[key]
    review = next(r for r in read("pricing-review.json")["rows"] if r["key"] == key)
    assert row["release_evidence"]["row_sha256"] == \
        "918fe99714195fc3d0b4db18401afacaa3bfc429e214d2a80a1334bbc1650420"
    assert row["release_evidence"]["raw_results_sha256"] == \
        "589125ae04dabf2600ae17b472c15c7fe402d3c03d016d59e7ffe6e88551ee49"
    assert row["cost"]["reported_suffix_input_tokens_frozen"] == 366707
    assert row["cost"]["usd_per_1000"] is None and not row["ranked"]
    assert "previous_price_basis" not in row["cost"]
    assert row["v130_comparison_rank"] is None and row["v130_comparison_score"] is None
    source = next(r for r in read("addition-rows.json") if r["key"] == key)
    assert source["cost"]["usd_per_1000"] == pytest.approx(366707 * 0.42 / 1e6 / 534 * 1000)
    assert row["release_evidence"] == source["release_evidence"]
    assert row["sealed_accuracy"] == next(
        s for s in read("addition-sources.json")["systems"] if s["key"] == key)["sealed_acc"]
    assert review["status"] == "withheld-pending-usage"
    assert key in {item["key"] for item in published["measured_unranked_holds"]}
    assert "__head__ prefix" in row["not_ranked_because"]


def test_diffusion_jev_842_measurement_is_listed_without_sibling_proxy(published, rows):
    key = "diffusion-jev-sglang"
    row = rows[key]
    review = next(r for r in read("pricing-review.json")["rows"] if r["key"] == key)
    assert row["release_evidence"]["row_sha256"] == \
        "443dd05d6063134c55d807b022d1fbf55a2cf80e3465ebb88422f7d3e27cbc81"
    assert row["release_evidence"]["raw_results_sha256"] == \
        "61793de392826021186558e5bcbcd6c7bd40ea651c152aa3589ec7f906f1bc0d"
    assert row["cost"]["measured_input_tokens_frozen"] == 380768
    assert row["cost"]["measured_output_tokens_frozen"] == 2660
    assert row["cost"]["usd_per_1000"] is None and row["rank"] is None
    assert not row["ranked"] and row["listing"] == "pending-price"
    assert row["sealed_accuracy"] == 90 / 308
    assert row["measurement_completion"] == {"attempted": 842, "valid": 839,
                                             "invalid": 3, "http_503": 3}
    assert review["status"] == "withheld-pending-price"
    assert key in {item["key"] for item in published["measured_unranked_holds"]}
    source = next(s for s in read("addition-sources.json")["systems"] if s["key"] == key)
    assert source["sealed"]["n"] == 308 and source["sealed"]["answered_valid"] == 307
    assert source["v130"]["axes"]["cost"] is not None


def test_exact_qwen35_9b_endpoint_price_and_output_tokens(rows):
    expected = {"jpt-9b": (380080, 534), "deem-9b-v1": (352175, 0), "jevall": (296208, 0),
                "jevk5-9b-v0.3.3": (397944, 0)}
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key, (inputs, outputs) in expected.items():
        row = rows[key]
        assert row["cost"]["usd_per_1000"] == pytest.approx(
            (inputs * 0.08 + outputs * 0.13) / 1e6 / 534 * 1000)
        assert row["cost"]["measured_output_tokens_frozen"] == outputs
        assert review[key]["status"] == "bookable-base-reference"
        assert "Darkbloom" in row["cost"]["basis"]


def test_jevk5_9b_v033_replaces_unranked_owner_price(published, rows):
    row = rows["jevk5-9b-v0.3.3"]
    assert row["ranked"] and row["jevbench_score"] == pytest.approx(55.1099, abs=0.001)
    assert row["release_evidence"]["row_sha256"] == \
        "ec8ebc3522aa6bdba240116e1558312abde3aa7b5446537d7161debf19227f9c"
    assert row["release_evidence"]["raw_results_sha256"] == \
        "e8bf19065c98390eea7ed77d28cc05ae4f33365878db0d3e454e6695ae4e892d"
    assert row["release_evidence"]["token_receipt_sha256"] == \
        "0f7034372252f2d12b7c03952b5fca2997e58c8e8bb96d0a6152fa656f9f0796"
    assert row["sealed_accuracy"] == 128 / 308
    assert "public" in published["footnotes"][row["key"]].lower()
    assert "stays unranked" not in published["footnotes"][row["key"]]


def test_exact_gemma4_12b_reference_charges_recorded_output(rows):
    receipt = DATA / "price-receipts/NANOGPT-MODELS-20260925T1650Z.json"
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == \
        "e87daee3d16b5ec3ef43be0752135731bbd28a86b47098cf43297d5a5c2d0a6e"
    models = [model for model in json.loads(receipt.read_text())["data"]
              if model.get("id") == "gemma-4-12b-it"]
    assert len(models) == 1 and "aoru" in models[0]["providers"]
    assert models[0]["pricing"]["prompt"] == 0.05
    assert models[0]["pricing"]["completion"] == 0.25
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key, inputs, outputs in (("go-system-one", 380085, 66422),
                                 ("simplejev-gemma-4-12b", 1183379, 0)):
        row = rows[key]
        assert row["cost"]["usd_per_1000"] == pytest.approx(
            (inputs * 0.05 + outputs * 0.25) / 1e6 / 534 * 1000)
        assert row["cost"]["measured_output_tokens_frozen"] == outputs
        expected_axes = dict(row["axes"], cost=C13.cost(row["cost"]["usd_per_1000"]))
        assert row["axes"] == pytest.approx(expected_axes)
        assert row["jevbench_score"] == pytest.approx(C.harmonic(expected_axes))
        for preset, weights in C13.PRESETS.items():
            assert row["presets"][preset] == pytest.approx(
                C.harmonic(expected_axes, dict(zip(C13.AXES, weights))))
        assert review[key]["status"] == "bookable-base-reference"
        assert "NanoGPT" in row["cost"]["basis"]
        assert "Gemma 3" not in row["cost"]["basis"]


def test_gemma4_26b_cheapest_standard_exact_endpoint(rows):
    receipt = DATA / "price-receipts/OR-GEMMA26-ENDPOINTS-20260925T1716Z.json"
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == \
        "21d50b2e7d12b4acfe538de3cda7c2b183b255bcbbfb56d59e8703d60a14f374"
    catalog = json.loads(receipt.read_text())["data"]
    assert catalog["id"] == "google/gemma-4-26b-a4b-it"
    darkbloom = [e for e in catalog["endpoints"] if e["provider_name"] == "Darkbloom" and e["status"] == 0]
    assert len(darkbloom) == 1 and darkbloom[0]["pricing"]["discount"] == 0
    assert float(darkbloom[0]["pricing"]["prompt"]) * 1e6 == pytest.approx(0.042)
    assert float(darkbloom[0]["pricing"]["completion"]) * 1e6 == pytest.approx(0.22)
    for key, inputs in (("shisa-de-1", 394026), ("simplejev-gemma-4-26b-a4b", 1183379)):
        row = rows[key]
        usd = inputs * 0.042 / 1e6 / 534 * 1000
        assert row["ranked"] and row["cost"]["usd_per_1000"] == pytest.approx(usd)
        assert row["cost"]["measured_output_tokens_frozen"] == 0
        expected_axes = dict(row["axes"], cost=C13.cost(usd))
        assert row["axes"] == pytest.approx(expected_axes)
        assert row["jevbench_score"] == pytest.approx(C.harmonic(expected_axes))
        for preset, weights in C13.PRESETS.items():
            assert row["presets"][preset] == pytest.approx(
                C.harmonic(expected_axes, dict(zip(C13.AXES, weights))))
        assert "Darkbloom" in row["cost"]["basis"]


def test_qwen38_27b_exact_endpoint_prices_seven_rows_and_charges_outputs(rows):
    receipt = DATA / "price-receipts/OPENROUTER-QWEN38-27B-ENDPOINTS-20260925T1748Z.json"
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == \
        "c8511a8278a396d72561c4f6527bf89b2f9c1fa9a568071712bee29d56e54679"
    audit = ROOT.parent / "receipts/QWEN38-27B-AND-MODERNBERT-AUDIT-20260925.md"
    assert hashlib.sha256(audit.read_bytes()).hexdigest() == \
        "6f6305037b6dd106d58004063db7bc81024ed195e39da279fb0ffa962b22f74e"
    endpoints = json.loads(receipt.read_text())["data"]
    assert endpoints["id"] == "qwen/qwen3.8-27b"
    reka = [e for e in endpoints["endpoints"] if e["provider_name"] == "Reka"]
    assert len(reka) == 1 and reka[0]["status"] == 0
    assert reka[0]["model_id"] == "qwen/qwen3.8-27b"
    assert reka[0]["pricing"]["discount"] == 0
    assert (reka[0]["pricing"]["prompt"], reka[0]["pricing"]["completion"]) == \
        ("0.000000092", "0.0000044")
    darkbloom = [e for e in endpoints["endpoints"] if e["provider_name"] == "Darkbloom"]
    assert len(darkbloom) == 1 and darkbloom[0]["status"] == 0
    assert darkbloom[0]["model_id"] == "qwen/qwen3.8-27b"
    assert darkbloom[0]["pricing"]["discount"] == 0
    assert (darkbloom[0]["pricing"]["prompt"], darkbloom[0]["pricing"]["completion"]) == \
        ("0.0000001", "0.0000018")
    correction = ROOT.parent / "receipts/QWEN38-REKA-CORRECTION-20260925.md"
    assert hashlib.sha256(correction.read_bytes()).hexdigest() == \
        "da4facd1f9344a3a1fcb6b6643f741da395ae7a2f2c45efda4618ce50940a78c"
    measured = {
        "autojev-27b": (381653, 0), "eikos-27b": (397944, 0),
        "bev-v0.1.2": (405641, 534), "open-jev-27b-v1.1": (1328707, 0),
        "diy-jev-27b": (384467, 534), "rev-qwen3.8-27b": (348169, 0),
        "bonsai-llama-jev": (388801, 0),
    }
    assert set(measured) == REPRICED_QWEN38
    source = {r["key"]: r for r in read("addition-rows.json")}
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key, (inputs, outputs) in measured.items():
        row = rows[key]
        assert source[key]["cost"]["usd_per_1000"] == pytest.approx(inputs * 0.42 / 1e6 / 534 * 1000)
        assert row["cost"]["measured_input_tokens_frozen"] == inputs
        assert row["cost"]["measured_output_tokens_frozen"] == outputs
        corrected = (inputs * 0.092 + outputs * 4.40) / 1e6 / 534 * 1000
        alternative = (inputs * 0.10 + outputs * 1.80) / 1e6 / 534 * 1000
        assert corrected < alternative
        assert row["cost"]["usd_per_1000"] == pytest.approx(corrected)
        assert row["axes"]["cost"] == pytest.approx(C13.cost(corrected))
        assert row["jevbench_score"] == pytest.approx(C.harmonic(row["axes"]))
        assert review[key]["status"] == "bookable-base-reference"
        assert "$0.42/M model-level" in row["pricing_change_note"]
        assert "$0.092/M input" in row["scoring_note"]
        assert "$4.40/M output" in row["scoring_note"]
        assert f"{outputs:,} measured output tokens" in row["scoring_note"]
        assert row["rank"] > 5
    assert {key for key, pair in measured.items() if pair[1]} == {"bev-v0.1.2", "diy-jev-27b"}


def test_capability_entrants_disclose_training_overlap_limits(published):
    eikos = published["footnotes"]["eikos-27b"]
    assert "25,566 released training rows against 231 public JevBench items" in eikos
    assert "other 146 public-source frozen items" in eikos
    assert "any unreleased training data were not screened" in eikos
    assert "author evaluated public JevBench items" in eikos
    assert "not proven training contamination" in eikos
    auto = published["footnotes"]["autojev-27b"]
    assert "all 377 public-source frozen items is UNVERIFIED" in auto
    assert "73,000-example corpus is not published" in auto


def test_tde_modernbert_base_proxy_is_unranked(rows):
    for path, expected_sha in (
        (ROOT.parent / "receipts/QWEN38-27B-AND-MODERNBERT-AUDIT-20260925.md",
         "6f6305037b6dd106d58004063db7bc81024ed195e39da279fb0ffa962b22f74e"),
        (DATA / "price-receipts/OPENROUTER-FRESH-20260925T1715Z.json",
         "49b44d1c2e4cf4f7349462318fa3943080a1a9660cc4d9a3236a4d556e9cefb5"),
        (DATA / "price-receipts/DEEPINFRA-FRESH-20260925T1715Z.json",
         "786aacf24c13208300d0beca6f3a324977048084266760355a39c8aab7474078"),
    ):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha
    source = {r["key"]: r for r in read("addition-sources.json")["systems"]}
    for key, rate in (("tde-general-v0.1", 0.005), ("tde-general-large", 0.01)):
        receipt = DATA / ("price-receipts/FEATHERLESS-MODERNBERT-BASE-DETAIL-20260925T1752Z.json"
                          if key == "tde-general-v0.1" else
                          "price-receipts/FEATHERLESS-MODERNBERT-LARGE-DETAIL-20260925T1751Z.json")
        assert hashlib.sha256(receipt.read_bytes()).hexdigest() == \
            "86f0768d163960b35ad30b59b5d5013386ff37355fee51ff3c5f7d3972044950"
        assert json.loads(receipt.read_text())["error"]["code"] == "model_not_found"
        assert source[key]["sealed"]["n"] == 308
        assert source[key]["sealed"]["answered_valid"] == 308
        row = rows[key]
        assert row["public_accuracy"] == source[key]["public_acc"]
        assert row["sealed_accuracy"] == source[key]["sealed_acc"]
        assert len(row["release_evidence"]["raw_results_sha256"]) == 64
        assert not row["ranked"] and row["listing"] == "pending-price"
        assert row["cost"]["usd_per_1000"] is None
        assert row["cost"]["measured_input_tokens_frozen"] == 215301
        assert row["cost"]["measured_output_tokens_frozen"] == 0
        assert row["cost"]["previous_price_basis"]["usd_per_1000"] == \
            pytest.approx(215301 * rate / 1e6 / 534 * 1000)
        assert "ModernBERT" in row["not_ranked_because"]


def test_unchanged_exact_base_prices_are_receipt_pinned(rows):
    review = {r["key"]: r for r in read("pricing-review.json")["rows"]}
    for key, tokens, rate in (("ryotide-gemma", 421421, 0.02),
                              ("winnow-e4b", 393957, 0.02),
                              ("standardone-3b", 371816, 0.10),
                              ("jqv-targeted", 376573, 0.08)):
        row = rows[key]
        assert row["ranked"] and row["cost"]["usd_per_1000"] == pytest.approx(
            tokens * rate / 1e6 / 534 * 1000)
        assert review[key]["status"] == "bookable-base-reference"
        assert row["cost"]["measured_output_tokens_frozen"] == 0


def test_tiny_exact_base_audits_and_vtx_hold(rows):
    audits = (("BALLOT-NANO-JQV-PRICE-AUDIT-20260925.md",
               "a677eca692bff76d0b050549fe7e73dc4e93f3958b5b2d49a78067b8ad857d73"),
              ("VTX-BOSUN06-AUDIT-20260925.md",
               "52574517e329f9dbf0e66e5c968d95b7dbb57c6adebc6c89f0931b29d142c082"))
    for filename, expected in audits:
        assert hashlib.sha256((ROOT.parent / "receipts" / filename).read_bytes()).hexdigest() == expected
    receipt = DATA / "price-receipts/OPENROUTER-QWEN3-32B-ENDPOINTS-20260925T1807Z.json"
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == \
        "a28be8be5e90a6f6e689d7b9e52216d123ce6d1d5af6819fa0c30dff64d23ec5"
    catalog = json.loads(receipt.read_text())["data"]
    assert catalog["id"] == "qwen/qwen3-32b"
    route = [e for e in catalog["endpoints"] if e["provider_name"] == "DeepInfra"]
    assert len(route) == 1 and route[0]["model_id"] == "qwen/qwen3-32b"
    assert route[0]["status"] == 0 and route[0]["pricing"]["discount"] == 0
    assert (route[0]["pricing"]["prompt"], route[0]["pricing"]["completion"]) == \
        ("0.00000008", "0.00000028")
    vtx_receipt = DATA / "price-receipts/FEATHERLESS-VTX-JEV-1-DETAIL-20260925T1807Z.json"
    assert hashlib.sha256(vtx_receipt.read_bytes()).hexdigest() == \
        "86f0768d163960b35ad30b59b5d5013386ff37355fee51ff3c5f7d3972044950"
    assert json.loads(vtx_receipt.read_text())["error"]["code"] == "model_not_found"
    vtx = rows["vtx-jev-1"]
    assert not vtx["ranked"] and vtx["listing"] == "pending-price"
    assert vtx["cost"]["usd_per_1000"] is None
    assert vtx["cost"]["measured_input_tokens_frozen"] == 213468
    assert vtx["cost"]["measured_output_tokens_frozen"] == 0
    assert vtx["sealed_aggregate"]["n"] == vtx["sealed_aggregate"]["answered_valid"] == 308
    assert vtx["release_evidence"]["raw_results_sha256"] == \
        "208e29327f88f1c0fec4a1c17ed701fa1fc9701fad51ba0e94dbdb18cf791f13"
    owner = ROOT.parent.parent / "gpu/outputs/vtx-jev-1-ROW-v1.4.3.json"
    assert hashlib.sha256(owner.read_bytes()).hexdigest() == vtx["release_evidence"]["row_sha256"]
    scopes = json.loads(owner.read_text())["measurements"]["scope_counts"]
    assert scopes == {"public-source": 377, "historical-private": 157, "current-sealed": 308}
    assert sum(scopes.values()) == 842


def test_certo_label_only_full_run_uses_paid_exact_base(rows):
    row = rows["certo-r1"]
    receipt = DATA / "price-receipts/APIAIRFORCE-QWEN3-4B-20260925.html"
    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == \
        "c9809f7c866b6614046d9d67d5a35baac0c9c9d84a84444ae3641de8d420ca65"
    assert row["ranked"] and row["listing"] == "ranked" and row["rank"] is not None
    assert row["has_distribution"] is False and row["sealed_aggregate"]["label_only"] is True
    assert row["sealed_aggregate"]["n"] == 308
    assert row["sealed_aggregate"]["calibration"] is None
    assert row["sealed_aggregate"]["risk_coverage"] is None
    assert row["calibration"]["score"] == row["axes"]["calibration"] == row["jevbench_score"] == 0
    assert row["cost"]["usd_per_1000"] == pytest.approx(
        (355490 * 0.05 + 19562 * 0.18) / 1e6 / 534 * 1000)
    assert row["release_evidence"]["raw_results_sha256"] == \
        "02392cca5138862e25cbdc603c2753749a598e4153de1c55b952aa571ba70d62"
    assert "label-only" in row["scoring_note"]


def test_this_that_is_unranked_without_verified_exact_parent_rate(rows):
    row = rows["this-that-1-2"]
    review = next(r for r in read("pricing-review.json")["rows"] if r["key"] == row["key"])
    assert not row["ranked"] and row["listing"] == "pending-price"
    assert row["cost"]["usd_per_1000"] is None
    assert row["cost"]["measured_input_tokens_frozen"] == 354059
    assert review["status"] == "withheld-pending-price"
    assert "Qwen3.5-2B-Base" in row["not_ranked_because"]


def test_jevk5_lite_official_842_is_price_held(rows):
    row = rows["jevk5-lite-preview1"]
    review = next(r for r in read("pricing-review.json")["rows"] if r["key"] == row["key"])
    manifest = next(r for r in read("input-manifest.json") if r["key"] == row["key"])
    assert not row["ranked"] and row["listing"] == "pending-price"
    assert row["cost"]["usd_per_1000"] is None
    assert row["cost"]["measured_input_tokens_frozen"] == 147309
    assert row["cost"]["measured_output_tokens_frozen"] == 0
    assert row["release_evidence"]["row_sha256"] == \
        "d990fbdf57abf53aff5714fec8da48f03d26f69acf7acb861db6506f30ad9df7"
    assert row["release_evidence"]["raw_results_sha256"] == \
        "aeae95a6ddfdb2c57b603b9b3b756e633992d692e74c72140eabf65faaa5983d"
    assert manifest["aggregate_source_sha256"] == \
        "abed1bd2547c7d57f4f9f6cbbcb49f610fde8801f8fc083a32159db0d23ab3e9"
    assert manifest["token_receipt_sha256"] == \
        "894d92551874d0f5abf35ff1f91dacf0ec3892770592ce7e79253dcd0e34e2e7"
    assert row["sealed_aggregate"]["n"] == row["sealed_aggregate"]["answered_valid"] == 308
    source = next(s for s in read("addition-sources.json")["systems"] if s["key"] == row["key"])
    assert source["ranked"] is False and source["sealed"]["n"] == 308
    assert review["status"] == "withheld-pending-price"


def test_derived_aggregate_pins_and_public_field_allowlist():
    spec = importlib.util.spec_from_file_location("v143_builder_derived_pins", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    manifest = {r["key"]: r for r in read("input-manifest.json")}
    sources = {r["key"]: r for r in read("addition-sources.json")["systems"]}
    allowed = {"key", "display", "author", "repo", "class", "licence", "ranked", "source", "note",
               "note_v14", "v130", "public_acc", "sealed_acc", "api_flag", "sealed", "v14"}
    sealed_allowed = {"n", "answered_valid", "by_family", "ece", "mean_tvd_gold_probs",
                      "calibration", "label_only", "by_panel_stratum", "risk_coverage"}
    for key, (agg_sha, _) in builder.DERIVED_INPUT_PINS.items():
        assert manifest[key]["aggregate_source_sha256"] == agg_sha
        assert set(sources[key]) == allowed
        assert set(sources[key]["sealed"]) == sealed_allowed
        assert "/home/" not in json.dumps(sources[key])


def test_public_aggregate_schema_and_input_hash_fail_before_output(tmp_path):
    spec = importlib.util.spec_from_file_location("v143_builder_fail_closed", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    before = hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest()
    sources = read("addition-sources.json")
    ordinary = next(s for s in sources["systems"] if s["key"] == "mica-v01-4b")
    ordinary["unexpected_private_field"] = "must not publish"
    sources_path = tmp_path / "bad-sources.json"
    sources_path.write_text(json.dumps(sources))
    builder.SOURCES = sources_path
    with pytest.raises(AssertionError):
        builder.build()
    details = read("addition-rows.json")
    detail = next(d for d in details if d["key"] == "mica-v01-4b")
    detail["release_evidence"]["input_sha256"] = "0" * 64
    details_path = tmp_path / "bad-details.json"
    details_path.write_text(json.dumps(details))
    builder.SOURCES = DATA / "addition-sources.json"
    builder.DETAILS = details_path
    with pytest.raises(AssertionError):
        builder.build()
    assert hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest() == before


def test_token_receipts_are_not_treated_as_aggregate_inputs(tmp_path):
    spec = importlib.util.spec_from_file_location("v143_builder_input_filter", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    aggregate = tmp_path / "sample-AGGREGATE-SOURCE-v1.4.3.json"
    token_receipt = tmp_path / "sample-TOKEN-AGGREGATE-SOURCE-v1.4.3.json"
    aggregate.write_text("{}")
    token_receipt.write_text("{}")
    config = tmp_path / "inputs.txt"
    config.write_text(str(tmp_path) + "\n")
    assert builder.input_files(config) == [aggregate]


def test_price_floor_and_publication_gate(published, rows, tmp_path):
    spec = importlib.util.spec_from_file_location("v143_builder", ROOT / "scripts/v1.4.3/build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert builder.policy_cost(0.02, 0.03) == 0.03
    assert builder.policy_cost(0.04, 0.03) == 0.04
    assert builder.policy_cost(None, 0.03) == 0.03
    assert builder.policy_cost(None, None) is None
    # Documented measured-unranked holds leave the changed-top-five approval
    # as the remaining final gate. No real receipt exists for this draft.
    before = hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, str(ROOT / "scripts/v1.4.3/build.py"), "--final"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0 and "Florian's approval receipt" in result.stderr
    assert hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest() == before
    # Independently exercise both failure modes in memory.
    spec = importlib.util.spec_from_file_location("v143_builder_price_gate", ROOT / "scripts/v1.4.3/build.py")
    price_gate_builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(price_gate_builder)
    original_pricing_rule = price_gate_builder.apply_pricing_rule
    price_gate_builder.apply_pricing_rule = lambda rows, notes: [
        {**r, "evidence": []} if r["key"] == "gevva-e2b" else r
        for r in original_pricing_rule(rows, notes)]
    with pytest.raises(ValueError, match="provenance reviews remain") as err:
        price_gate_builder.build(final=True, approval_receipt="test-receipt")
    assert "gevva-e2b" in str(err.value)
    assert hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest() == before
    # No actual ranked base-reference candidate remains. Inject one to prove the
    # final gate still rejects a future unaudited ranked estimate.
    price_gate_builder.apply_pricing_rule = lambda rows, notes: [
        {"key": "synthetic-ranked-price-hold", "status": "base-reference-candidate"}]
    with pytest.raises(ValueError, match="price reviews remain"):
        price_gate_builder.build(final=True, approval_receipt="test-receipt")
    assert hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest() == before
    # A mock receipt plus fully documented holds can produce an isolated final
    # artifact without changing the real draft output.
    price_gate_builder.apply_pricing_rule = original_pricing_rule
    price_gate_builder.ROOT = tmp_path / "repo"
    price_gate_builder.ROOT.mkdir()
    (price_gate_builder.ROOT / "jevbench").symlink_to(ROOT / "jevbench", target_is_directory=True)
    price_gate_builder.APPROVAL_RECEIPTS_DIR = tmp_path
    price_gate_builder.PREVIEW_HTML = tmp_path / "preview.html"
    price_gate_builder.PREVIEW_HTML.write_text("test preview")
    price_gate_builder.NOTIFY_LOG = tmp_path / "notify.jsonl"
    photo = tmp_path / "preview.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\ntest-only")
    sent_ts = photo.stat().st_mtime + 1
    price_gate_builder.NOTIFY_LOG.write_text(json.dumps({
        "ts": sent_ts, "level": "now", "source": "test", "sent": True,
        "message_id": 42, "photo": str(photo),
        "text": "JevBench v1.4.3 mock preview"}) + "\n")
    receipt = tmp_path / "mock-approval.json"
    receipt.write_text(json.dumps({
        "approved_by": "Florian", "decision": "approved", "source": "Telegram",
        "request_message_id": "42", "reply_message_id": "43",
        "approved_utc": dt.datetime.fromtimestamp(sent_ts + 1, dt.timezone.utc).isoformat(),
        "candidate_sha256": published["candidate_sha256"],
        "composite_top_five": [r["key"] for r in published["systems"] if r["ranked"]][:5],
        "capability_top_five": published["capability_headline_top_five"],
        "preview_sha256": hashlib.sha256(price_gate_builder.PREVIEW_HTML.read_bytes()).hexdigest(),
        "preview_images": [{"path": photo.name, "sha256": hashlib.sha256(photo.read_bytes()).hexdigest()}],
    }))
    price_gate_builder.OUTPUT = tmp_path / "mock-final.json"
    price_gate_builder.PRICING_REVIEW = tmp_path / "mock-review.json"
    mock = price_gate_builder.build(final=True, approval_receipt=str(receipt))
    assert mock["publication_ready"] and len(mock["measured_unranked_holds"]) == 17
    assert not mock["pricing_review_pending"] and not mock["provenance_review_pending"]
    assert hashlib.sha256((DATA / "jevbench-v1.4.3-results.json").read_bytes()).hexdigest() == before
    for key in ("certus-v0007", "jevall"):
        source = next(s for s in read("addition-sources.json")["systems"] if s["key"] == key)
        assert source["sealed"]["n"] == 308 and 0 < source["sealed"]["answered_valid"] < 308
        assert rows[key]["ranked"] and rows[key]["sealed_accuracy"] < 1


def test_decision_4b_disclosure_is_corrected(published):
    for key in ("decision-4b-v12", "decision-4b-v11"):
        note = published["footnotes"][key]
        assert "used for training, tuning or model selection" not in note
        assert "reports/gates.json" in note and "public split was used for model selection" in note


def test_mica_overlap_disclosure_has_verifiable_scope(published):
    note = published["footnotes"]["mica-v01-4b"]
    assert "77,732 training rows and the 231 public JevBench items" in note
    assert "training data is not published" in note
    assert "only the published repository (code and predictions), not the training data" in note
    assert "public or held out, was trained on" not in note


def test_top_five_and_fairness_note_are_true(published, rows):
    ranked = [r for r in published["systems"] if r["ranked"]]
    assert [r["key"] for r in ranked[:5]] == EXPECTED_TOP_FIVE
    note = published["top_five_note"]
    for r in ranked[:5]:
        assert f"{r['display'].split(' (')[0]} {r['axes']['intelligence']:.1f}" in note
    jev = rows["jev-1.13.0"]["axes"]["intelligence"]
    above = sum(r["axes"]["intelligence"] > jev for r in ranked[:5])
    assert f"out-reasoned by {['no', 'one', 'two', 'three', 'four', 'five'][above]} of them" in note
    assert "strongest reasoner" not in note and "out-reasons" not in note
    best = max(ranked, key=lambda r: r["axes"]["intelligence"])
    assert f"up to {best['axes']['intelligence']:.1f}" in note


def test_no_private_fields_are_published():
    for name in ("jevbench-v1.4.3-results.json", "addition-sources.json", "addition-rows.json", "input-manifest.json", "pricing-review.json"):
        text = (DATA / name).read_text()
        for forbidden in ('"results_file"', '"gold"', '"gold_probs"', '"task_text"', '"prompt_text"', "/home/",
                          "jevbench-sealed"):
            assert forbidden not in text, (name, forbidden)
