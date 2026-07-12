"""
Train the newsletter curation ranker.

A logistic relevance model over the same five features the API computes at serve
time (see api/curation.py `_features`). It learns from REAL interaction logs when
they exist (which newsletter sections fans expand/click, logged now that the app
has a datastore) and cold-starts from a labeled sample otherwise. Only the linear
weights are exported, to `api/curation_weights.json`, so serving stays pure-Python
with no ML runtime in the function.

Run it once real logs accumulate; until then the app uses the heuristic weights
baked into api/curation.py and honestly labels the ranker "heuristic".

Usage:
  python training/train_curation.py                 # cold-start (synthetic labels)
  python training/train_curation.py --logs data/interactions.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random

import _bootstrap  # noqa: F401

# Fixed order: MUST match api/curation.py `_features` keys.
FEATURES = ["followed_team", "followed_player", "recency", "magnitude", "upcoming"]
OUT_PATH = os.path.join(os.path.dirname(_bootstrap.__file__), "..", "api", "curation_weights.json")


def _load_logs(path: str | None) -> list[tuple[list[float], int]]:
    """Real interaction rows: {"features": {...}, "engaged": 0|1}."""
    rows: list[tuple[list[float], int]] = []
    if path and os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                rec = json.loads(line)
                f = rec.get("features", {})
                rows.append(([float(f.get(k, 0.0)) for k in FEATURES], int(rec.get("engaged", 0))))
    return rows


def _synthetic(n: int) -> list[tuple[list[float], int]]:
    """Cold-start: a noisy oracle so the fit is real (weights differ from the
    hand-set heuristic) rather than an identity of the prior."""
    rng = random.Random(7)
    rows = []
    for _ in range(n):
        ft = rng.random() < 0.5
        fp = rng.random() < 0.3
        rec = rng.random()          # already the exp-decayed feature in [0,1]
        mag = rng.random()
        up = rng.random() < 0.25
        # latent relevance: dominated by personalization, then recency/magnitude
        z = 2.4 * ft + 1.9 * fp + 1.2 * rec + 0.9 * mag + 0.5 * up - 2.2
        p = 1.0 / (1.0 + pow(2.718281828, -z))
        label = 1 if rng.random() < p else 0
        rows.append(([1.0 if ft else 0.0, 1.0 if fp else 0.0, rec, mag, 1.0 if up else 0.0], label))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=None, help="JSONL of real interactions")
    ap.add_argument("--min-real", type=int, default=500, help="min real rows before skipping synthetic")
    args = ap.parse_args()

    from sklearn.linear_model import LogisticRegression
    import numpy as np

    real = _load_logs(args.logs)
    rows = real if len(real) >= args.min_real else real + _synthetic(4000)
    version = "trained-logs-v1" if len(real) >= args.min_real else "trained-coldstart-v1"
    print(f"training on {len(rows)} rows ({len(real)} real) -> {version}")

    X = np.array([r[0] for r in rows], dtype=float)
    y = np.array([r[1] for r in rows], dtype=int)
    clf = LogisticRegression(max_iter=1000, C=1.0).fit(X, y)

    weights = {k: round(float(w), 4) for k, w in zip(FEATURES, clf.coef_[0])}
    payload = {"version": version, "bias": round(float(clf.intercept_[0]), 4), "weights": weights}

    with open(os.path.abspath(OUT_PATH), "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"train accuracy: {clf.score(X, y):.3f}")
    print(f"wrote {os.path.abspath(OUT_PATH)}:\n{json.dumps(payload, indent=2)}")


if __name__ == "__main__":
    main()
