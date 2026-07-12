"""
Distill training targets from a strong teacher.

For each facts record from espn_dataset.py, we build the EXACT system+prompt the
API uses at serve time (reusing api.newsletter._newsletter_prompt and
api.broadcast._broadcast_prompt) and ask the teacher to write the target. This
guarantees the student is trained on the same distribution it will see in
production. Grounding is filtered afterwards by grounding.py.

The teacher is a strong OPEN model served over an OpenAI-compatible API
(Orthogonal / Baseten): no Anthropic key needed. Pick a big instruct model as
the teacher (e.g. DeepSeek-V3, Kimi-K2, GLM-4.5, or GPT-OSS-120B) and fine-tune
a smaller student on its grounded output.

Usage:
  export ORTHO_BASE_URL=https://...   # OpenAI-compatible base URL
  export ORTHO_API_KEY=...            # Orthogonal key
  python training/distill.py --task newsletter --limit 4000 --teacher-model deepseek-ai/DeepSeek-V3
  python training/distill.py --task broadcast  --limit 6000 --seconds 300
"""
from __future__ import annotations

import argparse
import json
import os

import _bootstrap  # noqa: F401

from api.newsletter import _newsletter_prompt
from api.broadcast import _broadcast_prompt

# A strong open teacher on Orthogonal. Override with --teacher-model.
DEFAULT_TEACHER = os.environ.get("TEACHER_MODEL", "deepseek-ai/DeepSeek-V3")

_client = None
_teacher_model = DEFAULT_TEACHER


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        base_url = os.environ.get("ORTHO_BASE_URL") or os.environ.get("TRAINED_BASE_URL")
        key = os.environ.get("ORTHO_API_KEY") or os.environ.get("TRAINED_API_KEY")
        if not (base_url and key):
            raise SystemExit("Set ORTHO_BASE_URL and ORTHO_API_KEY (Orthogonal teacher) to run distillation.")
        _client = OpenAI(api_key=key, base_url=base_url)
    return _client


def _teacher(system: str, prompt: str, max_tokens: int) -> str | None:
    try:
        resp = _get_client().chat.completions.create(
            model=_teacher_model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip() or None
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
    global _teacher_model
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["newsletter", "broadcast"], required=True)
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--seconds", type=int, default=300, help="broadcast target length")
    ap.add_argument("--teacher-model", default=DEFAULT_TEACHER,
                    help="strong open teacher on Orthogonal (e.g. deepseek-ai/DeepSeek-V3, moonshotai/Kimi-K2)")
    args = ap.parse_args()
    _teacher_model = args.teacher_model
    print(f"teacher: {_teacher_model}")
    if args.task == "newsletter":
        distill_newsletter(args.limit)
    else:
        distill_broadcast(args.limit, args.seconds)


if __name__ == "__main__":
    main()
