"""JevBench CLI.

  python -m jevbench.cli run      --tasks <jsonl[,jsonl...]> \
      --adapter typesafe|systemone_list|gradio_space|local_openjev|openai_compat \
      --results <out.jsonl> [--endpoint URL] [--model NAME] [--key-env ENV] \
      [--cap-usd N] [--ledger PATH] [--raw-dir DIR] [--reserve-usd N] \
      [--price-in-per-m X] [--price-out-per-m X] [--limit N]
  python -m jevbench.cli summarize --tasks <jsonl[,jsonl...]> --results <jsonl> \
      [--ledger PATH] [--public-export PATH] [--include-excluded]

Never prints or logs secrets. Raw responses are written into --raw-dir,
which should live OUTSIDE the repo (defaults to ../private/raw_responses).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .adapters import (GradioSpaceAdapter, LocalOpenJevAdapter, NeedleLocalAdapter,
                       OpenAICompatAdapter, SystemOneListAdapter,
                       RemoteInprocAdapter, SemIfDirectAdapter, SgSystemOneAdapter, So1DeciderAdapter,
                       TypeSafeAdapter, DjevAdapter,
                       LayaLocalAdapter, Gliner2LocalAdapter, VerdictLocalAdapter, PawLocalAdapter, MetaskJevAdapter,
                       ClassifierDevAdapter, CertoLocalAdapter)
from .budget import Ledger
from .runner import DEFAULT_RESERVE_USD, Runner
from .summarize import public_export, summarize
from .tasks import dataset_hash, load_jsonl

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_tasks(spec: str):
    tasks = []
    for part in spec.split(","):
        part = part.strip()
        if part:
            tasks.extend(load_jsonl(part))
    return tasks


def _now() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def cmd_run(args) -> int:
    started = _now()
    tasks = _load_tasks(args.tasks)
    if args.limit:
        tasks = tasks[: args.limit]

    kinds = {"typesafe": TypeSafeAdapter, "systemone_list": SystemOneListAdapter,
             "gradio_space": GradioSpaceAdapter, "local_openjev": LocalOpenJevAdapter,
             "openai_compat": OpenAICompatAdapter,
             "needle_local": NeedleLocalAdapter,
             "semif_direct": SemIfDirectAdapter, "so1_decider": So1DeciderAdapter,
             "remote_inproc": RemoteInprocAdapter, "sg_system_one": SgSystemOneAdapter,
             "djev": DjevAdapter,
             "laya_local": LayaLocalAdapter, "gliner2_local": Gliner2LocalAdapter,
             "verdict_local": VerdictLocalAdapter, "paw_local": PawLocalAdapter,
             "metask_jev": MetaskJevAdapter,
             "classifier_dev": ClassifierDevAdapter, "certo_local": CertoLocalAdapter}
    if args.adapter not in ("typesafe", "djev", "needle_local", "semif_direct", "so1_decider", "sg_system_one", "classifier_dev", "metask_jev") and not args.endpoint:
        print(f"--endpoint required for {args.adapter}", file=sys.stderr)
        return 2
    kwargs = dict(endpoint=args.endpoint, model=args.model,
                  key_env=args.key_env,
                  price_input_per_m=args.price_in_per_m,
                  price_output_per_m=args.price_out_per_m)
    if args.adapter == "openai_compat":
        kwargs["model"] = args.model or ""
    if args.adapter in ("local_openjev", "semif_direct", "so1_decider", "sg_system_one",
                        "laya_local", "gliner2_local", "verdict_local", "paw_local", "certo_local", "metask_jev"):
        kwargs["revision"] = args.revision
    adapter = kinds[args.adapter](**kwargs)
    if args.cost_basis:
        adapter.cost_basis = args.cost_basis
    if args.request_options:
        # Extra provider-specific body fields (e.g. reasoning effort). Logged
        # into the run manifest so a published number names its settings.
        adapter.request_options = json.loads(args.request_options)
    endpoint_desc = getattr(adapter, "endpoint", None) or getattr(adapter, "path", "")
    if os.environ.get("JEVBENCH_WARM_LOAD") == "1" and hasattr(adapter, "load"):
        # v1.1.3 in-process GPU entrants: load weights before the clock starts,
        # like a server that is already up. The load time is printed to the run log.
        _t = time.perf_counter()
        adapter.load()
        print(f"[jevbench] warm load {time.perf_counter() - _t:.1f}s", flush=True)

    ledger = Ledger(args.ledger, cap_usd=args.cap_usd)
    runner = Runner(adapter, ledger, raw_dir=args.raw_dir,
                    default_reserve_usd=args.reserve_usd)
    print(f"[jevbench] adapter={args.adapter} endpoint={endpoint_desc} "
          f"tasks={len(tasks)} cap=${args.cap_usd} ledger={args.ledger}")
    records = runner.run_all(tasks, results_path=args.results,
                             delay_s=args.delay_s)
    failed = sum(1 for r in records if r["status"] == "failed")
    print(f"[jevbench] done: {len(records)}/{len(tasks)} attempted, "
          f"{failed} failed; charged=${ledger.charged:.4f}")
    if args.manifest:
        manifest = {
            "run_label": args.run_label or args.model or args.adapter,
            "adapter": args.adapter, "endpoint": endpoint_desc,
            "requested_model": args.model,
            "resolved_models": sorted({r.get("model") or "" for r in records}),
            "request_options": json.loads(args.request_options) if args.request_options else {},
            "key_env_used": bool(args.key_env),
            "price_input_per_m": args.price_in_per_m,
            "price_output_per_m": args.price_out_per_m,
            "cost_basis": args.cost_basis,
            "dataset_hash": dataset_hash(tasks),
            "n_planned": len(tasks), "n_attempted": len(records),
            "charged_usd": ledger.charged, "delay_s": args.delay_s,
            "started_utc": started, "finished_utc": _now(),
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.manifest)), exist_ok=True)
        with open(args.manifest, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
    return 0 if len(records)==len(tasks) else 3


def cmd_summarize(args) -> int:
    tasks = _load_tasks(args.tasks)
    records = []
    with open(args.results, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    charged = 0.0
    if args.ledger and os.path.exists(args.ledger):
        charged = Ledger(args.ledger).charged
    summary = summarize(tasks, records, charged,
                        headline_only=not args.include_excluded)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.public_export:
        export = public_export(summary, tasks, records)
        export["dataset_hash"] = dataset_hash(tasks)
        os.makedirs(os.path.dirname(os.path.abspath(args.public_export)),
                    exist_ok=True)
        with open(args.public_export, "w", encoding="utf-8") as fh:
            json.dump(export, fh, indent=2, sort_keys=True, ensure_ascii=False)
        print(f"[jevbench] public export -> {args.public_export}",
              file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jevbench")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def ds_default(name: str) -> str:
        return os.path.join(REPO_ROOT, "..", "private", name)

    p_run = sub.add_parser("run", help="run the benchmark over tasks")
    p_run.add_argument("--tasks", required=True)
    p_run.add_argument("--adapter", required=True,
                       choices=["typesafe", "systemone_list", "gradio_space",
                                "local_openjev", "openai_compat", "needle_local",
                                "semif_direct", "so1_decider", "remote_inproc",
                                "sg_system_one", "djev", "laya_local", "gliner2_local",
                                "verdict_local", "paw_local", "classifier_dev", "certo_local", "metask_jev"])
    p_run.add_argument("--endpoint", default=None)
    p_run.add_argument("--model", default=None)
    p_run.add_argument("--key-env", dest="key_env",
                       default="TYPESAFE_API_KEY")
    p_run.add_argument("--results", required=True)
    p_run.add_argument("--ledger", default=ds_default("ledger.jsonl"))
    p_run.add_argument("--raw-dir", dest="raw_dir",
                       default=ds_default("raw_responses"))
    p_run.add_argument("--cap-usd", dest="cap_usd", type=float, default=15.0)
    p_run.add_argument("--reserve-usd", dest="reserve_usd", type=float,
                       default=DEFAULT_RESERVE_USD)
    p_run.add_argument("--price-in-per-m", dest="price_in_per_m", type=float,
                       default=None)
    p_run.add_argument("--price-out-per-m", dest="price_out_per_m", type=float,
                       default=None)
    p_run.add_argument("--limit", type=int, default=None)
    p_run.add_argument("--delay-s", dest="delay_s", type=float, default=0.0,
                       help="pause between requests; be a polite guest on "
                            "someone else's free public demo")
    p_run.add_argument("--request-options", dest="request_options", default=None,
                       help="JSON of extra request body fields, e.g. "
                            "'{\"reasoning_effort\": \"low\"}'")
    p_run.add_argument("--revision", default=None,
                       help="pinned revision of a local checkpoint")
    p_run.add_argument("--run-label", dest="run_label", default=None)
    p_run.add_argument("--cost-basis", dest="cost_basis", default=None,
                       help="why this route's per-decision cost is what it is, "
                            "e.g. no_billable_account_public_demo")
    p_run.add_argument("--manifest", default=None,
                       help="write the run's exact settings here")
    p_run.set_defaults(fn=cmd_run)

    p_sum = sub.add_parser("summarize", help="aggregate results")
    p_sum.add_argument("--tasks", required=True)
    p_sum.add_argument("--results", required=True)
    p_sum.add_argument("--ledger", default=None)
    p_sum.add_argument("--public-export", dest="public_export", default=None)
    p_sum.add_argument("--include-excluded", dest="include_excluded",
                       action="store_true",
                       help="include non-headline (excluded/unmeasured) items")
    p_sum.set_defaults(fn=cmd_summarize)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
