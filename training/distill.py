"""
Distill training targets from a strong teacher.

For each facts record from espn_dataset.py, we build the EXACT system+prompt the
API uses at serve time (reusing api.newsletter._newsletter_prompt and
api.broadcast._broadcast_prompt) and ask the teacher (Claude Sonnet) to write the
target. This guarantees the student is trained on the same distribution it will
see in production. Grounding is filtered afterwards by grounding.py.

Usage:
  export ANTHROPIC_API_KEY=...
  python training/distill.py --task newsletter --limit 4000
  python training/distill.py --task broadcast  --limit 6000 --seconds 300
"""
from __future__ import annotations

import argparse
import json
import os

import _bootstrap  # noqa: F401

from api.newsletter import _newsletter_prompt
from api.broadcast import _broadcast_prompt

TEACHER_MODEL = "claude-sonnet-4-6"


def _teacher(system: str, prompt: str, max_tokens: int) -> str | None:
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Set ANTHROPIC_API_KEY (teacher key) to run distillation.")
    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.messages.create(
            model=TEACHER_MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        print(f"[teacher] {type(exc).__name__}: {str(exc)[:200]}")
        return None


def _iter_records(name: str, limit: int):
    path = os.path.join(_bootstrap.DATA_DIR, name)
    if not os.path.exists(path):
        raise SystemExit(f"Missing {path}. Run espn_dataset.py first.")
    with open(path) as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            yield json.loads(line)


def distill_newsletter(limit: int) -> None:
    out = os.path.join(_bootstrap.DATA_DIR, "newsletter_pairs.jsonl")
    n = 0
    with open(out, "w") as w:
        for rec in _iter_records("newsletter_facts.jsonl", limit):
            system, prompt = _newsletter_prompt(
                rec.get("display_name"), rec["favorite_teams"],
                rec.get("followed_players", []), rec["games"], rec["week_key"],
            )
            target = _teacher(system, prompt, max_tokens=1400)
            if not target:
                continue
            w.write(json.dumps({"system": system, "prompt": prompt, "target": target,
                                "facts": {"games": rec["games"], "favorite_teams": rec["favorite_teams"]}}) + "\n")
            n += 1
            if n % 25 == 0:
                print(f"  newsletter pairs: {n}")
    print(f"newsletter_pairs.jsonl: {n} -> {out}")


def distill_broadcast(limit: int, seconds: int) -> None:
    out = os.path.join(_bootstrap.DATA_DIR, "broadcast_pairs.jsonl")
    n = 0
    with open(out, "w") as w:
        for rec in _iter_records("broadcast_facts.jsonl", limit):
            facts = rec["facts"]
            system, prompt, max_tokens = _broadcast_prompt(facts, seconds)
            target = _teacher(system, prompt, max_tokens=max_tokens)
            if not target:
                continue
            w.write(json.dumps({"system": system, "prompt": prompt, "target": target, "facts": facts}) + "\n")
            n += 1
            if n % 25 == 0:
                print(f"  broadcast pairs: {n}")
    print(f"broadcast_pairs.jsonl: {n} -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["newsletter", "broadcast"], required=True)
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--seconds", type=int, default=300, help="broadcast target length")
    args = ap.parse_args()
    if args.task == "newsletter":
        distill_newsletter(args.limit)
    else:
        distill_broadcast(args.limit, args.seconds)


if __name__ == "__main__":
    main()
