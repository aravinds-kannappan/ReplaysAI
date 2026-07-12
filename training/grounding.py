"""
Grounding filter: keep only distilled pairs whose target is fully traceable to
the facts. This is the anti-hallucination guarantee enforced on the training
data itself, so the student learns to never invent a stat or a name.

Rules (heuristic but strict):
  - Every "salient" number in the target (>= 13, i.e. plausibly a score or stat,
    excluding four-digit years) must appear verbatim among the facts' numbers.
  - Every First-Last name in the target must have its surname present in the
    facts (players and teams mentioned in the facts).

Usage:
  python training/grounding.py --task newsletter
  python training/grounding.py --task broadcast
"""
from __future__ import annotations

import argparse
import json
import os
import re

import _bootstrap  # noqa: F401

_NUM = re.compile(r"\d+")
_NAME = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b")


def _blob(facts: dict) -> str:
    return json.dumps(facts, default=str)


def _facts_numbers(blob: str) -> set[str]:
    return set(_NUM.findall(blob))


def _facts_tokens(blob: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'.-]+", blob)}


def check(facts: dict, target: str) -> tuple[bool, list[str]]:
    blob = _blob(facts)
    ok_numbers = _facts_numbers(blob)
    ok_tokens = _facts_tokens(blob)
    reasons: list[str] = []

    for num in _NUM.findall(target):
        n = int(num)
        if n < 13:              # small counts, quarters, list markers: ignore
            continue
        if 1900 <= n <= 2099:   # a year, not a stat
            continue
        if num not in ok_numbers:
            reasons.append(f"invented number {num}")

    for first, last in _NAME.findall(target):
        # A person reference is grounded if the surname appears in the facts.
        if last.lower() not in ok_tokens and first.lower() not in ok_tokens:
            reasons.append(f"invented name {first} {last}")

    # Allow a tiny amount of noise (e.g. an idiom that reads like a name).
    return (len(reasons) <= 1, reasons)


def filter_file(task: str) -> None:
    src = os.path.join(_bootstrap.DATA_DIR, f"{task}_pairs.jsonl")
    dst = os.path.join(_bootstrap.DATA_DIR, f"{task}_pairs.grounded.jsonl")
    if not os.path.exists(src):
        raise SystemExit(f"Missing {src}. Run distill.py --task {task} first.")
    kept = total = 0
    with open(src) as r, open(dst, "w") as w:
        for line in r:
            rec = json.loads(line)
            total += 1
            ok, _reasons = check(rec.get("facts", {}), rec.get("target", ""))
            if ok:
                w.write(line)
                kept += 1
    rate = (kept / total * 100) if total else 0
    print(f"{task}: kept {kept}/{total} ({rate:.1f}% grounded) -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["newsletter", "broadcast"], required=True)
    args = ap.parse_args()
    filter_file(args.task)


if __name__ == "__main__":
    main()
