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
ESPN_CORE_BASE = "https://sports.core.api.espn.com/v2/sports"

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


def fetch_espn_team_schedule(sport: str, team_id: str | int, limit: int = 24) -> list[dict]:
    """A single team's games from ESPN's team-schedule endpoint.

    The league-wide recent-games window only surfaces teams that played in the
    last day or two, so a fan's team can be missing entirely (e.g. eliminated
    from the playoffs). Pulling the team's own schedule guarantees their recent
    games are available for reels, broadcasts and newsletters.

    Schedule events differ from scoreboard events: status lives on the
    competition and scores are {value, displayValue} objects, so this parses
    them directly rather than reusing `_event_to_game`.
    """
    keys = get_league_keys(sport)
    url = f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/teams/{team_id}/schedule"
    year = _current_season_year(sport)
    games_by_id: dict[int, dict] = {}

    def _sched_score(competitor: dict):
        score = competitor.get("score")
        if isinstance(score, dict):
            score = score.get("value")
        return _score_value(score)

    def _load(params: Optional[dict]) -> None:
        try:
            data = _get_json(url, params)
        except Exception:
            return
        for event in data.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            event_id = str(event.get("id") or "")
            if not home or not away or not event_id or int(event_id) in games_by_id:
                continue
            home_team = _team_from_competitor(home, sport)
            away_team = _team_from_competitor(away, sport)
            games_by_id[int(event_id)] = {
                "id": int(event_id),
                "external_id": event_id,
                "sport": sport.upper(),
                "status": _status_from_event({"status": competition.get("status") or event.get("status")}),
                "game_date": _parse_espn_datetime(event.get("date")),
                "home_team": {"id": home_team["id"], "name": home_team["name"], "abbreviation": home_team["abbreviation"]},
                "away_team": {"id": away_team["id"], "name": away_team["name"], "abbreviation": away_team["abbreviation"]},
                "home_score": _sched_score(home),
                "away_score": _sched_score(away),
                "video_url": None,
            }

    # Default view = current postseason for playoff teams; the explicit regular
    # season query always returns games (including teams that missed the
    # playoffs and so have an empty default view, e.g. Golden State).
    _load(None)
    _load({"season": year, "seasontype": 2})
    if not any(g.get("status") in ("final", "live") for g in games_by_id.values()):
        # Deep offseason before the new season is populated — use last season.
        _load({"season": year - 1, "seasontype": 3})
        _load({"season": year - 1, "seasontype": 2})

    games = sorted(games_by_id.values(), key=lambda g: g.get("game_date") or "", reverse=True)
    return games[:limit]


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


_NBA_STAT_LINE = [
    ("avgPoints", "PPG"), ("avgRebounds", "RPG"), ("avgAssists", "APG"),
    ("avgSteals", "SPG"), ("avgBlocks", "BPG"), ("gamesPlayed", "GP"),
]

# Position-specific NFL stat lines — shown for the player's actual position
_NFL_STAT_LINE_QB = [
    ("passingYards", "Pass Yds"), ("passingTouchdowns", "Pass TD"),
    ("completionPct", "Comp%"), ("rushingYards", "Rush Yds"), ("interceptions", "INT"),
]
_NFL_STAT_LINE_RB = [
    ("rushingYards", "Rush Yds"), ("rushingTouchdowns", "Rush TD"),
    ("rushingYardsPerCarry", "Yds/Car"), ("receptions", "Rec"), ("receivingYards", "Rec Yds"),
]
_NFL_STAT_LINE_WR_TE = [
    ("receptions", "Rec"), ("receivingYards", "Rec Yds"), ("receivingTouchdowns", "Rec TD"),
    ("receivingYardsPerReception", "Yds/Rec"), ("targets", "Tgts"),
]
_NFL_STAT_LINE_DL_LB = [
    ("totalTackles", "Tackles"), ("sacks", "Sacks"), ("tacklesForLoss", "TFL"),
    ("quarterbackHits", "QB Hits"), ("interceptions", "INT"),
]
_NFL_STAT_LINE_DB = [
    ("interceptions", "INT"), ("passesDefended", "PD"), ("totalTackles", "Tackles"),
    ("sacks", "Sacks"), ("forcedFumbles", "FF"),
]
_NFL_STAT_LINE_GENERIC = [
    ("passingYards", "Pass Yds"), ("passingTouchdowns", "Pass TD"),
    ("rushingYards", "Rush Yds"), ("rushingTouchdowns", "Rush TD"),
    ("receivingYards", "Rec Yds"), ("receivingTouchdowns", "Rec TD"),
    ("totalTackles", "Tackles"), ("sacks", "Sacks"), ("interceptions", "INT"),
]

TEAM_STAR_PRIORITY = {
    "NBA": {
        "BOS": ["Jayson Tatum", "Jaylen Brown", "Derrick White", "Payton Pritchard", "Sam Hauser"],
        "LAL": ["LeBron James", "Luka Doncic", "Austin Reaves", "Rui Hachimura"],
        "GS": ["Stephen Curry", "Jimmy Butler III", "Draymond Green", "Brandin Podziemski"],
        "NY": ["Jalen Brunson", "Karl-Anthony Towns", "OG Anunoby", "Mikal Bridges", "Josh Hart"],
        "OKC": ["Shai Gilgeous-Alexander", "Jalen Williams", "Chet Holmgren", "Luguentz Dort"],
        "DEN": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Michael Porter Jr."],
        "MIN": ["Anthony Edwards", "Julius Randle", "Rudy Gobert", "Jaden McDaniels"],
        "MIL": ["Giannis Antetokounmpo", "Damian Lillard", "Khris Middleton", "Brook Lopez"],
        "DAL": ["Anthony Davis", "Kyrie Irving", "Klay Thompson", "Dereck Lively II"],
        "PHX": ["Devin Booker", "Kevin Durant", "Bradley Beal"],
        "CLE": ["Donovan Mitchell", "Evan Mobley", "Darius Garland", "Jarrett Allen"],
        "PHI": ["Joel Embiid", "Tyrese Maxey", "Paul George", "Jared McCain"],
        "MIA": ["Bam Adebayo", "Tyler Herro", "Andrew Wiggins"],
        "LAC": ["Kawhi Leonard", "James Harden", "Ivica Zubac"],
        "SAS": ["Victor Wembanyama", "De'Aaron Fox", "Devin Vassell", "Stephon Castle"],
        "ORL": ["Paolo Banchero", "Franz Wagner", "Jalen Suggs"],
        "HOU": ["Alperen Sengun", "Jalen Green", "Amen Thompson", "Jabari Smith Jr."],
        "MEM": ["Ja Morant", "Jaren Jackson Jr.", "Desmond Bane"],
        "IND": ["Tyrese Haliburton", "Pascal Siakam", "Bennedict Mathurin", "Myles Turner"],
        "NO": ["Zion Williamson", "Trey Murphy III", "CJ McCollum", "Herbert Jones"],
        "ATL": ["Trae Young", "Jalen Johnson", "Dyson Daniels", "De'Andre Hunter"],
        "TOR": ["Scottie Barnes", "Brandon Ingram", "RJ Barrett", "Immanuel Quickley"],
        "CHA": ["LaMelo Ball", "Brandon Miller", "Miles Bridges", "Mark Williams"],
        "DET": ["Cade Cunningham", "Jalen Duren", "Ausar Thompson", "Jaden Ivey"],
        "CHI": ["Coby White", "Josh Giddey", "Nikola Vucevic", "Matas Buzelis"],
        "SAC": ["Domantas Sabonis", "Zach LaVine", "DeMar DeRozan", "Keegan Murray"],
        "POR": ["Scoot Henderson", "Shaedon Sharpe", "Deni Avdija", "Jerami Grant"],
        "UTAH": ["Lauri Markkanen", "Keyonte George", "Walker Kessler", "Collin Sexton"],
        "WSH": ["Bilal Coulibaly", "Alex Sarr", "Jordan Poole", "Corey Kispert"],
        "BKN": ["Cam Thomas", "Nic Claxton", "Cameron Johnson"],
    },
    "NFL": {
        "BUF": ["Josh Allen", "James Cook III", "Keon Coleman", "Khalil Shakir", "Dalton Kincaid"],
        "KC": ["Patrick Mahomes", "Travis Kelce", "Rashee Rice", "Chris Jones", "Xavier Worthy"],
        "BAL": ["Lamar Jackson", "Derrick Henry", "Zay Flowers", "Mark Andrews", "Roquan Smith"],
        "CIN": ["Joe Burrow", "Ja'Marr Chase", "Tee Higgins", "Trey Hendrickson"],
        "DET": ["Jared Goff", "Jahmyr Gibbs", "Amon-Ra St. Brown", "Sam LaPorta", "Aidan Hutchinson"],
        "PHI": ["Jalen Hurts", "Saquon Barkley", "A.J. Brown", "DeVonta Smith", "Jalen Carter"],
        "SF": ["Brock Purdy", "Christian McCaffrey", "George Kittle", "Deebo Samuel", "Nick Bosa"],
        "DAL": ["Dak Prescott", "CeeDee Lamb", "Micah Parsons", "George Pickens"],
        "CHI": ["Caleb Williams", "DJ Moore", "Rome Odunze", "Cole Kmet", "D'Andre Swift"],
        "CAR": ["Bryce Young", "Chuba Hubbard", "Tetairoa McMillan", "Xavier Legette", "Jaycee Horn"],
        "HOU": ["C.J. Stroud", "Nico Collins", "Joe Mixon", "Will Anderson Jr.", "Danielle Hunter"],
        "LAC": ["Justin Herbert", "Ladd McConkey", "Keenan Allen", "Derwin James Jr."],
        "LAR": ["Matthew Stafford", "Puka Nacua", "Davante Adams", "Kyren Williams", "Jared Verse"],
        "GB": ["Jordan Love", "Josh Jacobs", "Romeo Doubs", "Christian Watson", "Rashan Gary"],
        "MIN": ["Justin Jefferson", "Jordan Addison", "T.J. Hockenson", "J.J. McCarthy"],
        "MIA": ["Tua Tagovailoa", "Tyreek Hill", "Jaylen Waddle", "De'Von Achane", "Jalen Ramsey"],
        "NYJ": ["Garrett Wilson", "Breece Hall", "Sauce Gardner", "Quinnen Williams"],
        "NYG": ["Malik Nabers", "Dexter Lawrence II", "Brian Burns", "Tyrone Tracy Jr."],
        "WAS": ["Jayden Daniels", "Terry McLaurin", "Deebo Samuel", "Zach Ertz"],
        "ATL": ["Michael Penix Jr.", "Bijan Robinson", "Drake London", "Kyle Pitts"],
        "TB": ["Baker Mayfield", "Mike Evans", "Bucky Irving", "Antoine Winfield Jr."],
        "SEA": ["Sam Darnold", "Jaxon Smith-Njigba", "Kenneth Walker III", "Devon Witherspoon"],
        "DEN": ["Bo Nix", "Courtland Sutton", "Pat Surtain II", "Nik Bonitto"],
        "PIT": ["T.J. Watt", "DK Metcalf", "George Pickens", "Najee Harris"],
        "LV": ["Brock Bowers", "Ashton Jeanty", "Maxx Crosby", "Jakobi Meyers"],
        "IND": ["Anthony Richardson", "Jonathan Taylor", "Michael Pittman Jr.", "DeForest Buckner"],
        "JAX": ["Trevor Lawrence", "Brian Thomas Jr.", "Travis Etienne Jr.", "Josh Hines-Allen"],
        "TEN": ["Cam Ward", "Tony Pollard", "Calvin Ridley", "Jeffery Simmons"],
        "NO": ["Chris Olave", "Alvin Kamara", "Tyrann Mathieu", "Demario Davis"],
        "CLE": ["Myles Garrett", "Jerry Jeudy", "David Njoku", "Denzel Ward"],
        "NE": ["Drake Maye", "Stefon Diggs", "Rhamondre Stevenson", "Christian Gonzalez"],
        "ARI": ["Kyler Murray", "Marvin Harrison Jr.", "Trey McBride", "Budda Baker"],
    },
}


def _flatten_athlete_stats(item: dict, names_by_cat: dict[str, list[str]] | None = None) -> dict[str, float]:
    categories = item.get("categories", [])
    names_by_cat = names_by_cat or {cat.get("name"): cat.get("names", []) for cat in categories}
    flat: dict[str, float] = {}
    for cat in categories:
        for name, value in zip(names_by_cat.get(cat.get("name"), []), cat.get("values", [])):
            if isinstance(value, (int, float)):
                flat[name] = value
    return flat


def _athlete_team_abbr(athlete: dict) -> str:
    return (
        athlete.get("teamShortName")
        or ((athlete.get("teams") or [{}])[0].get("abbreviation"))
        or ((athlete.get("team") or {}).get("abbreviation"))
        or ""
    ).upper()


def _star_score(sport: str, player: dict, flat: dict[str, float] | None = None) -> float:
    """Rank likely fan-facing stars instead of raw roster order.

    ESPN's public roster endpoint is not consistently sorted, especially during
    off-season roster churn. The leaderboard payload is better, but raw stat
    sums overvalue games played or one-volume category. This score keeps the
    ordering aligned with what fans expect to pick.
    """
    flat = flat or {}
    position = str(player.get("position") or "").upper()
    if sport.upper() == "NBA":
        return (
            float(flat.get("avgPoints", 0)) * 5.0
            + float(flat.get("avgAssists", 0)) * 3.0
            + float(flat.get("avgRebounds", 0)) * 2.2
            + float(flat.get("avgSteals", 0)) * 6.0
            + float(flat.get("avgBlocks", 0)) * 5.0
            + min(float(flat.get("gamesPlayed", 0)), 82) * 0.15
        )

    offense = (
        float(flat.get("passingYards", 0)) * 0.018
        + float(flat.get("passingTouchdowns", 0)) * 5.5
        + float(flat.get("rushingYards", 0)) * 0.075
        + float(flat.get("rushingTouchdowns", 0)) * 7.0
        + float(flat.get("receivingYards", 0)) * 0.075
        + float(flat.get("receivingTouchdowns", 0)) * 7.0
    )
    defense = (
        float(flat.get("totalTackles", 0)) * 1.1
        + float(flat.get("sacks", 0)) * 10.0
        + float(flat.get("interceptions", 0)) * 12.0
    )
    position_weight = {
        "QB": 36.0,
        "RB": 20.0,
        "WR": 18.0,
        "TE": 14.0,
        "DE": 10.0,
        "EDGE": 10.0,
        "LB": 9.0,
        "CB": 8.0,
        "S": 7.0,
        "FS": 7.0,
        "SS": 7.0,
    }.get(position, 0.0)
    return offense + defense + position_weight


def _fetch_byathlete_pages(sport: str, max_pages: int = 12) -> tuple[list[dict], dict[str, list[str]]]:
    keys = get_league_keys(sport)
    items: list[dict] = []
    names_by_cat: dict[str, list[str]] = {}
    page = 1
    total_pages = 1
    while page <= min(total_pages, max_pages):
        data = _get_json(
            f"{ESPN_WEB_BASE}/{keys['sport']}/{keys['league']}/statistics/byathlete",
            {"limit": 25, "page": page},
        )
        if not names_by_cat:
            names_by_cat = {c.get("name"): c.get("names", []) for c in data.get("categories", [])}
        items.extend(data.get("athletes", []))
        total_pages = int((data.get("pagination") or {}).get("pages") or total_pages)
        page += 1
    return items, names_by_cat


def _fallback_roster_score(sport: str, player: dict, position_seen: dict[str, int], index: int) -> float:
    position = str(player.get("position") or "").upper()
    ordinal = position_seen.get(position, 0)
    position_seen[position] = ordinal + 1

    if sport.upper() == "NBA":
        # ESPN's NBA roster page is usually already star-skewed. Keep that
        # order as the main fallback signal.
        return 1000 - index

    base = {
        "QB": 100,
        "RB": 88,
        "WR": 84,
        "TE": 78,
        "DE": 72,
        "EDGE": 72,
        "LB": 70,
        "CB": 68,
        "S": 66,
        "FS": 66,
        "SS": 66,
        "K": 45,
    }.get(position, 50)
    duplicate_penalty = {
        "QB": 95,
        "RB": 18,
        "WR": 12,
        "TE": 14,
        "K": 40,
    }.get(position, 6)
    return base - ordinal * duplicate_penalty - index * 0.01


def _presentation_players(sport: str, team_abbr: str, ranked: list[dict], limit: int) -> list[dict]:
    priority = {
        name.lower(): index
        for index, name in enumerate(TEAM_STAR_PRIORITY.get(sport.upper(), {}).get(team_abbr.upper(), []))
    }
    ordered = sorted(
        ranked,
        key=lambda p: (
            priority.get(str(p.get("name") or "").lower(), 999),
            -p.get("_score", 0),
            str(p.get("name") or ""),
        ),
    )
    cleaned = []
    qb_seen = False
    for player in ordered:
        position = str(player.get("position") or "").upper()
        name = str(player.get("name") or "")
        if sport.upper() == "NFL" and position == "QB":
            if qb_seen and name.lower() not in priority:
                continue
            qb_seen = True
        if player.get("id") in {p.get("id") for p in cleaned}:
            continue
        player = dict(player)
        player.pop("_score", None)
        cleaned.append(player)
        if len(cleaned) >= limit:
            break
    return cleaned


# Broader, sport-agnostic fallback labels so a player who is found but whose
# production sits outside the curated stat line still shows real averages
# instead of "not published".
_FALLBACK_STAT_LABELS: dict[str, str] = {
    "avgPoints": "PPG", "avgRebounds": "RPG", "avgAssists": "APG", "avgSteals": "SPG",
    "avgBlocks": "BPG", "avgMinutes": "MPG", "points": "PTS", "rebounds": "REB", "assists": "AST",
    "passingYards": "Pass Yds", "passingTouchdowns": "Pass TD", "rushingYards": "Rush Yds",
    "rushingTouchdowns": "Rush TD", "receivingYards": "Rec Yds", "receivingTouchdowns": "Rec TD",
    "receptions": "Rec", "totalTackles": "Tackles", "sacks": "Sacks", "interceptions": "INT",
    "fieldGoalsMade": "FGM", "completions": "Comp", "gamesPlayed": "GP",
}


def _fallback_line(flat: dict[str, float]) -> list[dict]:
    """Up to 5 of a player's most meaningful numeric stats, for athletes who fall
    outside the curated per-sport stat line."""
    line = []
    for key, label in _FALLBACK_STAT_LABELS.items():
        value = flat.get(key)
        if value:
            line.append({"label": label, "value": round(value, 1) if isinstance(value, float) else value})
        if len(line) >= 5:
            break
    return line


def _nfl_line_from_flat(flat: dict[str, float]) -> list[dict]:
    """Position-appropriate NFL stat line inferred from the stats themselves.

    Used for athletes resolved via the per-athlete endpoint, where the position
    label isn't on hand. Picking a spec from the dominant production avoids
    noise like a "1 tackle" stat showing up on a running back's line.
    """
    passing = flat.get("passingYards") or 0
    rushing = flat.get("rushingYards") or 0
    receiving = flat.get("receivingYards") or 0
    defense = (flat.get("totalTackles") or 0) + (flat.get("sacks") or 0)
    if passing >= 200:
        spec = _NFL_STAT_LINE_QB
    elif receiving and receiving >= rushing:
        spec = _NFL_STAT_LINE_WR_TE
    elif rushing:
        spec = _NFL_STAT_LINE_RB
    elif defense:
        spec = _NFL_STAT_LINE_DL_LB
    else:
        spec = _NFL_STAT_LINE_GENERIC
    line = []
    for name, label in spec:
        value = flat.get(name)
        if value:
            line.append({"label": label, "value": round(value, 1) if isinstance(value, float) else value})
    return line or _fallback_line(flat)


def _current_season_year(sport: str) -> int:
    """Season year ESPN tags the current season with (NFL by start year, NBA by
    end year)."""
    today = date_cls.today()
    if sport.upper() == "NFL":
        return today.year if today.month >= 8 else today.year - 1
    return today.year + 1 if today.month >= 9 else today.year


def _fetch_athlete_stats_direct(sport: str, athlete_id: int) -> dict[str, float]:
    """Direct per-athlete season stats from ESPN's core API.

    The older site-API summary endpoint 404s for most non-QB athletes, which is
    why league-wide NFL stats used to come back empty for every position except
    quarterback. The core API resolves cleanly across all positions.
    """
    keys = get_league_keys(sport)
    year = _current_season_year(sport)
    for season in (year, year - 1):  # tolerate the season boundary
        try:
            data = _get_json(
                f"{ESPN_CORE_BASE}/{keys['sport']}/leagues/{keys['league']}"
                f"/seasons/{season}/types/2/athletes/{athlete_id}/statistics",
            )
        except Exception:
            continue
        cats = (data.get("splits") or {}).get("categories") or []
        flat: dict[str, float] = {}
        for cat in cats:
            for stat in cat.get("stats", []):
                name = stat.get("name")
                value = stat.get("value")
                if name and isinstance(value, (int, float)) and value:
                    flat[name] = float(value)
        if flat:
            return flat
    return {}


def fetch_espn_athlete_stats(sport: str, ids: list[int]) -> dict[int, dict]:
    """Season stat lines for specific athletes. Returns {athlete_id: {id, name, line: [{label, value}]}}."""
    sport_key = sport.upper()
    want = {int(i) for i in ids}
    if not want:
        return {}
    try:
        athletes, names_by_cat = _fetch_byathlete_pages(sport_key, max_pages=40)
    except Exception:
        athletes, names_by_cat = [], {}

    spec = _NBA_STAT_LINE if sport_key == "NBA" else None
    out: dict[int, dict] = {}
    found: set[int] = set()

    for item in athletes:
        athlete = item.get("athlete", {})
        aid = athlete.get("id")
        if not aid or int(aid) not in want:
            continue
        flat = _flatten_athlete_stats(item, names_by_cat)
        if sport_key == "NFL":
            position = str((athlete.get("position") or {}).get("abbreviation") or "").upper()
            if position == "QB":
                stat_spec = _NFL_STAT_LINE_QB
            elif position in ("RB", "FB"):
                stat_spec = _NFL_STAT_LINE_RB
            elif position in ("WR", "TE"):
                stat_spec = _NFL_STAT_LINE_WR_TE
            elif position in ("DE", "DT", "NT", "EDGE", "LB", "MLB", "OLB", "ILB"):
                stat_spec = _NFL_STAT_LINE_DL_LB
            elif position in ("CB", "S", "FS", "SS", "DB"):
                stat_spec = _NFL_STAT_LINE_DB
            else:
                stat_spec = _NFL_STAT_LINE_GENERIC
        else:
            stat_spec = spec
        line = []
        for name, label in stat_spec:
            value = flat.get(name)
            if value:
                line.append({"label": label, "value": round(value, 1) if isinstance(value, float) else value})
        if not line:
            line = _fallback_line(flat)
        aid_int = int(aid)
        found.add(aid_int)
        out[aid_int] = {
            "id": aid_int,
            "name": athlete.get("displayName"),
            "team": athlete.get("teamShortName") or ((athlete.get("teams") or [{}])[0].get("abbreviation")),
            "line": line[:5],
        }

    # Fallback: directly fetch stats for any player the leaderboard scan missed.
    # For NFL that is every non-QB (the leaderboard is passing-only), so these
    # are fetched in parallel — a serial loop would make an all-positions stats
    # view crawl.
    missing = list(want - found)
    if missing:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = pool.map(lambda aid: (aid, _fetch_athlete_stats_direct(sport_key, aid)), missing)
        for athlete_id, flat in results:
            if not flat:
                continue
            if sport_key == "NBA":
                line = []
                for name, label in _NBA_STAT_LINE:
                    value = flat.get(name)
                    if value:
                        line.append({"label": label, "value": round(value, 1) if isinstance(value, float) else value})
                if not line:
                    line = _fallback_line(flat)
            else:
                line = _nfl_line_from_flat(flat)
            if line:
                out[athlete_id] = {"id": athlete_id, "name": None, "team": None, "line": line[:5]}

    return out


def fetch_espn_team_stars(sport: str, team_id: str | int, limit: int = 10) -> list[dict]:
    """Top fan-facing players for a team.

    Prefer ESPN's by-athlete leaderboard filtered to the team abbreviation. It
    is usually more reliable than the roster page for "who are the stars?".
    Fill with roster players only if the leaderboard lacks depth.
    """
    keys = get_league_keys(sport)
    sport_key = sport.upper()
    roster = fetch_espn_team_roster(sport_key, team_id, limit=80)
    team_abbr = (roster[0].get("team") if roster else "") or ""
    team_name = (roster[0].get("team_name") if roster else "") or ""
    by_id = {p["id"]: p for p in roster}
    stars: list[dict] = []
    seen: set[int] = set()

    if team_abbr:
        try:
            athletes, names_by_cat = _fetch_byathlete_pages(sport_key)
            for item in athletes:
                athlete = item.get("athlete") or {}
                aid = athlete.get("id")
                if not aid or _athlete_team_abbr(athlete) != team_abbr.upper():
                    continue
                position = athlete.get("position") or {}
                flat = _flatten_athlete_stats(item, names_by_cat)
                player = {
                    "id": int(aid),
                    "name": athlete.get("displayName") or athlete.get("fullName"),
                    "position": position.get("abbreviation") or position.get("name"),
                    "jersey": athlete.get("jersey"),
                    "team": team_abbr,
                    "team_name": team_name,
                    "sport": sport_key,
                    "headshot": (athlete.get("headshot") or {}).get("href"),
                    "_score": _star_score(sport_key, {
                        "position": position.get("abbreviation") or position.get("name"),
                    }, flat),
                }
                if not player["name"]:
                    continue
                roster_player = by_id.get(player["id"])
                if roster_player:
                    player = {**roster_player, **{k: v for k, v in player.items() if v}}
                stars.append(player)
        except Exception:
            pass

    for player in sorted(stars, key=lambda p: p.get("_score", 0), reverse=True):
        seen.add(player["id"])
    ranked = sorted(stars, key=lambda p: p.get("_score", 0), reverse=True)

    position_seen: dict[str, int] = {}
    for index, player in enumerate(roster):
        if player["id"] in seen:
            continue
        player = {**player, "_score": _fallback_roster_score(sport_key, player, position_seen, index)}
        if sport_key == "NBA":
            # Injured or off-cycle stars can disappear from ESPN's by-athlete
            # leaderboard while still being the players fans expect to follow.
            player["_score"] += 250
        ranked.append(player)
        seen.add(player["id"])

    if sport_key == "NFL":
        ranked.sort(key=lambda p: p.get("_score", 0), reverse=True)
    elif roster:
        roster_order = {player["id"]: index for index, player in enumerate(roster)}
        ranked.sort(key=lambda p: (-p.get("_score", 0), roster_order.get(p["id"], 999)))

    if len(ranked) < limit:
        for index, player in enumerate(roster):
            if player["id"] in seen:
                continue
            player = {**player, "_score": _fallback_roster_score(sport_key, player, position_seen, index)}
            ranked.append(player)
            seen.add(player["id"])

    return _presentation_players(sport_key, team_abbr, ranked, limit)


def fetch_espn_team_roster(sport: str, team_id: str | int, limit: int = 60) -> list[dict]:
    """Real ESPN roster for a single team so the demo can offer player follows
    grouped by the teams a fan picked."""
    keys = get_league_keys(sport)
    sport_key = sport.upper()
    try:
        data = _get_json(
            f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/teams/{team_id}/roster"
        )
    except Exception:
        return []

    team_block = data.get("team") or {}
    team_abbr = team_block.get("abbreviation")
    team_name = team_block.get("displayName") or team_block.get("name")

    # NBA returns a flat athletes list; NFL groups athletes by position bucket.
    raw_groups = data.get("athletes") or []
    athletes_raw: list[dict] = []
    for group in raw_groups:
        if isinstance(group, dict) and "items" in group:
            athletes_raw.extend(group.get("items") or [])
        else:
            athletes_raw.append(group)

    players = []
    for athlete in athletes_raw:
        if not athlete.get("id"):
            continue
        position = (athlete.get("position") or {})
        players.append({
            "id": int(athlete.get("id")),
            "name": athlete.get("displayName") or athlete.get("fullName"),
            "position": position.get("abbreviation") or position.get("name"),
            "jersey": athlete.get("jersey"),
            "team": team_abbr,
            "team_name": team_name,
            "sport": sport_key,
            "headshot": (athlete.get("headshot") or {}).get("href"),
        })
        if len(players) >= limit:
            break

    # Keep roster fallback roughly star-biased when no leaderboard is available.
    try:
        stats = fetch_espn_athlete_stats(sport_key, [p["id"] for p in players])
        def _star(p: dict) -> float:
            flat = {
                {
                    "PPG": "avgPoints",
                    "RPG": "avgRebounds",
                    "APG": "avgAssists",
                    "SPG": "avgSteals",
                    "BPG": "avgBlocks",
                    "GP": "gamesPlayed",
                    "Pass Yds": "passingYards",
                    "Pass TD": "passingTouchdowns",
                    "Rush Yds": "rushingYards",
                    "Rush TD": "rushingTouchdowns",
                    "Rec Yds": "receivingYards",
                    "Rec TD": "receivingTouchdowns",
                    "Tackles": "totalTackles",
                    "Sacks": "sacks",
                    "INT": "interceptions",
                }.get(s.get("label"), ""): s.get("value")
                for s in stats.get(p["id"], {}).get("line", [])
                if isinstance(s.get("value"), (int, float))
            }
            flat.pop("", None)
            return _star_score(sport_key, p, flat)
        players.sort(key=_star, reverse=True)
    except Exception:
        pass
    return players


def fetch_espn_news(sport: str | None = None, limit: int = 12) -> list[dict]:
    """Tailored headline feed straight from ESPN's public news endpoint."""
    sports = [sport.upper()] if sport else ["NBA", "NFL"]
    articles = []
    for sport_key in sports:
        keys = get_league_keys(sport_key)
        try:
            data = _get_json(
                f"{ESPN_SITE_BASE}/{keys['sport']}/{keys['league']}/news",
                {"limit": limit},
            )
        except Exception:
            continue
        for item in data.get("articles", []):
            images = item.get("images") or []
            web_links = (item.get("links") or {}).get("web") or {}
            articles.append({
                "id": str(item.get("id") or item.get("guid") or len(articles) + 1),
                "headline": item.get("headline") or item.get("title") or "",
                "description": item.get("description") or "",
                "published": item.get("published"),
                "sport": sport_key,
                "image": (images[0].get("url") if images else None),
                "link": web_links.get("href"),
                "type": item.get("type") or "story",
            })
    articles.sort(key=lambda a: a.get("published") or "", reverse=True)
    return articles[:limit if sport else limit * 2]


# ESPN's by-athlete leaderboard is single-category. The default (and the
# "offense" category) is the passing leaderboard, so *every* NFL result is a QB.
# Pulling and merging these categories surfaces every position group:
#   offense → QB · scoring → RB/WR/TE · defense → DE/DT/LB/CB/S
_NFL_LEADERBOARD_CATEGORIES = ("offense", "scoring", "defense")
_NFL_POSITION_WEIGHT = {
    "QB": 34.0, "RB": 26.0, "WR": 24.0, "TE": 18.0,
    "DE": 16.0, "EDGE": 16.0, "DT": 14.0, "NT": 13.0,
    "LB": 15.0, "MLB": 15.0, "OLB": 15.0, "ILB": 15.0,
    "CB": 13.0, "S": 12.0, "FS": 12.0, "SS": 12.0, "DB": 12.0,
    "K": 6.0, "P": 4.0,
}


def _athlete_leaderboard_value(item: dict) -> float:
    """Headline numeric value for an athlete on a by-athlete leaderboard."""
    values = [
        v
        for category in item.get("categories", [])
        for v in category.get("values", [])
        if isinstance(v, (int, float))
    ]
    if not values:
        return 0.0
    return sum(values[:6]) / max(1, min(len(values), 6))


def _athlete_card(item: dict, sport_key: str, impact: float) -> dict | None:
    athlete = item.get("athlete", {})
    raw_id = athlete.get("id")
    if not raw_id:
        return None
    return {
        "id": int(raw_id),
        "name": athlete.get("displayName"),
        "position": (athlete.get("position") or {}).get("abbreviation"),
        "team": athlete.get("teamShortName") or ((athlete.get("teams") or [{}])[0].get("abbreviation")),
        "sport": sport_key,
        "impact_score": round(impact, 1),
        "headshot": (athlete.get("headshot") or {}).get("href"),
    }


def _fetch_nfl_athletes_all_positions(limit: int) -> list[dict]:
    """Position-diverse NFL athlete pool merged from several stat leaderboards."""
    keys = get_league_keys("NFL")
    base_url = f"{ESPN_WEB_BASE}/{keys['sport']}/{keys['league']}/statistics/byathlete"
    athletes: list[dict] = []
    seen: set[int] = set()
    for category in _NFL_LEADERBOARD_CATEGORIES:
        try:
            data = _get_json(base_url, {"limit": 50, "category": category})
        except Exception:
            continue
        items = data.get("athletes", [])
        # Normalise each leaderboard to 0..100 so positions ranked by different
        # stats (tackles vs touchdowns vs passing yards) compare fairly; a
        # position weight then keeps the cross-position ordering fan-sensible.
        raw = [_athlete_leaderboard_value(it) for it in items]
        top = max(raw) if raw else 0.0
        for item, value in zip(items, raw):
            card = _athlete_card(item, "NFL", 0.0)
            if not card or card["id"] in seen:
                continue
            seen.add(card["id"])
            norm = (value / top * 100.0) if top else 0.0
            weight = _NFL_POSITION_WEIGHT.get(str(card["position"] or "").upper(), 8.0)
            card["impact_score"] = round(norm + weight, 1)
            athletes.append(card)
    athletes.sort(key=lambda p: p.get("impact_score") or 0, reverse=True)
    return athletes[:limit] if limit else athletes


def fetch_espn_athletes(sport: str, limit: int = 80) -> list[dict]:
    sport_key = sport.upper()
    if sport_key == "NFL":
        nfl = _fetch_nfl_athletes_all_positions(limit)
        if nfl:
            return nfl
        # Fall through to the single-leaderboard path if the category fetch fails.
    keys = get_league_keys(sport)
    try:
        data = _get_json(
            f"{ESPN_WEB_BASE}/{keys['sport']}/{keys['league']}/statistics/byathlete",
            {"limit": limit},
        )
    except Exception:
        return []
    athletes = []
    for index, item in enumerate(data.get("athletes", [])):
        value = _athlete_leaderboard_value(item)
        impact = round(value, 1) if value else round(80 - index * 0.5, 1)
        card = _athlete_card(item, sport_key, impact)
        if card:
            athletes.append(card)
    return athletes
