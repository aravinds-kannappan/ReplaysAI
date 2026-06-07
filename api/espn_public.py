"""Small ESPN public API helpers for resilient team/player fallbacks."""
from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_WEB_BASE = "https://site.web.api.espn.com/apis/common/v3/sports"

LEAGUE_KEYS = {
    "NBA": {"sport": "basketball", "league": "nba"},
    "NFL": {"sport": "football", "league": "nfl"},
}

STATIC_TEAMS = {
    "NBA": [
        ("ATL", "Atlanta Hawks"), ("BOS", "Boston Celtics"), ("BKN", "Brooklyn Nets"), ("CHA", "Charlotte Hornets"),
        ("CHI", "Chicago Bulls"), ("CLE", "Cleveland Cavaliers"), ("DAL", "Dallas Mavericks"), ("DEN", "Denver Nuggets"),
        ("DET", "Detroit Pistons"), ("GSW", "Golden State Warriors"), ("HOU", "Houston Rockets"), ("IND", "Indiana Pacers"),
        ("LAC", "LA Clippers"), ("LAL", "Los Angeles Lakers"), ("MEM", "Memphis Grizzlies"), ("MIA", "Miami Heat"),
        ("MIL", "Milwaukee Bucks"), ("MIN", "Minnesota Timberwolves"), ("NOP", "New Orleans Pelicans"), ("NYK", "New York Knicks"),
        ("OKC", "Oklahoma City Thunder"), ("ORL", "Orlando Magic"), ("PHI", "Philadelphia 76ers"), ("PHX", "Phoenix Suns"),
        ("POR", "Portland Trail Blazers"), ("SAC", "Sacramento Kings"), ("SAS", "San Antonio Spurs"), ("TOR", "Toronto Raptors"),
        ("UTA", "Utah Jazz"), ("WAS", "Washington Wizards"),
    ],
    "NFL": [
        ("ARI", "Arizona Cardinals"), ("ATL", "Atlanta Falcons"), ("BAL", "Baltimore Ravens"), ("BUF", "Buffalo Bills"),
        ("CAR", "Carolina Panthers"), ("CHI", "Chicago Bears"), ("CIN", "Cincinnati Bengals"), ("CLE", "Cleveland Browns"),
        ("DAL", "Dallas Cowboys"), ("DEN", "Denver Broncos"), ("DET", "Detroit Lions"), ("GB", "Green Bay Packers"),
        ("HOU", "Houston Texans"), ("IND", "Indianapolis Colts"), ("JAX", "Jacksonville Jaguars"), ("KC", "Kansas City Chiefs"),
        ("LV", "Las Vegas Raiders"), ("LAC", "Los Angeles Chargers"), ("LAR", "Los Angeles Rams"), ("MIA", "Miami Dolphins"),
        ("MIN", "Minnesota Vikings"), ("NE", "New England Patriots"), ("NO", "New Orleans Saints"), ("NYG", "New York Giants"),
        ("NYJ", "New York Jets"), ("PHI", "Philadelphia Eagles"), ("PIT", "Pittsburgh Steelers"), ("SF", "San Francisco 49ers"),
        ("SEA", "Seattle Seahawks"), ("TB", "Tampa Bay Buccaneers"), ("TEN", "Tennessee Titans"), ("WAS", "Washington Commanders"),
    ],
}


def _get_json(url: str, params: Optional[dict] = None) -> dict:
    full_url = f"{url}?{urlencode(params)}" if params else url
    request = Request(full_url, headers={"User-Agent": "ReplaysAI/1.0"})
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def get_league_keys(sport: str) -> dict[str, str]:
    return LEAGUE_KEYS[sport.upper()]


def fetch_espn_teams(sport: str) -> list[dict]:
    keys = get_league_keys(sport)
    sport_key = sport.upper()
    try:
        data = _get_json(f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/teams")
        league = (data.get("sports") or [{}])[0].get("leagues", [{}])[0]
    except Exception:
        return fallback_teams(sport_key)
    teams = []

    for item in league.get("teams", []):
        team = item.get("team", {})
        if not team.get("id"):
            continue
        synthetic_id = (1000 if sport_key == "NBA" else 2000) + int(team.get("id"))
        teams.append({
            "id": synthetic_id,
            "external_id": str(team.get("id")),
            "name": team.get("displayName") or team.get("name"),
            "abbreviation": team.get("abbreviation"),
            "sport": sport_key,
            "conference": "",
            "division": "",
            "logo": (team.get("logos") or [{}])[0].get("href"),
            "color": team.get("color"),
        })
    return teams or fallback_teams(sport_key)


def fallback_teams(sport: str) -> list[dict]:
    sport_key = sport.upper()
    base = 1000 if sport_key == "NBA" else 2000
    return [
        {
            "id": base + index + 1,
            "external_id": str(index + 1),
            "name": name,
            "abbreviation": abbr,
            "sport": sport_key,
            "conference": "",
            "division": "",
            "logo": None,
            "color": None,
        }
        for index, (abbr, name) in enumerate(STATIC_TEAMS.get(sport_key, []))
    ]


def fetch_espn_athletes(sport: str, limit: int = 80) -> list[dict]:
    keys = get_league_keys(sport)
    sport_key = sport.upper()
    try:
        data = _get_json(
            f"{ESPN_WEB_BASE}/{keys['sport']}/{keys['league']}/statistics/byathlete",
            {"limit": limit},
        )
    except Exception:
        return fallback_athletes(sport_key, limit)
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
            "sport": sport_key,
            "impact_score": impact,
            "headshot": (athlete.get("headshot") or {}).get("href"),
        })
    return athletes or fallback_athletes(sport_key, limit)


def fallback_athletes(sport: str, limit: int = 80) -> list[dict]:
    names = {
        "NBA": [
            ("Nikola Jokic", "C", "DEN"), ("Shai Gilgeous-Alexander", "G", "OKC"), ("Luka Doncic", "G", "LAL"),
            ("Giannis Antetokounmpo", "F", "MIL"), ("Jayson Tatum", "F", "BOS"), ("Anthony Edwards", "G", "MIN"),
            ("Stephen Curry", "G", "GSW"), ("Jalen Brunson", "G", "NYK"), ("Kevin Durant", "F", "PHX"),
            ("Victor Wembanyama", "C", "SAS"),
        ],
        "NFL": [
            ("Patrick Mahomes", "QB", "KC"), ("Josh Allen", "QB", "BUF"), ("Lamar Jackson", "QB", "BAL"),
            ("Justin Jefferson", "WR", "MIN"), ("Ja'Marr Chase", "WR", "CIN"), ("Christian McCaffrey", "RB", "SF"),
            ("CeeDee Lamb", "WR", "DAL"), ("Micah Parsons", "EDGE", "DAL"), ("T.J. Watt", "EDGE", "PIT"),
            ("Travis Kelce", "TE", "KC"),
        ],
    }.get(sport.upper(), [])
    return [
        {
            "id": (3000 if sport.upper() == "NBA" else 4000) + index + 1,
            "name": name,
            "position": position,
            "team": team,
            "sport": sport.upper(),
            "impact_score": round(96 - index * 3.1, 1),
            "headshot": None,
        }
        for index, (name, position, team) in enumerate(names[:limit])
    ]
