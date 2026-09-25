"""Build the JevBench v1.4.3 result artifact.

v1.4.3 = the 93 published v1.4.2 rows (carried byte-for-byte except `rank` and `rank_under`)
       + official full-protocol addition rows (534 frozen v1.2 + 308 sealed v1.4 decisions).

Two steps, both in this script:

  1. assemble (only with --inputs FILE): read the owners' frozen `<key>-AGGREGATE-SOURCE-*.json` /
     `<key>-ROW-*.json` pairs (and `<key>-PARTIAL-*.json` listings) from every directory or glob listed in
     FILE, check them, apply the release corrections in OVERRIDES / DISCLOSURES below, and write
     results/v1.4.3/addition-sources.json, addition-rows.json and input-manifest.json.
     Owner files are only read.
  2. build: score every addition with the unchanged, pinned jevbench/composite_v14.py and write
     results/v1.4.3/jevbench-v1.4.3-results.json.

Without --inputs, step 2 runs on the committed addition files, so the artifact is reproducible from the repo.

    python scripts/v1.4.3/build.py --inputs /path/to/INPUT-DIRS.txt   # re-assemble, then build
    python scripts/v1.4.3/build.py                                    # build from committed inputs

INPUT-DIRS.txt: one path per line; `#` starts a comment. A line is a directory (all
`*-AGGREGATE-SOURCE-*.json` and `*-PARTIAL-*.json` in it are used) or a glob (e.g. `/dir/APUS-OpenJev-v1-4B-*`).
Appending wave-2 rows = add their output directories to the file and re-run with --inputs.
"""

import argparse
import copy
import datetime as dt
import glob
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jevbench import composite_v13 as old_score  # noqa: E402
from jevbench import composite_v14 as score  # noqa: E402

PREV = ROOT / "results" / "v1.4.2" / "jevbench-v1.4.2-results.json"
PREV_SHA256 = "ac14e206dde51ae28e40dc1ea2ff1fecc4a449b941d098e9ecb5618bd533e5be"
COMPOSITE_SHA256 = "33177d06eab9f78667972ec3b20997344f70a78e16b05326453a2c31200cac79"
FULL_INPUT_SHA256 = "6b06782a8a9fadfae770cf88985ec188f3244f01510e9b3f15b34c9723937cfc"
DATA = ROOT / "results" / "v1.4.3"
SOURCES = DATA / "addition-sources.json"
DETAILS = DATA / "addition-rows.json"
MANIFEST = DATA / "input-manifest.json"
OUTPUT = DATA / "jevbench-v1.4.3-results.json"
PREVIOUS_TOP_FIVE = ["decider-4b-v2", "jev-1.13.0", "jevk5-v02", "cygnet", "hopper"]
BLEND = 308 / 528  # sealed share of the hard+sealed calibration items (every v1.4.x row)

# ---------------------------------------------------------------------------------------------------------------
# Release corrections applied at assembly. Every entry is documented in docs/RELEASE-v1.4.3.md.
# ---------------------------------------------------------------------------------------------------------------
DECISION_4B_OLD = ("Disclosed by the author: no JevBench item and no Jev output was used for training, tuning or model "
                   "selection, and a 13-word overlap filter removed every generated training item sharing a span with "
                   "the public items.")
DECISION_4B_NEW = (
    "Training data not released (the author offers it privately for an overlap audit), so it could not be screened; "
    "an 8-gram screen of the released package found no text shared with the public items. The author states that no "
    "JevBench item and no Jev output was used as training data and that a 13-word overlap filter removed generated "
    "training items sharing a span with the public items. The package's own reports/gates.json shows that its "
    "release gates included thresholds on the 231 public JevBench items (public hard, standard and easy), so the "
    "public split was used for model selection. Temperature fitted on the author's own data.")
DECISION_4B_GATE = (
    "Independent verification gate for new top-five entrants (25 Sep 2026): LEGIT. Cost basis, public-versus-sealed "
    "gap, available overlap and a composite recomputation from the raw predictions were checked; the score recomputes "
    "exactly. Its never-public held-out hard accuracy ({heldout}) is close to its public hard accuracy ({public}).")
APUS_PRICE_IN = 0.03  # USD per 1M input tokens, DeepInfra Qwen/Qwen3.5-4B (exact base weights)
APUS_BASIS = (
    "ESTIMATE, repriced for v1.4.3 to the basis every other Qwen3.5-4B row uses: DeepInfra Qwen/Qwen3.5-4B list "
    "price $0.03/M input (the exact base weights; DeepInfra marks the listing deprecated but still lists this "
    "price; catalog read 2026-09-24T17:08Z), zero output tokens (nothing generated), x the model's own measured "
    "prompt tokens (389,142 over the 534 frozen decisions). The measurement handoff had used the $0.10/M Qwen3.5-9B "
    "sibling price. Estimated, not charged.")
APUS_NOTE_V14 = (
    "Offline local open-weight inference of all 842 decisions (534 frozen v1.2 + 308 sealed v1.4, the same "
    "label-free source input rendered for APUS's native decision API) in a network-disabled, read-only container on "
    "an evaluator-owned Lium RTX PRO 6000 pod; no operator endpoint; no golds were exposed. Latency is the "
    "in-process APUS decision call on the serial standard+judge items with the self-hosted adjustment. Cost is a "
    "labelled estimate at DeepInfra's Qwen/Qwen3.5-4B list price ($0.03/M input, no output), the basis of every "
    "other Qwen3.5-4B row; it is not a GPU bill.")


def reprice_apus(src, row):
    """Same measured tokens, Qwen3.5-4B price; recompute usd/1000 and the Cost axis with composite_v13.cost."""
    c = row["measurements"]["cost"]
    assert c["input_tokens_old_534"] == 389142 and c["output_tokens_old_534"] == 0 and c["usage_complete"], c
    usd = c["input_tokens_old_534"] * APUS_PRICE_IN / 1e6 / 534 * 1000
    axis = old_score.cost(usd)
    for block in ("v130", "v14"):
        src[block]["axes"]["cost"] = axis
        src[block]["score"] = None  # preliminary comparison scores are not recomputed; the release score is
        src[block]["rank"] = None
    src["note_v14"] = APUS_NOTE_V14
    cost = {"kind": "estimate", "usd_per_1000": usd, "basis": APUS_BASIS, "usd_per_1000_v11_tiers": None,
            "usd_per_1000_hard": None, "self_host_sensitivity": None,
            "repriced_from": {"usd_per_1000": c["usd_per_1000_estimate"], "cost_axis": c["cost_axis"],
                              "input_usd_per_m": c["input_usd_per_m"]}}
    return cost


def fix_decision_4b(src, row):
    note = src["note"]
    if DECISION_4B_OLD in note:
        note = note.replace(DECISION_4B_OLD, DECISION_4B_NEW)
    else:
        note = note + " " + DECISION_4B_NEW
    assert "used for training, tuning or model selection" not in note
    src["note"] = note + " " + DECISION_4B_GATE.format(heldout=f"{row['heldout_hard_acc_v12']:.3f}",
                                                       public=f"{row['public_hard_acc']:.3f}")


OVERRIDES = {"apus-openjev-4b": reprice_apus, "decision-4b-v12": fix_decision_4b, "decision-4b-v11": fix_decision_4b}

DISCLOSURES = {  # appended to the row note (from the v1.4.2 release and the independent gates)
    "imajev-4b": "Independent #1 gate (25 Sep 2026): PASS — composite recomputed exactly from the raw predictions. Disclosure: the author's training pipeline evaluated every checkpoint on the public JevBench splits as a development monitor (not a selection gate); held-out hard accuracy (0.697) is at the public hard level (0.694). Packaging note: torchvision was missing from the package's [torch] extra and was added to start the server; nothing else was changed.",
    "blink-4b": "Disclosure: the author developed on the public items and on JevBench K5's public hard items. Its sealed accuracy (0.295) is at the 0.293 chance level while its public accuracy is high; the generalization penalty applies. An 8-gram screen found no shared text.",
    "ryotide-qwen": "Disclosure (pre-registered by the author): public hard accuracy 0.658 against held-out hard 0.523. The repository vendors JevBench's published public dataset for running the harness; the serving path does not use it.",
    "ryotide-gemma": "The repository vendors JevBench's published public dataset for running the harness; the serving path does not use it.",
    "imajev-2b": "Packaging note: torchvision was missing from the package's [torch] extra and was added to start the server; nothing else was changed.",
    "imajev-9b": "Packaging note: torchvision was missing from the package's [torch] extra and was added to start the server; nothing else was changed.",
    "plumb-4b": "Independent top-five gate (25 Sep 2026): LEGIT — cost basis (same as its JevK5 parent), public-versus-sealed gap against like-for-like rows, an 8-gram screen of its released training data (no row shares more than two 8-grams with a public item) and an exact composite recomputation.",
    "jpt-4b": "Measured in run 12 (24 Sep) on an H100 80 GB because its pinned SGLang fails on Blackwell GPUs; released with v1.4.3 because its aggregate file was missing at the v1.4.2 cut.",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def clean_basis(text):
    return re.sub(r"^(ESTIMATE:?\s*)+(?=ESTIMATE)", "", text) if text else text


def hardware(basis):
    for pat, name in ((r"H100", "H100 80 GB (evaluator-owned Lium pod)"),
                      (r"RTX PRO 6000", "RTX PRO 6000 Blackwell 96 GB (evaluator-owned Lium pod)")):
        if basis and re.search(pat, basis):
            return name
    return None


def input_files(config):
    files = []
    for line in Path(config).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        path = Path(line).expanduser()
        if path.is_dir():
            found = sorted(glob.glob(str(path / "*-AGGREGATE-SOURCE-*.json")) + glob.glob(str(path / "*-PARTIAL-*.json")))
        else:
            found = sorted(p for p in glob.glob(line) if "-AGGREGATE-SOURCE-" in p or "-PARTIAL-" in p)
        if not found:
            raise SystemExit(f"no AGGREGATE-SOURCE or PARTIAL files for input line: {line}")
        files += [Path(p) for p in found]
    return files


def detail_block(src, row, cost=None):
    m = row["measurements"]
    sp, co = m["old_speed"], m["cost"]
    hw = hardware(sp.get("basis"))
    detail = {
        "key": src["key"], "open": "yes", "underlying": None,
        "has_distribution": not src["sealed"].get("label_only", False), "probability_source": None,
        "endpoint_condition": f"our evaluator-owned Lium GPU pod ({hw or 'see speed basis'}), offline read-only container, "
                              "author's model served on loopback",
        "endpoint_kind": "gpu", "partial": False, "tiers": src["v130"]["tiers"],
        "speed": {"p50_s_raw": sp["p50_raw_s"], "p95_s_raw": sp["p95_raw_s"],
                  "p50_s_adjusted": sp["p50_adjusted_s"], "p95_s_adjusted": sp["p95_adjusted_s"],
                  "adjustment": "x2 + 0.15 s (assumption, not measured)",
                  "run": "serial 242-decision standard+judge run", "hardware": hw,
                  "measured_where": sp.get("basis"), "hard_tier_p50_s": None, "hard_tier_p95_s": None},
        "cost": cost or {"kind": "estimate", "usd_per_1000": co["usd_per_1000_estimate"], "basis": clean_basis(co["basis"]),
                         "usd_per_1000_v11_tiers": None, "usd_per_1000_hard": None, "self_host_sensitivity": None},
        "calibration": {"score": None, "note": None}, "hard": None,
        "release_evidence": {"raw_results_sha256": row.get("raw_results_sha256"), "input_sha256": row.get("input_sha256")},
    }
    return detail


def check_pair(src, row):
    """The owner's aggregate source must be the projection of its full-protocol ROW and reproduce its release score."""
    key = src["key"]
    assert src["key"] == row["key"], (src["key"], row["key"])
    for f in ("v130", "public_acc", "sealed_acc"):
        assert src[f] == row[f], (key, f)
    assert src["v14"]["axes"] == row["v14"]["axes"], key
    s = row["sealed"]
    assert s["n"] == 308 and s["answered_valid"] == 308, (key, "sealed run incomplete")
    counts = row["measurements"]["scope_counts"]
    assert counts["public-source"] + counts["historical-private"] == 534 and counts["current-sealed"] == 308, (key, counts)
    assert row["release_score"]["scoring_module_sha256"] == COMPOSITE_SHA256, key
    _, value = score.score_from_comparison(src)
    assert value == row["release_score"]["score"], (key, value, row["release_score"]["score"])
    assert abs(row["measurements"]["cost"]["cost_axis"] - src["v130"]["axes"]["cost"]) < 1e-9, key
    assert abs(row["measurements"]["old_speed"]["axis"] - src["v130"]["axes"]["speed"]) < 1e-9, key
    # Calibration blend: every v1.4.x row uses the 308/528 weight.
    old, cand = src["v130"]["axes"]["calibration"], src["v14"]["axes"]["calibration"]
    assert abs(old + (s["calibration"] - old) * BLEND - cand) < 1e-9, (key, "calibration blend")


def partial_listing(p):
    part = read(p)
    assert part.get("partial") and not part.get("ranked"), p
    src = {"key": part["key"], "display": part["display"], "author": part.get("author"), "repo": part.get("repo"),
           "class": part["class"], "licence": part.get("licence"), "ranked": False, "source": part["source"],
           "note": part["note"], "note_v14": None, "v130": {"score": None, "rank": None,
                                                            "axes": {a: None for a in old_score.AXES}, "tiers": {}},
           "public_acc": None, "sealed_acc": None, "api_flag": bool(part.get("api_flag")), "sealed": None, "v14": None}
    ms = part["measured"]
    detail = {"key": part["key"], "open": "yes", "endpoint_kind": "cpu", "partial": True,
              "endpoint_condition": part.get("comparability_note"),
              "not_ranked_because": part["not_ranked_because"],
              "partial_measurement": {"attempted": ms["attempted"], "answered": ms["answered"], "timed_out": ms["timed_out"],
                                      "never_attempted": ms["never_attempted"], "by_tier": ms["by_tier"],
                                      "latency_of_answered_s": ms["latency_of_answered_s"]},
              "cost": {"kind": "estimate", "usd_per_1000": None, "basis": part.get("price_basis_if_ranked_later"),
                       "usd_per_1000_v11_tiers": None, "usd_per_1000_hard": None, "self_host_sensitivity": None},
              "release_evidence": {"partial_sha256": sha(p), "raw_results_sha256": part.get("raw_results_sha256"),
                                   "input_sha256": part.get("input_sha256")}}
    return src, detail


def assemble(config):
    previous_keys = {r["key"] for r in read(PREV)["systems"]}
    sources, details, manifest = {}, {}, []
    for path in input_files(config):
        if "-PARTIAL-" in path.name:
            src, detail = partial_listing(path)
            manifest.append({"key": src["key"], "partial": path.name, "partial_sha256": sha(path)})
        else:
            row_path = path.with_name(path.name.replace("-AGGREGATE-SOURCE-", "-ROW-"))
            if not row_path.exists():
                raise SystemExit(f"missing ROW file next to {path.name}")
            src, row = copy.deepcopy(read(path)), read(row_path)
            check_pair(src, row)
            cost = OVERRIDES[src["key"]](src, row) if src["key"] in OVERRIDES else None
            detail = detail_block(src, row, cost)
            detail["release_evidence"].update(aggregate_source_sha256=sha(path), row_sha256=sha(row_path))
            if row.get("input_sha256") != FULL_INPUT_SHA256:
                detail["release_evidence"]["source_input_sha256"] = FULL_INPUT_SHA256
            manifest.append({"key": src["key"], "aggregate_source": path.name, "aggregate_source_sha256": sha(path),
                             "row": row_path.name, "row_sha256": sha(row_path),
                             "override": src["key"] in OVERRIDES})
        key = src["key"]
        if key in previous_keys or key in sources:
            raise SystemExit(f"duplicate key {key}: already in v1.4.2 or listed twice")
        if key in DISCLOSURES:
            src["note"] = (src.get("note") or "") + " | " + DISCLOSURES[key]
        sources[key], details[key] = src, detail
    DATA.mkdir(parents=True, exist_ok=True)
    meta = {"source": "Official full-protocol v1.4.3 addition rows; only system/family/stratum aggregates, no task text, "
                      "answers or per-item output", "sealed_items": 308, "composite_v14_sha256": COMPOSITE_SHA256}
    SOURCES.write_text(json.dumps({"meta": meta, "systems": list(sources.values())}, indent=1, ensure_ascii=False) + "\n")
    DETAILS.write_text(json.dumps(list(details.values()), indent=1, ensure_ascii=False) + "\n")
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    print(f"assembled {len(sources)} addition rows:", ", ".join(sources))


# ---------------------------------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------------------------------
def new_row(source, detail):
    return {
        "key": source["key"], "display": source["display"], "author": source.get("author"), "repo": source.get("repo"),
        "class": source["class"], "licence": source.get("licence"), "open": detail.get("open"), "underlying": None,
        "has_distribution": detail.get("has_distribution"), "probability_source": None,
        "endpoint_condition": detail.get("endpoint_condition"), "endpoint_kind": detail.get("endpoint_kind"),
        "partial": detail.get("partial", False), "ranked": source["ranked"],
        "listing": "ranked" if source["ranked"] else "partial", "not_ranked_because": detail.get("not_ranked_because"),
        "tiers": source["v130"]["tiers"], "speed": detail.get("speed"), "cost": detail.get("cost"),
        "calibration": {"score": None, "note": None}, "hard": None,
        **({"partial_measurement": detail["partial_measurement"]} if "partial_measurement" in detail else {}),
        "release_evidence": detail.get("release_evidence"),
    }


def fmt(x):
    return f"{x:.1f}"


def top_five_note(ranked):
    """A presentation sentence that is true for whatever top five the data produces (method unchanged)."""
    top = ranked[:5]
    by_i = sorted(top, key=lambda r: -r["axes"]["intelligence"])
    lead = top[0]
    parts = [f"{r['display'].split(' (')[0]} {fmt(r['axes']['intelligence'])}" for r in by_i]
    text = f"Intelligence among the top five: {', '.join(parts)}."
    jev = next((r for r in ranked if r["key"] == "jev-1.13.0"), None)
    if jev is not None:
        above = [r for r in top if r["key"] != "jev-1.13.0" and r["axes"]["intelligence"] > jev["axes"]["intelligence"]]
        if above:
            text += (f" Jev 1.13.0 ({fmt(jev['axes']['intelligence'])}, rank {jev['rank']}) is out-reasoned by "
                     f"{['no', 'one', 'two', 'three', 'four', 'five'][len(above)]} of them.")
    if by_i[0]["key"] == lead["key"]:
        text += f" {lead['display'].split(' (')[0]} leads both the JevBench Score and Intelligence among the top five."
    best = max(ranked, key=lambda r: r["axes"]["intelligence"])
    if best["rank"] > 5:
        behind = [a for a in ("speed", "cost", "calibration") if best["axes"][a] < min(r["axes"][a] for r in top)]
        why = f", held back by its {' and '.join(a.capitalize() for a in behind)}" if behind else ""
        text += (f" Rows outside the top five reason better still (up to {fmt(best['axes']['intelligence'])}, "
                 f"{best['display'].split(' (')[0]}, rank {best['rank']}){why}.")
    text += " JevBench weighs the four axes equally; sort by Intelligence for raw reasoning."
    return text


def build():
    assert sha(PREV) == PREV_SHA256, "v1.4.2 artifact changed"
    assert sha(ROOT / "jevbench" / "composite_v14.py") == COMPOSITE_SHA256, "composite_v14 changed"
    prev = read(PREV)
    sources = read(SOURCES)["systems"]
    details = {d["key"]: d for d in read(DETAILS)}
    carried = [copy.deepcopy(r) for r in prev["systems"]]
    carried_keys = {r["key"] for r in carried}
    footnotes = copy.deepcopy(prev["footnotes"])
    rows = list(carried)
    for source in sources:
        key = source["key"]
        assert key not in carried_keys and key not in {r["key"] for r in rows}, key
        row = new_row(source, details[key])
        row["new_in"] = "v1.4.3"
        row["source_round"] = source.get("source")
        row["api_flag"] = bool(source.get("api_flag"))
        row["api_exposure_note"] = ("API — the operator's endpoint received sealed item text, without answers."
                                    if row["api_flag"] else None)
        row["public_accuracy"] = source.get("public_acc")
        row["sealed_accuracy"] = source.get("sealed_acc")
        row["public_minus_sealed_gap_pp"] = (100 * (source["public_acc"] - source["sealed_acc"])
                                             if source.get("sealed_acc") is not None else None)
        sealed = source.get("sealed")
        row["sealed_aggregate"] = ({k: sealed.get(k) for k in ("n", "answered_valid", "by_family", "by_panel_stratum", "ece",
                                                              "mean_tvd_gold_probs", "calibration", "label_only",
                                                              "risk_coverage")} if sealed else None)
        if row["sealed_aggregate"]:
            for k in ("by_family", "by_panel_stratum"):  # one published shape: accuracy per group, 4 decimals
                row["sealed_aggregate"][k] = {g: round(v["accuracy"] if isinstance(v, dict) else v, 4)
                                              for g, v in row["sealed_aggregate"][k].items()}
            row["sealed_aggregate"]["risk_coverage"] = {
                t: {"coverage": round(v["coverage"], 4), "accuracy": None if v["accuracy"] is None else round(v["accuracy"], 4)}
                for t, v in row["sealed_aggregate"]["risk_coverage"].items()}
        row["v130_comparison_rank"] = source["v130"].get("rank")
        row["v130_comparison_score"] = source["v130"].get("score")
        row["scoring_note"] = source.get("note_v14")
        notes = [n for n in (source.get("note"), source.get("note_v14")) if n]
        if notes:
            footnotes[key] = " | ".join(dict.fromkeys(notes))
        axes, value = score.score_from_comparison(source)
        if axes is not None and source["ranked"]:
            assert all(math.isfinite(v) for v in axes.values()), key
            row["axes"] = axes
            row["calibration"]["score"] = axes["calibration"]
            row["jevbench_score"] = value
            row["presets"] = {name: score.harmonic(axes, dict(zip(old_score.AXES, w))) for name, w in old_score.PRESETS.items()}
            row.update(ranked=True, listing="ranked", partial=False, not_ranked_because=None)
        else:
            row.update(axes=None, jevbench_score=None, presets={}, ranked=False, listing="partial", partial=True)
            row["not_ranked_because"] = row["not_ranked_because"] or "No completed sealed v1.4 run"
        rows.append(row)

    ranked = sorted((r for r in rows if r["ranked"]), key=lambda r: -r["jevbench_score"])
    for rank, row in enumerate(ranked, 1):
        row["rank"] = rank
    unranked = [r for r in rows if not r["ranked"]]
    for row in unranked:
        row["rank"] = None
    for row in rows:
        row["rank_under"] = {}
    for name in old_score.PRESETS:
        for rank, row in enumerate(sorted(ranked, key=lambda r: -(r["presets"][name] or 0)), 1):
            row["rank_under"][name] = rank

    added = [s["key"] for s in sources]
    added_ranked = sum(1 for s in sources if s["ranked"])
    artifact = copy.deepcopy(prev)
    artifact.update(
        revision="v1.4.3", status="final", generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        revision_note=(f"v1.4.3 adds {added_ranked} newly measured ranked systems"
                       + (f" and lists {len(added) - added_ranked} partial run{'s' if len(added) - added_ranked > 1 else ''} unranked" if len(added) > added_ranked else "")
                       + ". The v1.4 scoring formulas and all v1.4.2 measurements are unchanged."),
        footnotes=footnotes, systems=ranked + unranked)
    artifact["top_five_note"] = top_five_note(ranked)
    artifact["revision_log"] = prev["revision_log"] + [
        {"revision": "v1.4.3", "date": "2026-09-25",
         "note": (f"Added {added_ranked} newly measured systems on the full 842-decision protocol"
                  + (f" and {len(added) - added_ranked} partial listing{'s' if len(added) - added_ranked > 1 else ''}" if len(added) > added_ranked else "")
                  + ". APUS-OpenJev-v1-4B is priced on the Qwen3.5-4B basis of every other Qwen3.5-4B row. The v1.4 "
                    "scoring formulas and all v1.4.2 rows are unchanged apart from rank. Sealed items and answers are "
                    "not published.")}]
    OUTPUT.write_text(json.dumps(artifact, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", help="INPUT-DIRS.txt: re-assemble the addition files from owner ROW/AGGREGATE dirs first")
    args = parser.parse_args()
    if args.inputs:
        assemble(args.inputs)
    output = build()
    ranked = [r for r in output["systems"] if r["ranked"]]
    top_five = [r["key"] for r in ranked[:5]]
    gate = "UNCHANGED" if top_five == PREVIOUS_TOP_FIVE else "CHANGED (needs Florian's preview approval before publishing)"
    print(f"Built {len(output['systems'])} rows ({len(ranked)} ranked); top five {gate}:")
    for r in ranked[:10]:
        print(f"  {r['rank']:>3}  {r['jevbench_score']:6.2f}  {r['display']}")
