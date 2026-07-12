"""
Newsletter curation ranker (inference).

This is the "curated and personalized" half of the newsletter agent: it scores
candidate content items (a game result, a followed player's line, a news story)
for a specific fan and returns them ranked, so the writer fills in the sections
that matter most to this fan rather than a fixed dump of recent games.

The model is a small linear relevance scorer: score = sigmoid(b + w · features).
Weights are trained offline (logistic regression / LightGBM distilled to linear
weights) on ESPN features plus real interaction logs, then exported to
`api/curation_weights.json`. Until that file exists the heuristic weights below
are used, so the ranker works on day one and improves once trained. Inference is
pure Python: no ML runtime is shipped to the serverless function.

See training/README.md (train_curation.py) for how the weights are produced.
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache

# Heuristic cold-start weights. Deliberately sensible, not learned: a fan cares
# most about their own teams and players, then recent and high-magnitude events.
_HEURISTIC = {
    "version": "heuristic-v1",
    "bias": -0.5,
    "weights": {
        "followed_team": 2.2,
        "followed_player": 2.0,
        "recency": 1.3,
        "magnitude": 1.1,
        "upcoming": 0.6,
    },
}

_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "curation_weights.json")


@lru_cache(maxsize=1)
def _weights() -> dict:
    try:
        with open(_WEIGHTS_PATH, "r") as fh:
            data = json.load(fh)
        if isinstance(data.get("weights"), dict):
            return data
    except Exception:
        pass
    return _HEURISTIC


def model_label() -> str:
    """Honest label for the UI: which ranker actually ran."""
    v = _weights().get("version", "heuristic-v1")
    return "trained curation ranker" if not v.startswith("heuristic") else "heuristic curation ranker"


def _features(item: dict) -> dict:
    recency_days = float(item.get("recency_days", 3.0))
    return {
        "followed_team": 1.0 if item.get("followed_team") else 0.0,
        "followed_player": 1.0 if item.get("followed_player") else 0.0,
        "recency": math.exp(-max(0.0, recency_days) / 7.0),  # 1.0 today, decays weekly
        "magnitude": min(1.0, max(0.0, float(item.get("magnitude", 0.0)))),
        "upcoming": 1.0 if item.get("upcoming") else 0.0,
    }


def score_item(item: dict) -> float:
    w = _weights()
    feats = _features(item)
    z = float(w.get("bias", 0.0)) + sum(w["weights"].get(k, 0.0) * v for k, v in feats.items())
    return 1.0 / (1.0 + math.exp(-z))


def rank_items(items: list[dict], limit: int | None = None) -> list[dict]:
    """Return items sorted by learned relevance, each annotated with `_score`."""
    scored = [{**it, "_score": round(score_item(it), 4)} for it in items]
    scored.sort(key=lambda it: it["_score"], reverse=True)
    return scored[:limit] if limit else scored
