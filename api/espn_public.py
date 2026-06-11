"""Small ESPN public API helpers for real ESPN team/player/game data."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_cls, datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_WEB_BASE = "https://site.web.api.espn.com/apis/common/v3/sports"

LEAGUE_KEYS = {
    "NBA": {"sport": "basketball", "league": "nba"},
    "NFL": {"sport": "football", "league": "nfl"},
}

NBA_SEASON_WINDOWS = {
    "2015-16": (date_cls(2015, 10, 27), date_cls(2016, 6, 19)),
    "2016-17": (date_cls(2016, 10, 25), date_cls(2017, 6, 12)),
    "2017-18": (date_cls(2017, 10, 17), date_cls(2018, 6, 8)),
    "2018-19": (date_cls(2018, 10, 16), date_cls(2019, 6, 13)),
    "2019-20": (date_cls(2019, 10, 22), date_cls(2020, 10, 11)),
    "2020-21": (date_cls(2020, 12, 22), date_cls(2021, 7, 22)),
    "2021-22": (date_cls(2021, 10, 19), date_cls(2022, 6, 16)),
    "2022-23": (date_cls(2022, 10, 18), date_cls(2023, 6, 12)),
    "2023-24": (date_cls(2023, 10, 24), date_cls(2024, 6, 17)),
    "2024-25": (date_cls(2024, 10, 22), date_cls(2025, 6, 30)),
    "2025-26": (date_cls(2025, 10, 21), date_cls(2026, 6, 30)),
}


# Warm serverless instances reuse this cache, so repeat dashboard loads avoid
# re-hitting ESPN for every season window.
_CACHE_TTL_SECONDS = 60.0
_CACHE_MAX_ENTRIES = 256
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _get_json(url: str, params: Optional[dict] = None) -> dict:
    full_url = f"{url}?{urlencode(params)}" if params else url
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(full_url)
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]

    response = httpx.get(
        full_url,
        headers={"User-Agent": "ReplaysAI/1.0"},
        timeout=12,
        follow_redirects=True,
    )
    response.raise_for_status()
    data = response.json()

    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            for stale_key, _ in sorted(_cache.items(), key=lambda item: item[1][0])[: _CACHE_MAX_ENTRIES // 4]:
                _cache.pop(stale_key, None)
        _cache[full_url] = (now, data)
    return data


def get_league_keys(sport: str) -> dict[str, str]:
    return LEAGUE_KEYS[sport.upper()]


def fetch_espn_teams(sport: str) -> list[dict]:
    keys = get_league_keys(sport)
    sport_key = sport.upper()
    try:
        data = _get_json(f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/teams")
        league = (data.get("sports") or [{}])[0].get("leagues", [{}])[0]
    except Exception:
        return []
    teams = []

    for item in league.get("teams", []):
        team = item.get("team", {})
        if not team.get("id"):
            continue
        teams.append({
            "id": int(team.get("id")),
            "external_id": str(team.get("id")),
            "name": team.get("displayName") or team.get("name"),
            "abbreviation": team.get("abbreviation"),
            "sport": sport_key,
            "conference": "",
            "division": "",
            "logo": (team.get("logos") or [{}])[0].get("href"),
            "color": team.get("color"),
        })
    return teams


def _parse_espn_datetime(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return raw


def _status_from_event(event: dict) -> str:
    status = ((event.get("status") or {}).get("type") or {})
    name = (status.get("name") or status.get("state") or "").lower()
    completed = bool(status.get("completed"))
    if completed or "final" in name or name in {"post", "postponed"}:
        return "final"
    if name in {"in", "live", "inprogress"} or "in_progress" in name:
        return "live"
    return "scheduled"


def _score_value(raw: object) -> int | None:
    try:
        if raw in (None, ""):
            return None
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return None


def _team_from_competitor(competitor: dict, sport: str) -> dict:
    team = competitor.get("team") or {}
    external_id = team.get("id") or competitor.get("id") or "0"
    return {
        "id": int(external_id),
        "external_id": str(external_id),
        "name": team.get("displayName") or team.get("shortDisplayName") or team.get("name"),
        "abbreviation": team.get("abbreviation") or team.get("shortDisplayName"),
        "sport": sport.upper(),
    }


def _event_to_game(event: dict, sport: str) -> dict | None:
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competitors = competitions[0].get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home or not away:
        return None

    event_id = str(event.get("id") or "")
    if not event_id:
        return None

    home_team = _team_from_competitor(home, sport)
    away_team = _team_from_competitor(away, sport)
    return {
        "id": int(event_id),
        "external_id": event_id,
        "sport": sport.upper(),
        "status": _status_from_event(event),
        "game_date": _parse_espn_datetime(event.get("date")),
        "home_team": {"id": home_team["id"], "name": home_team["name"], "abbreviation": home_team["abbreviation"]},
        "away_team": {"id": away_team["id"], "name": away_team["name"], "abbreviation": away_team["abbreviation"]},
        "home_score": _score_value(home.get("score")),
        "away_score": _score_value(away.get("score")),
        "video_url": None,
    }


def _nfl_season_windows(seasons: int) -> list[tuple[str, date_cls, date_cls]]:
    today = date_cls.today()
    start_year = today.year if today.month >= 8 else today.year - 1
    windows = []
    for year in range(start_year - seasons + 1, start_year + 1):
        windows.append((str(year), date_cls(year, 9, 1), date_cls(year + 1, 2, 28)))
    return windows


def _season_windows(sport: str, seasons: int) -> list[tuple[str, date_cls, date_cls]]:
    if sport.upper() == "NBA":
        windows = dict(NBA_SEASON_WINDOWS)
        # Keep the current season covered even after the hardcoded table ends,
        # so the feed never goes stale at a season boundary.
        today = date_cls.today()
        start_year = today.year if today.month >= 9 else today.year - 1
        label = f"{start_year}-{str(start_year + 1)[-2:]}"
        if label not in windows:
            windows[label] = (date_cls(start_year, 10, 1), date_cls(start_year + 1, 6, 30))
        return [(label, start, end) for label, (start, end) in list(windows.items())[-seasons:]]
    return _nfl_season_windows(seasons)


def _date_range(start: date_cls, end: date_cls) -> str:
    return f"{start:%Y%m%d}-{end:%Y%m%d}"


def fetch_espn_scoreboard(sport: str, date: str | None = None, limit: int = 20) -> list[dict]:
    keys = get_league_keys(sport)
    # ESPN honors limits well above 100; capping lower truncates multi-week
    # date ranges mid-window and silently drops the newest games.
    params = {"limit": min(max(limit, 1), 1000)}
    if date:
        params["dates"] = date.replace("-", "") if len(date) == 10 else date
    data = _get_json(f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/scoreboard", params)
    games = [_event_to_game(event, sport) for event in data.get("events", [])]
    return [game for game in games if game][:limit]


def fetch_espn_games(sport: str, date: str | None = None, limit: int = 20, seasons: int = 10) -> list[dict]:
    """Return real ESPN games across the requested date or the last N seasons."""
    sport_key = sport.upper()
    if date:
        try:
            return fetch_espn_scoreboard(sport_key, date=date, limit=limit)
        except Exception:
            return []

    seen: set[int] = set()
    games: list[dict] = []

    # Today's scoreboard first: live and just-scheduled games (e.g. tonight's
    # Finals game) must always be present regardless of season-window slicing.
    try:
        for game in fetch_espn_scoreboard(sport_key, limit=50):
            if game["id"] not in seen:
                seen.add(game["id"])
                games.append(game)
    except Exception:
        pass

    per_window = max(1, limit // max(1, seasons))
    today = date_cls.today()
    windows = []
    for _, start, end in reversed(_season_windows(sport_key, seasons)):
        end = min(end, today)
        if end >= start:
            windows.append((start, end))

    def _window_games(window: tuple[date_cls, date_cls]) -> list[dict]:
        start, end = window
        end_slice_start = max(start, end - timedelta(days=60))
        try:
            # Full range limit: a 60-day slice can exceed 100 games, and ESPN
            # returns events oldest-first, so a low limit drops the newest games.
            window_games = fetch_espn_scoreboard(sport_key, date=_date_range(end_slice_start, end), limit=1000)
            if not window_games:
                window_games = fetch_espn_scoreboard(sport_key, date=_date_range(start, end), limit=1000)
            return window_games
        except Exception:
            return []

    if not windows:
        return games
    with ThreadPoolExecutor(max_workers=min(8, len(windows))) as pool:
        results = list(pool.map(_window_games, windows))

    for window_games in results:
        added = 0
        for game in sorted(window_games, key=lambda g: g.get("game_date") or "", reverse=True):
            if game["id"] in seen:
                continue
            seen.add(game["id"])
            games.append(game)
            added += 1
            if len(games) >= limit:
                return games
            if added >= per_window:
                break
    return games


def fetch_espn_game_summary(sport: str, event_id: str | int) -> dict:
    keys = get_league_keys(sport)
    return _get_json(
        f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/summary",
        {"event": str(event_id)},
    )


def fetch_espn_game(sport: str, event_id: str | int) -> dict | None:
    summary = fetch_espn_game_summary(sport, event_id)
    header = summary.get("header") or {}
    competitions = header.get("competitions") or []
    event = {
        "id": str(event_id),
        "date": competitions[0].get("date") if competitions else None,
        "status": header.get("status"),
        "competitions": competitions,
    }
    return _event_to_game(event, sport)


def fetch_espn_game_by_id(event_id: str | int, sports: tuple[str, ...] = ("NBA", "NFL")) -> tuple[str, dict] | None:
    for sport in sports:
        try:
            game = fetch_espn_game(sport, event_id)
        except Exception:
            game = None
        if game:
            return sport, game
    return None


def fetch_espn_summary_by_id(event_id: str | int, sports: tuple[str, ...] = ("NBA", "NFL")) -> tuple[str, dict] | None:
    for sport in sports:
        try:
            summary = fetch_espn_game_summary(sport, event_id)
        except Exception:
            summary = None
        if summary and summary.get("header"):
            return sport, summary
    return None


def classify_play_description(description: str, sport: str) -> str:
    text = description.lower()
    if sport.upper() == "NFL":
        if "touchdown" in text:
            return "touchdown"
        if "intercept" in text:
            return "interception"
        if "sack" in text:
            return "sack"
        if "field goal" in text:
            return "field_goal"
        if "fumble" in text:
            return "turnover"
        if "pass" in text:
            return "pass"
        if "rush" in text or "run" in text:
            return "rush"
        return "other"

    if "dunk" in text:
        return "dunk"
    if "3pt" in text or "three point" in text or "three-pointer" in text:
        return "three_pointer"
    if "block" in text:
        return "block"
    if "steal" in text:
        return "steal"
    if "turnover" in text:
        return "turnover"
    if "free throw" in text:
        return "free_throw"
    if "assist" in text:
        return "assist"
    if "jump shot" in text or "layup" in text or "makes" in text:
        return "shot"
    return "other"


def extract_summary_plays(summary: dict, sport: str, limit: int = 200) -> list[dict]:
    raw_plays: list[dict] = []
    raw_plays.extend(summary.get("plays") or [])
    for drive in (summary.get("drives") or {}).get("previous", []):
        raw_plays.extend(drive.get("plays") or [])

    plays = []
    for index, play in enumerate(raw_plays[:limit]):
        description = str(play.get("text") or play.get("description") or "").strip()
        if not description:
            continue
        period_data = play.get("period") or {}
        clock_data = play.get("clock") or {}
        plays.append({
            "id": index + 1,
            "period": period_data.get("number", 1) if isinstance(period_data, dict) else 1,
            "clock": clock_data.get("displayValue", "") if isinstance(clock_data, dict) else "",
            "play_type": classify_play_description(description, sport),
            "description": description[:500],
            "home_score": _score_value(play.get("homeScore")),
            "away_score": _score_value(play.get("awayScore")),
            "player": None,
        })
    return plays


def extract_summary_highlights(summary: dict, sport: str) -> list[dict]:
    highlight_types = {
        "dunk", "three_pointer", "block", "steal", "touchdown",
        "interception", "sack", "field_goal", "turnover",
    }
    highlights = []
    for index, play in enumerate(extract_summary_plays(summary, sport, limit=200)):
        if play["play_type"] in highlight_types:
            highlights.append({
                "timestamp": float(index * 35),
                "play_type": play["play_type"],
                "confidence": 0.72,
            })
    return highlights[:16]


def extract_summary_leaders(summary: dict) -> list[dict]:
    """Top statistical performers per team from a game summary."""
    rows = []
    for team_block in summary.get("leaders") or []:
        team = ((team_block.get("team") or {}).get("abbreviation")
                or (team_block.get("team") or {}).get("displayName") or "")
        for category in team_block.get("leaders") or []:
            label = category.get("displayName") or category.get("name") or ""
            for leader in (category.get("leaders") or [])[:1]:
                athlete = (leader.get("athlete") or {}).get("displayName")
                value = leader.get("displayValue")
                if athlete and value:
                    rows.append({
                        "team": team,
                        "category": label,
                        "player": athlete,
                        "stat_line": value,
                    })
    return rows


def extract_summary_videos(summary: dict) -> list[dict]:
    """Real highlight video clips (MP4 on ESPN's CDN) attached to a game summary."""
    clips = []
    for video in summary.get("videos") or []:
        links = video.get("links") or {}
        source = links.get("source") or {}
        # HLS first: ESPN's direct MP4 variants 500 on Akamai, while the HLS
        # playlists stream publicly with permissive CORS.
        href = (
            (source.get("HLS") or {}).get("href")
            or (source.get("HD") or {}).get("href")
            or source.get("href")
            or ((links.get("mobile") or {}).get("source") or {}).get("href")
        )
        if not href:
            continue
        clips.append({
            "id": str(video.get("id") or len(clips) + 1),
            "headline": video.get("headline") or "",
            "description": video.get("description") or "",
            "duration": int(video.get("duration") or 0),
            "url": href,
            "thumbnail": video.get("thumbnail") or "",
        })
    return clips


def fetch_espn_athletes(sport: str, limit: int = 80) -> list[dict]:
    keys = get_league_keys(sport)
    sport_key = sport.upper()
    try:
        data = _get_json(
            f"{ESPN_WEB_BASE}/{keys['sport']}/{keys['league']}/statistics/byathlete",
            {"limit": limit},
        )
    except Exception:
        return []
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
    return athletes
