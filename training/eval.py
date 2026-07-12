"""
Held-out evaluation for the trained writers.

Reports, on a sample of grounded pairs (or fresh model outputs if you wire an
endpoint in), the metrics that actually matter for these surfaces:

  Newsletter: grounding rate + section-format adherence (all 4 headers present).
  Broadcast:  grounding rate + turns-JSON validity + turn-count sanity + host mix.

Usage:
  python training/eval.py --task newsletter
  python training/eval.py --task broadcast
"""
from __future__ import annotations

import argparse
import json
import os

import _bootstrap  # noqa: F401

from grounding import check
from api.broadcast import _clean_turns

NEWSLETTER_SECTIONS = ["## Week in Review", "## Your Players This Week", "## Games to Watch", "## The Take"]


def _sample(task: str):
    path = os.path.join(_bootstrap.DATA_DIR, f"{task}_pairs.grounded.jsonl")
    if not os.path.exists(path):
        raise SystemExit(f"Missing {path}. Build the dataset first.")
    with open(path) as fh:
        return [json.loads(line) for line in fh]


def eval_newsletter() -> None:
    rows = _sample("newsletter")
    grounded = fmt_ok = 0
    for r in rows:
        target = r["target"]
        if check(r.get("facts", {}), target)[0]:
            grounded += 1
        if all(sec in target for sec in NEWSLETTER_SECTIONS):
            fmt_ok += 1
    n = len(rows) or 1
    print(f"newsletter (n={len(rows)}): grounding {grounded/n:.1%} | section-format {fmt_ok/n:.1%}")


def eval_broadcast() -> None:
    rows = _sample("broadcast")
    grounded = json_ok = count_ok = mix_ok = 0
    for r in rows:
        target = r["target"]
        if check(r.get("facts", {}), target)[0]:
            grounded += 1
        turns = _clean_turns(target)
        if turns:
            json_ok += 1
            if 8 <= len(turns) <= 60:
                count_ok += 1
            hosts = {t["host"] for t in turns}
            if {"play", "analyst"} <= hosts:
                mix_ok += 1
    n = len(rows) or 1
    print(f"broadcast (n={len(rows)}): grounding {grounded/n:.1%} | json-valid {json_ok/n:.1%} "
          f"| turn-count-ok {count_ok/n:.1%} | both-hosts {mix_ok/n:.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["newsletter", "broadcast"], required=True)
    args = ap.parse_args()
    (eval_newsletter if args.task == "newsletter" else eval_broadcast)()


if __name__ == "__main__":
    main()
