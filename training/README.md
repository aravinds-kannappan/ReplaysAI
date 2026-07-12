# ReplaysAI trained agents

This directory trains the two flagship "agents" that write ReplaysAI content:

- **Newsletter writer**: turns a fan's ranked weekly facts into a magazine-style digest.
- **Broadcast writer**: turns a game's play-by-play into a two-host commentary script (turns JSON).

Plus a small **curation ranker** that personalizes which content a fan sees.

Everything here runs **offline**. It is intentionally kept out of `requirements.txt` and out of the
Vercel serverless bundle (see `.vercelignore`), so the deployed API stays small. The app calls the
finished models over an OpenAI-compatible API and reads the ranker's exported weights; it never
imports anything in this directory.

Honesty note (matches the app's labeling rule): a model is only called "trained" once these scripts
have actually produced it. Until then the newsletter/broadcast surfaces run on the Anthropic LLM or
the deterministic template, and the ranker uses heuristic weights. The API reports which path ran
(`source: trained | llm | fallback`, `curation: trained|heuristic ...`).

---

## The two problems, and why distillation

We do not have a labeled corpus of "ESPN game facts -> ideal ReplaysAI newsletter". We do have:

1. Real, structured ESPN data (box scores, play-by-play, leaders, standings, news) for thousands of
   past NBA + NFL games, reachable through the app's own `api/espn_public.py` provider.
2. A strong open teacher model on Orthogonal that, given those facts and the exact production prompt,
   writes a good, grounded draft.

So we **distill**: the teacher generates targets from real facts, a grounding filter throws out any
draft that invents a number or a name, and we fine-tune a smaller open student on the survivors. The
student learns our format and voice cheaply, runs cheaply, and (because we reuse the production
prompt builders) is trained on exactly the inputs it will see in production.

**Teacher** (big, on Orthogonal, OpenAI-compatible): DeepSeek-V3 / Kimi-K2 / GLM-4.5 / GPT-OSS-120B.
No Anthropic key required. **Student** (small, LoRA/QLoRA, one adapter per writer): Qwen2.5-7B (fits a
single Colab A100 in bf16) or GPT-OSS-20B (QLoRA, matches the Orthogonal serving family).

---

## Pipeline

```
espn_dataset.py   real ESPN facts        -> data/{newsletter,broadcast}_facts.jsonl
      │           (reuses api/espn_public.py; same fact shape the API builds)
      ▼
distill.py        teacher writes targets -> data/{...}_pairs.jsonl
      │           (reuses the PRODUCTION prompt builders, so train == serve)
      ▼
grounding.py      drop ungrounded drafts -> data/{...}_pairs.grounded.jsonl
      │           (every number/name in the target must trace to the facts)
      ▼
train_writer_lora.py   LoRA fine-tune    -> out/{newsletter,broadcast}-writer/  (adapter)
      ▼
(deploy adapter on Baseten) -> set TRAINED_BASE_URL / TRAINED_API_KEY / NEWSLETTER_MODEL / BROADCAST_MODEL

train_curation.py  logistic ranker       -> ../api/curation_weights.json (linear weights, pure-python at serve)
eval.py            held-out metrics      -> grounding rate, format adherence, JSON validity
```

### 1. Build the dataset (real data)
```bash
python training/espn_dataset.py --sports NBA NFL --seasons 3 --max-games 1500
```
Writes one broadcast record per finished game (its `facts`), and one newsletter record per
(synthetic fan profile x ISO week), where a profile is a random subset of real teams/players. Inputs
only: no targets yet.

### 2. Distill targets from the teacher (Orthogonal)
```bash
export ORTHO_BASE_URL=https://...       # Orthogonal OpenAI-compatible base URL
export ORTHO_API_KEY=...                # Orthogonal key
python training/distill.py --task newsletter --limit 4000 --teacher-model deepseek-ai/DeepSeek-V3
python training/distill.py --task broadcast  --limit 6000 --teacher-model deepseek-ai/DeepSeek-V3
```
Each record is sent through the **same system+prompt** the API uses at serve time
(`api.newsletter._newsletter_prompt` / `api.broadcast._broadcast_prompt`), so the student never
sees a distribution shift. No Anthropic key is used.

### 3. Grounding filter
```bash
python training/grounding.py --task newsletter
python training/grounding.py --task broadcast
```
Rejects any pair whose target contains a number or a capitalized name not present in the facts. This
is the anti-hallucination guarantee, enforced on the training data itself.

### 4. LoRA fine-tune (Colab A100)
```bash
# single A100 40GB: Qwen2.5-7B in bf16 LoRA, or GPT-OSS-20B with --qlora
python training/train_writer_lora.py --task newsletter --base Qwen/Qwen2.5-7B-Instruct
python training/train_writer_lora.py --task broadcast  --base Qwen/Qwen2.5-7B-Instruct
```
Then deploy each adapter on Orthogonal / Baseten and point the API's `TRAINED_*` env vars at it.

### 5. Curation ranker
```bash
python training/train_curation.py            # exports ../api/curation_weights.json
```
Trains a logistic relevance model on ESPN features (followed team/player, recency, magnitude,
upcoming) with cold-start labels from heuristics + teacher judgments, then **refined on real
interaction logs** once the app has them (which sections fans expand/click, logged now that Phase 2
gives us a datastore). It exports linear weights only, so serving stays pure-Python with no ML
runtime in the function.

### 6. Evaluate
```bash
python training/eval.py --task newsletter
python training/eval.py --task broadcast
```
Reports, on a held-out split: grounding/factuality rate, section-format adherence (newsletter),
turns-JSON validity + turn count (broadcast), and an optional teacher-preference win-rate vs the
plain-prompt baseline.

---

## Dataset provenance and rights
Inputs are real ESPN public data (the same source the live app uses). Targets are model-generated
prose grounded strictly in that data and filtered for factuality. We do not train on copyrighted
article text or broadcast transcripts; if a licensed transcript corpus is later added for the
broadcast voice, keep it in a separate, clearly-licensed path.

## What the API needs (set in Vercel env)
| Var | Purpose |
|---|---|
| `TRAINED_BASE_URL` | OpenAI-compatible base URL of the Baseten deployment |
| `TRAINED_API_KEY` | key for that deployment |
| `NEWSLETTER_MODEL` | deployed newsletter-writer adapter id |
| `BROADCAST_MODEL` | deployed broadcast-writer adapter id |

Unset any of these and that surface cleanly falls back to the Anthropic LLM, then the deterministic
template. `api/curation_weights.json` is committed by `train_curation.py`; if absent, the heuristic
weights in `api/curation.py` are used.
