"""Build the publication-safe v1.4 board from aggregate inputs only."""

import copy
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jevbench import composite_v14 as score
from jevbench import composite_v13 as old_score

DATA = ROOT / "results" / "v1.4"
OUTPUT = DATA / "jevbench-v1.4-results.json"
EXPECTED_TOP_FIVE = ["jev-1.13.0", "jevk5-v02", "hopper", "winnow-12b", "reflex-4b"]


def read(path):
    return json.loads(path.read_text())


def new_row(source):
    """A new submission has no old detailed result row; do not invent one."""
    axes = source["v130"]["axes"]
    usd = source.get("cost_per_1000_decisions_usd")
    if usd is None and axes["cost"] not in (None, 0, 100):
        usd = 0.001 * 10 ** ((100 - axes["cost"]) / 30)
    api = is_operator_api(source)
    latency = source.get("api_latency") or {}
    return {
        "key": source["key"], "display": source["display"], "author": source.get("author"),
        "repo": source.get("repo"), "class": source["class"], "licence": source.get("licence"),
        "open": None, "underlying": None,
        "has_distribution": None if source.get("sealed") is None else not source["sealed"].get("label_only", False),
        "probability_source": None,
        "endpoint_condition": source.get("note_v14") or source.get("source"),
        "endpoint_kind": "api" if api else "unknown",
        "partial": False, "ranked": source["ranked"],
        "listing": "ranked" if source["ranked"] else "partial",
        "not_ranked_because": None,
        "tiers": source["v130"]["tiers"],
        "speed": {"p50_s_raw": latency.get("p50_s"), "p95_s_raw": latency.get("p95_s"),
                  "p50_s_adjusted": latency.get("p50_s"), "p95_s_adjusted": latency.get("p95_s"),
                  "adjustment": "none (production API)" if api else "See original v1.3 measurement",
                  "run": latency.get("basis"), "hardware": None, "measured_where": None,
                  "hard_tier_p50_s": None, "hard_tier_p95_s": None},
        "cost": {"kind": "measured" if source.get("cost_per_1000_decisions_usd") is not None else "estimate",
                 "usd_per_1000": usd,
                 "basis": "Measured API usage × list price" if source.get("cost_per_1000_decisions_usd") is not None else
                          "Reconstructed from the frozen v1.3 Cost axis; same speed/cost measurement, not a new price observation",
                 "usd_per_1000_v11_tiers": None, "usd_per_1000_hard": None,
                 "self_host_sensitivity": None},
        "calibration": {"score": axes["calibration"], "note": "none (label only)" if axes["calibration"] is None else None},
        "hard": None,
    }


def is_operator_api(source):
    note = source.get("note_v14") or ""
    return note.startswith("API measurement:") or note.startswith("sealed item text (no golds) was sent to the operator endpoint")


def build():
    old = read(ROOT / "results" / "v1.2" / "jevbench-v1.2-results.json")
    round4 = read(DATA / "round4-aggregate-rows.json")
    aggregate = read(DATA / "measurement-aggregates.json")
    by_key = {r["key"]: r for r in old["systems"] + round4}
    assert len(by_key) == len(old["systems"]) + len(round4)
    rows = []
    footnotes = copy.deepcopy(old.get("footnotes", {}))
    for source in aggregate["systems"]:
        key = source["key"]
        assert key not in {row["key"] for row in rows}, key
        row = copy.deepcopy(by_key[key]) if key in by_key else new_row(source)
        axes, value = score.score_from_comparison(source)
        row.update(display=source["display"], author=source.get("author"), repo=source.get("repo"),
                   licence=source.get("licence"), **{"class": source["class"]})
        row["source_round"] = source.get("source")
        row["api_flag"] = is_operator_api(source)
        row["api_exposure_note"] = ("API — the operator's endpoint received sealed item text, without answers."
                                    if row["api_flag"] else None)
        row["public_accuracy"] = source.get("public_acc")
        row["sealed_accuracy"] = source.get("sealed_acc")
        row["public_minus_sealed_gap_pp"] = (100 * (source["public_acc"] - source["sealed_acc"])
                                                if source.get("sealed_acc") is not None else None)
        sealed = source.get("sealed")
        row["sealed_aggregate"] = ({k: sealed.get(k) for k in
                                     ("n", "answered_valid", "by_family", "by_panel_stratum", "ece",
                                      "mean_tvd_gold_probs", "calibration", "label_only", "risk_coverage")}
                                    if sealed else None)
        row["v130_comparison_rank"] = source["v130"]["rank"]
        row["v130_comparison_score"] = source["v130"]["score"]
        row["scoring_note"] = source.get("note_v14")
        notes = [n for n in (footnotes.get(key), source.get("note"), source.get("note_v14")) if n]
        if notes:
            footnotes[key] = " | ".join(dict.fromkeys(notes))
        if axes is not None:
            # The old hard-tier and speed/cost measurement remain available as diagnostics.
            row["axes"] = axes
            row["calibration"]["score"] = axes["calibration"]
            row["jevbench_score"] = value
            row["presets"] = {name: score.harmonic(axes, dict(zip(old_score.AXES, weights)))
                              for name, weights in old_score.PRESETS.items()}
        else:
            row["axes"] = None
            row["jevbench_score"] = None
            row["presets"] = {}
        if source.get("sealed_acc") is None:
            row.update(ranked=False, listing="partial", partial=True,
                       not_ranked_because="No completed sealed v1.4 run; retained as an unranked historical row")
        elif not source["ranked"]:
            row["ranked"] = False
            if row["listing"] == "ranked":
                row["listing"] = "partial"
        else:
            row.update(ranked=True, listing="ranked", partial=False, not_ranked_because=None)
        rows.append(row)

    ranked = sorted((r for r in rows if r["ranked"]), key=lambda r: -r["jevbench_score"])
    assert [r["key"] for r in ranked[:5]] == EXPECTED_TOP_FIVE, [r["key"] for r in ranked[:5]]
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    for row in rows:
        if not row["ranked"]:
            row["rank"] = None
        row["rank_under"] = {}
    for name in old_score.PRESETS:
        for rank, row in enumerate(sorted(ranked, key=lambda r: -(r["presets"][name] or 0)), 1):
            row["rank_under"][name] = rank

    artifact = copy.deepcopy(old)
    artifact.update(revision="v1.4.0", protocol="jevbench::v1.4", status="final",
                    generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    measured_in="Frozen v1.2 public/held-out items plus 308 sealed v1.4 items; all item text and answers remain private",
                    revision_note="v1.4: 20% sealed Intelligence, blended Calibration, public-to-sealed gap penalty, harmonic mean and separate Speed/Cost gates.",
                    score_one_liner="Intelligence, Calibration, Speed and Cost — equal-weight harmonic mean, with generalization and Jev-class gates.",
                    tiers={**old["tiers"], "sealed": aggregate["meta"]["sealed_items"]},
                    sealed_chance=score.SEALED_CHANCE, sealed_weight=score.SEALED_WEIGHT,
                    footnotes=footnotes, systems=ranked + [r for r in rows if not r["ranked"]])
    artifact["revision_log"] = old["revision_log"] + [{"revision": "v1.4.0", "date": "2026-09-23",
        "note": "Added 308 sealed decisions, the selected 20% scoring blend, a generalization penalty, harmonic mean and separate Speed/Cost Jev-class gates. Sealed items and answers are not published."}]
    artifact["scoring"].update(
        jevbench_score="Equal-weight harmonic mean of Intelligence, Calibration, Speed and Cost (power mean p=-1). If Intelligence <50 multiply by (I/50)^2. For Speed and Cost separately, if below 50 multiply by (axis/50)^2.",
        intelligence="0.8 × v1.3 chance-corrected Intelligence on the frozen v1.2 items + 0.2 × 100 × max(0, (sealed accuracy − 0.293)/(1 − 0.293)); then multiply by 1 − max(0, public-minus-sealed accuracy gap in percentage points − 25)/100. Original tier weights: easy .14, standard .28, judge .28, hard .30.",
        calibration="v1.3 Calibration + (v1.4 candidate Calibration − v1.3 Calibration) × min(1, 0.2/0.35). Label-only systems contribute zero.",
        presets="Other views reweight the same four axes with a weighted harmonic mean and the same gates. They are not the official JevBench Score.",
        sealed="308 current sealed decisions; only aggregate results are published. API flags identify operator endpoints that received item text without answers.")
    OUTPUT.write_text(json.dumps(artifact, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    return artifact


if __name__ == "__main__":
    output = build()
    print(f"Published {len(output['systems'])} aggregate rows; top five: " +
          ", ".join(f"{r['display']} {r['jevbench_score']:.2f}" for r in output["systems"][:5]))
