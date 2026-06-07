"""Small ESPN public API helpers for resilient team/player fallbacks."""
from __future__ import annotations

from typing import Optional

import requests

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_WEB_BASE = "https://site.web.api.espn.com/apis/common/v3/sports"

LEAGUE_KEYS = {
    "NBA": {"sport": "basketball", "league": "nba"},
    "NFL": {"sport": "football", "league": "nfl"},
}


def _get_json(url: str, params: Optional[dict] = None) -> dict:
    response = requests.get(url, params=params or {}, timeout=12)
    response.raise_for_status()
    return response.json()


def get_league_keys(sport: str) -> dict[str, str]:
    return LEAGUE_KEYS[sport.upper()]


def fetch_espn_teams(sport: str) -> list[dict]:
    keys = get_league_keys(sport)
    data = _get_json(f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/teams")
    league = (data.get("sports") or [{}])[0].get("leagues", [{}])[0]
    teams = []

    for item in league.get("teams", []):
        team = item.get("team", {})
        if not team.get("id"):
            continue
        teams.append({
            "external_id": str(team.get("id")),
            "name": team.get("displayName") or team.get("name"),
            "abbreviation": team.get("abbreviation"),
            "sport": sport.upper(),
            "conference": "",
            "division": "",
            "logo": (team.get("logos") or [{}])[0].get("href"),
            "color": team.get("color"),
        })
    return teams


def fetch_espn_athletes(sport: str, limit: int = 80) -> list[dict]:
    keys = get_league_keys(sport)
    data = _get_json(
        f"{ESPN_WEB_BASE}/{keys['sport']}/{keys['league']}/statistics/byathlete",
        {"limit": limit},
    )
    athletes = []

    for index, item in enumerate(data.get("athletes", [])):
        athlete = item.get("athlete", {})
        if not athlete.get("id"):
            continue
        categories = item.get("categories", [])
        values = []
        for category in categories:
            values.extend(v for v in category.get("values", []) if isinstance(v, (int, float)))
        impact = round(sum(values[:6]) / max(1, min(len(values), 6)), 1) if values else round(80 - index * 0.5, 1)

        athletes.append({
            "id": int(athlete.get("id")),
            "name": athlete.get("displayName"),
            "position": (athlete.get("position") or {}).get("abbreviation"),
            "team": athlete.get("teamShortName") or ((athlete.get("teams") or [{}])[0].get("abbreviation")),
            "sport": sport.upper(),
            "impact_score": impact,
            "headshot": (athlete.get("headshot") or {}).get("href"),
        })
    return athletes
