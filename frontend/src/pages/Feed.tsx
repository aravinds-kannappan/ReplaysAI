import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueries } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import axios from "axios";
import {
  useFeed, useUpcomingGames, useNews, useRosterPlayers,
  useCreatePrediction, usePredictions, useSaveRoster, useRosters, usePlayerStats,
  useRankings, useLeaderboard, useMyRank, type Standing,
} from "../hooks/usePredictions";
import { useCurrentUser, type FollowedPlayer, type FavoriteTeam } from "../hooks/useUser";
import { useGames } from "../hooks/useGames";
import ScoreCard from "../components/ScoreCard";
import { apiPath } from "../lib/api";
import { getDeviceId } from "../lib/device";
import type { Game } from "../types";

type League = "NBA" | "NFL";
type Tab = "dashboard" | "season" | "stats" | "extras";

const TABS: { id: Tab; label: string; path: string }[] = [
  { id: "dashboard", label: "Dashboard", path: "/feed" },
  { id: "season", label: "Season", path: "/season" },
  { id: "stats", label: "Stats", path: "/stats" },
  { id: "extras", label: "Extras", path: "/extras" },
];
const PATH_TO_TAB: Record<string, Tab> = {
  "/feed": "dashboard", "/dashboard": "dashboard", "/season": "season", "/games": "season",
  "/stats": "stats",
  "/extras": "extras", "/picks": "extras", "/predictions": "extras", "/roster": "extras", "/leaderboard": "extras",
};

/* ── Position groups for the stats browser ── */
const POSITION_GROUPS: Record<League, { id: string; label: string; test: (pos: string) => boolean }[]> = {
  NBA: [
    { id: "G", label: "Guards", test: (p) => /^(PG|SG|G)$/.test(p) },
    { id: "F", label: "Forwards", test: (p) => /^(SF|PF|F)$/.test(p) },
    { id: "C", label: "Centers", test: (p) => /^C$/.test(p) },
  ],
  NFL: [
    { id: "QB", label: "Quarterbacks", test: (p) => p === "QB" },
    { id: "RB", label: "Running backs", test: (p) => /^(RB|FB)$/.test(p) },
    { id: "WR", label: "Wide receivers", test: (p) => p === "WR" },
    { id: "TE", label: "Tight ends", test: (p) => p === "TE" },
    { id: "DEF", label: "Defense", test: (p) => /^(DE|DT|NT|EDGE|LB|MLB|OLB|ILB|CB|S|FS|SS|DB)$/.test(p) },
  ],
};

function gameTitle(g?: Game) {
  if (!g) return "";
  return `${g.away_team.abbreviation || g.away_team.name} @ ${g.home_team.abbreviation || g.home_team.name}`;
}

/* ── team form computed from previous games ── */
type FormGame = { win: boolean; us: number; them: number; opp: string; id: number };
type TeamForm = { w: number; l: number; ppg: number; oppg: number; last: FormGame[]; total: number; latestId?: number };
function computeTeamForm(abbr: string, games: Game[]): TeamForm {
  const finals = games.filter((g) => g.status === "final" && [g.home_team.abbreviation, g.away_team.abbreviation].includes(abbr));
  let w = 0, l = 0, pf = 0, pa = 0;
  const last: FormGame[] = [];
  for (const g of finals) {
    const home = g.home_team.abbreviation === abbr;
    const us = home ? g.home_score : g.away_score;
    const them = home ? g.away_score : g.home_score;
    if (us == null || them == null) continue;
    if (us > them) w++;
    else l++;
    pf += us; pa += them;
    last.push({ win: us > them, us, them, opp: home ? g.away_team.abbreviation! : g.home_team.abbreviation!, id: g.id });
  }
  const n = w + l;
  return { w, l, ppg: n ? Math.round(pf / n) : 0, oppg: n ? Math.round(pa / n) : 0, last: last.slice(0, 8), total: n, latestId: finals[0]?.id };
}

function clampNum(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function askAssistant(prompt: string) {
  window.dispatchEvent(new CustomEvent("replaysai:assistant-prompt", { detail: { prompt } }));
}

/* ── lightweight SVG points trend ── */
function PointsTrend({ data }: { data: FormGame[] }) {
  const pts = [...data].reverse();
  if (pts.length < 2) return <p className="empty-state" style={{ padding: 0, fontSize: "0.8rem" }}>Not enough games for a trend yet.</p>;
  const all = pts.flatMap((g) => [g.us, g.them]);
  const max = Math.max(...all), min = Math.min(...all);
  const W = 280, H = 70, n = pts.length;
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => H - ((v - min) / (max - min || 1)) * (H - 8) - 4;
  const path = (k: "us" | "them") => pts.map((g, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(g[k]).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="trend" preserveAspectRatio="none">
      <path d={path("them")} className="t-them" /><path d={path("us")} className="t-us" />
      {pts.map((g, i) => <circle key={i} cx={x(i)} cy={y(g.us)} r="2.6" className="t-dot" />)}
    </svg>
  );
}

/* ── What-ifs for the latest game ── */
function WhatIf({ gameId, title }: { gameId?: number; title: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["whatif", gameId],
    queryFn: () => axios.get(apiPath(`/api/games/${gameId}/whatif`)).then((r) => r.data),
    enabled: !!gameId,
    staleTime: 300_000,
  });
  if (!gameId) return null;
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>What if…</span><h2>{title}</h2></div></div>
      {isLoading ? <p className="loading-text">Running scenarios…</p> : <div className="recap-content"><ReactMarkdown>{data?.scenarios || ""}</ReactMarkdown></div>}
    </section>
  );
}

/* ── Season shape (charts) ── */
function SeasonShape({ league, teams, games }: { league: League; teams: { name: string; abbreviation: string; sport: string }[]; games: Game[] }) {
  const leagueTeams = teams.filter((t) => t.sport === league);
  if (leagueTeams.length === 0) return null;
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>Season shape · from previous games</span><h2>Form & scoring</h2></div></div>
      <div className="shape-grid">
        {leagueTeams.map((t) => {
          const f = computeTeamForm(t.abbreviation, games);
          return (
            <div key={t.abbreviation} className="shape-card">
              <div className="shape-head"><strong>{t.abbreviation}</strong><span>{t.name}</span><b>{f.w}-{f.l}</b></div>
              <PointsTrend data={f.last} />
              <div className="shape-legend"><span className="lg us">scored {f.ppg}</span><span className="lg them">allowed {f.oppg}</span></div>
              <div className="stat-form">
                {f.last.map((r, i) => <Link key={i} to={`/game/${r.id}`} className={`form-dot ${r.win ? "w" : "l"}`} title={`${r.win ? "W" : "L"} ${r.us}-${r.them} vs ${r.opp}`}>{r.win ? "W" : "L"}</Link>)}
                {f.total === 0 && <span className="empty-state" style={{ padding: 0 }}>No finished games yet.</span>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ── Stats (teams + players) ── */
function StatsBlock({ league, players }: { league: League; players: FollowedPlayer[] }) {
  const leaguePlayers = players.filter((p) => p.sport === league);
  const { data: statMap = {} } = usePlayerStats(league, leaguePlayers.map((p) => p.id));
  if (leaguePlayers.length === 0) return null;
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>Followed players · season averages</span><h2>Player stats</h2></div></div>
      <div className="stat-cards">
        {leaguePlayers.map((p) => {
          const s = statMap[String(p.id)];
          return (
            <div key={p.id} className="stat-card player">
              <div className="stat-card-head"><strong>{p.name}</strong><span>{p.team || "FA"} · {p.position || "—"}</span></div>
              {s && s.line.length > 0 ? (
                <div className="player-line">{s.line.map((stat) => <div key={stat.label} className="player-stat"><b>{stat.value}</b><span>{stat.label}</span></div>)}</div>
              ) : <p className="empty-state" style={{ padding: "6px 0", fontSize: "0.82rem" }}>Season averages not published for this player.</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}


/* ── Rosters for the fan's own teams (deduped, cached) ── */
type TeamRosterPlayer = { id: number; name: string; position: string | null; team?: string | null; jersey?: string | null; headshot?: string | null };
function useFavoriteTeamRosters(league: League, teams: FavoriteTeam[]) {
  const leagueTeams = useMemo(() => teams.filter((t) => t.sport === league), [teams, league]);
  const results = useQueries({
    queries: leagueTeams.map((t) => ({
      queryKey: ["team-roster", t.id, t.sport],
      queryFn: () => axios.get(apiPath(`/api/teams/${t.id}/players`), { params: { sport: t.sport } }).then((r) => r.data as TeamRosterPlayer[]),
      staleTime: 600_000,
    })),
  });
  const pool = results.flatMap((r, i) => (r.data ?? []).map((p) => ({ ...p, team: p.team || leagueTeams[i]?.abbreviation || null })));
  return { pool, isLoading: results.some((r) => r.isLoading), teamCount: leagueTeams.length };
}

/* ── Stats browser scoped to the fan's teams (real ESPN season stats) ── */
function StatsExplorer({ league, teams, followed }: { league: League; teams: FavoriteTeam[]; followed: FollowedPlayer[] }) {
  const { pool, isLoading, teamCount } = useFavoriteTeamRosters(league, teams);
  const followedIds = useMemo(() => new Set(followed.map((p) => p.id)), [followed]);
  const groups = POSITION_GROUPS[league];
  const [filter, setFilter] = useState<string>("all");
  useEffect(() => { setFilter("all"); }, [league]);

  const groupOf = (pos: string | null) => groups.find((g) => g.test((pos || "").toUpperCase()));
  const perGroupCap = filter === "all" ? 8 : 40;
  const shownGroups = (filter === "all" ? groups : groups.filter((g) => g.id === filter))
    .map((g) => ({ group: g, players: pool.filter((p) => groupOf(p.position)?.id === g.id).slice(0, perGroupCap) }))
    .filter((x) => x.players.length > 0);

  const visibleIds = useMemo(
    () => shownGroups.flatMap((x) => x.players.map((p) => p.id)).slice(0, 36),
    [shownGroups],
  );
  const { data: statMap = {} } = usePlayerStats(league, visibleIds);

  if (teamCount === 0) {
    return (
      <section className="dash-panel">
        <div className="panel-heading"><div><span>Your {league} teams</span><h2>Player stats</h2></div></div>
        <p className="empty-state">No {league} teams followed yet. <Link to="/demo">Pick teams →</Link></p>
      </section>
    );
  }
  return (
    <section className="dash-panel">
      <div className="panel-heading">
        <div><span>Your {league} teams · real ESPN season stats</span><h2>Player stats</h2></div>
        <button className="btn-ghost" onClick={() => askAssistant(`Break down my ${league} teams' rosters by position this season.`)}>Ask the analyst</button>
      </div>
      <div className="stats-filter">
        <button className={filter === "all" ? "on" : ""} onClick={() => setFilter("all")}>All positions</button>
        {groups.map((g) => (
          <button key={g.id} className={filter === g.id ? "on" : ""} onClick={() => setFilter(g.id)}>{g.label}</button>
        ))}
      </div>
      {isLoading && pool.length === 0 && <p className="loading-text">Loading your teams' rosters…</p>}
      {!isLoading && pool.length === 0 && <p className="empty-state">Rosters unavailable right now.</p>}
      {shownGroups.map(({ group, players }) => (
        <div key={group.id} className="stat-pos-group">
          <h3 className="stat-pos-title">{group.label}<span>{players.length}</span></h3>
          <div className="stat-grid">
            {players.map((p) => {
              const line = statMap[String(p.id)]?.line ?? [];
              const isFollowed = followedIds.has(p.id);
              return (
                <Link key={p.id} to={`/player/${p.id}`} className={`stat-player-card ${isFollowed ? "followed" : ""}`}>
                  <div className="spc-head">
                    {p.headshot ? <img src={p.headshot} alt="" loading="lazy" /> : <span className="spc-ph">{p.position || "—"}</span>}
                    <div className="spc-id"><strong>{p.name}{isFollowed && <em className="spc-star" title="You follow this player">★</em>}</strong><span>{p.team || "FA"} · {p.position || "—"}</span></div>
                    {p.jersey && <b className="spc-impact" title="Jersey">#{p.jersey}</b>}
                  </div>
                  {line.length > 0 ? (
                    <div className="spc-line">{line.slice(0, 5).map((s) => <span key={s.label}><b>{s.value}</b>{s.label}</span>)}</div>
                  ) : (
                    <div className="spc-line muted">Season line loading…</div>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}

function PredictionLab({
  league,
  teams,
  games,
}: {
  league: League;
  teams: { name: string; abbreviation: string; sport: string }[];
  games: Game[];
}) {
  const leagueTeams = teams.filter((team) => team.sport === league);
  if (!leagueTeams.length) return null;
  return (
    <section className="dash-panel prediction-lab">
      <div className="panel-heading">
        <div><span>Prediction desk</span><h2>Season outlook</h2></div>
        <button className="btn-ghost" onClick={() => askAssistant(`Explain the ${league} prediction model for my teams in detail.`)}>Ask why</button>
      </div>
      <div className="model-grid">
        {leagueTeams.map((team) => {
          const form = computeTeamForm(team.abbreviation, games);
          const scoringEdge = form.ppg - form.oppg;
          const confidence = clampNum(50 + scoringEdge * 2 + (form.w - form.l) * 3, 12, 88);
          const label = confidence >= 65 ? "Positive trend" : confidence >= 48 ? "Volatile" : "Needs response";
          return (
            <div key={team.abbreviation} className="model-card">
              <div className="model-top"><strong>{team.abbreviation}</strong><span>{label}</span></div>
              <div className="model-ring" style={{ ["--p" as string]: `${confidence}%` }}><b>{Math.round(confidence)}%</b><span>confidence</span></div>
              <p>
                Record sample {form.w}-{form.l}. Scoring profile: {form.ppg || "-"} for,
                {` ${form.oppg || "-"} allowed`}. The model weights recent wins, point margin,
                and score stability from the games available in the ESPN feed.
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

type LeaderRow = {
  rank: number; user_id: string; display_name: string; total_points: number;
  correct_predictions: number; total_predictions: number; login_streak: number;
};
function LeaderboardPanel() {
  const { data: leaders = [], isLoading } = useLeaderboard() as { data?: LeaderRow[]; isLoading: boolean };
  const { data: mine } = useMyRank() as { data?: { my_rank: number; total_users: number } };
  const myId = getDeviceId();
  return (
    <section className="dash-panel sleeper-board">
      <div className="panel-heading"><div><span>Global picks ladder · points from correct picks</span><h2>Leaderboard</h2></div>
        {mine && <span className="panel-tag">You: #{mine.my_rank} of {mine.total_users}</span>}
      </div>
      {isLoading && <p className="loading-text">Loading the ladder…</p>}
      {!isLoading && leaders.length === 0 && (
        <p className="empty-state">No ranked fans yet. Lock a pick below, and when the game finishes you earn points and appear here.</p>
      )}
      <div className="sleep-table">
        {leaders.map((row) => (
          <div key={row.user_id} className={`sleep-row ${row.user_id === myId ? "me" : ""}`}>
            <b>{row.rank}</b>
            <div>
              <strong>{row.user_id === myId ? "You" : row.display_name}</strong>
              <span>{row.correct_predictions}/{row.total_predictions} correct · {row.login_streak} streak</span>
            </div>
            <em>{row.total_points}</em>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── Tailored news ── */
function NewsBlock({ league, teams, players, embedded }: { league: League; teams: { name: string; abbreviation: string; sport: string }[]; players: FollowedPlayer[]; embedded?: boolean }) {
  const leagueTeams = teams.filter((t) => t.sport === league);
  const leaguePlayers = players.filter((p) => p.sport === league);
  const keywords = useMemo(() => {
    const k: string[] = [];
    leagueTeams.forEach((t) => { k.push(t.name.split(" ").slice(-1)[0]); k.push(t.abbreviation); });
    leaguePlayers.forEach((p) => { k.push(p.name); });
    return [...new Set(k.filter(Boolean))];
  }, [leagueTeams, leaguePlayers]);
  const { data: news = [], isLoading } = useNews(league, keywords);

  const empty = keywords.length === 0
    ? <p className="empty-state" style={{ padding: "8px 0", fontSize: "0.82rem" }}>Follow teams/players for a tailored feed, never general news. <Link to="/demo">Pick →</Link></p>
    : isLoading ? <p className="loading-text">Finding your stories…</p>
    : news.length === 0 ? <p className="empty-state" style={{ padding: "8px 0", fontSize: "0.82rem" }}>No recent stories about your {league} picks.</p> : null;

  if (embedded) {
    return (
      <div className="rail-news">
        {empty}
        {news.slice(0, 8).map((a) => (
          <a key={a.id} className="rail-news-item" href={a.link || "#"} target="_blank" rel="noreferrer">
            <strong>{a.headline}</strong>{a.published && <span>{new Date(a.published).toLocaleDateString()}</span>}
          </a>
        ))}
      </div>
    );
  }
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>Tailored news · only your teams & players</span><h2>News feed</h2></div></div>
      {empty}
      <div className="news-grid">
        {news.map((a) => (
          <a key={a.id} className="news-card" href={a.link || "#"} target="_blank" rel="noreferrer">
            {a.image && <div className="news-thumb" style={{ backgroundImage: `url(${a.image})` }} />}
            <div className="news-body"><span className="news-sport">{a.sport}</span><strong>{a.headline}</strong><p>{a.description}</p>{a.published && <small>{new Date(a.published).toLocaleDateString()}</small>}</div>
          </a>
        ))}
      </div>
    </section>
  );
}

/* The Anthropic assistant lives in the bottom-right "AI" popup (FloatingAssistant). */

/* ── Extras: picks / roster / leaders ── */
function PicksPanel({ league }: { league: League }) {
  const { data: upcoming = [] } = useUpcomingGames() as { data?: { id: number; sport: string; game_date: string | null; home_team: { id: number; name: string | null }; away_team: { id: number; name: string | null } }[] };
  const { data: predictions = [] } = usePredictions() as { data?: { game_id: number; predicted_winner_team_id: number }[] };
  const create = useCreatePrediction();
  const games = upcoming.filter((g) => g.sport === league);
  const pickedFor = new Map(predictions.map((p) => [p.game_id, p.predicted_winner_team_id]));
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>{league} picks</span><h2>Lock your picks</h2></div></div>
      <div className="matchup-board">
        {games.length === 0 && <p className="empty-state">No scheduled {league} games to pick right now.</p>}
        {games.map((game) => {
          const picked = pickedFor.get(game.id);
          return (
            <div key={game.id} className="matchup-card">
              <div className="matchup-top"><span>{game.game_date ? new Date(game.game_date).toLocaleString() : "TBD"}</span><b>{picked ? "Locked ✓" : "Open"}</b></div>
              <div className="matchup-teams">
                {[game.away_team, game.home_team].map((team) => (
                  <button key={team.id} className={picked === team.id ? "selected" : ""} disabled={!!picked} onClick={() => create.mutate({ game_id: game.id, predicted_winner_team_id: team.id! })}>
                    <strong>{team.name}</strong><span>{team.id === game.away_team.id ? "Away" : "Home"}</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
function RosterPanel({ league }: { league: League }) {
  const { data: players = [] } = useRosterPlayers(league) as { data?: { id: number; name: string; team: string | null; position: string | null; impact_score: number }[] };
  const { data: rosters = [] } = useRosters() as { data?: { sport: string; player_ids: number[] }[] };
  const save = useSaveRoster();
  const saved = rosters.find((r) => r.sport === league.toUpperCase());
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const savedPlayerIds = useMemo(() => saved?.player_ids ?? [], [saved?.player_ids]);
  const savedPlayerKey = savedPlayerIds.join(",");
  useEffect(() => {
    const id = window.setTimeout(() => setPicked(new Set(savedPlayerIds)), 0);
    return () => window.clearTimeout(id);
  }, [league, savedPlayerKey, savedPlayerIds]);
  function toggle(id: number) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 8) next.add(id);
      return next;
    });
  }
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>{league} fantasy</span><h2>Roster ({picked.size}/8)</h2></div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-primary" disabled={picked.size === 0 || save.isPending} onClick={() => save.mutate({ sport: league, player_ids: [...picked] })}>{save.isPending ? "Saving…" : saved ? "Update" : "Save"}</button>
        </div></div>
      <div className="roster-pool">
        {players.length === 0 && <p className="empty-state">No {league} players yet.</p>}
        {[...players].sort((a, b) => b.impact_score - a.impact_score).slice(0, 30).map((p) => (
          <button key={p.id} className={`roster-player ${picked.has(p.id) ? "on" : ""}`} onClick={() => toggle(p.id)}>
            <div><strong>{p.name}</strong><span>{p.team || "FA"} · {p.position || "UTIL"}</span></div><b>{p.impact_score}</b>
          </button>
        ))}
      </div>
    </section>
  );
}

/* ── Live scores ticker for the fan's own teams ── */
function ScoresTicker({ sport, games: feedGames }: { sport: League; games: Game[] }) {
  const games = feedGames.filter((g) => g.status !== "scheduled").slice(0, 14);
  if (games.length === 0) return null;
  const row = games.length >= 6 ? [...games, ...games] : games;
  return (
    <div className="score-ticker">
      <span className="ticker-flag">{sport} · YOUR TEAMS</span>
      <div className="ticker-vp"><div className="ticker-row">
        {row.map((g, i) => (
          <Link key={i} to={`/game/${g.id}`} className="tick">
            <span className={`tick-dot ${g.status === "live" ? "live" : ""}`} />
            <b>{g.away_team.abbreviation}</b> {g.away_score ?? "—"} · {g.home_score ?? "—"} <b>{g.home_team.abbreviation}</b>
            <i>{g.status === "live" ? "LIVE" : "F"}</i>
          </Link>
        ))}
      </div></div>
    </div>
  );
}

/* ── Standings rail ── */
function StandingsRail({ sport, favs }: { sport: League; favs: Set<string> }) {
  const { data } = useRankings(sport);
  const standings = ((data?.[sport] ?? []) as Standing[]).slice(0, 10);
  return (
    <div className="rail-card">
      <div className="rail-head"><span>{sport} standings</span></div>
      {standings.length === 0 ? <p className="empty-state" style={{ padding: "8px 0", fontSize: "0.8rem" }}>Loading…</p> : (
        <table className="rail-table"><tbody>
          {standings.map((s, i) => (
            <tr key={s.team_id} className={favs.has(s.abbreviation) ? "fav" : ""}>
              <td className="r-rank">{i + 1}</td><td className="r-team">{s.abbreviation}</td>
              <td className="r-rec">{s.wins}-{s.losses}</td><td className="r-pct">{(s.win_pct * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody></table>
      )}
    </div>
  );
}

/* ── Your teams' key players rail ── */
function LeadersRail({ sport, teams }: { sport: League; teams: FavoriteTeam[] }) {
  const { pool, teamCount } = useFavoriteTeamRosters(sport, teams);
  const top = pool.slice(0, 8);
  if (teamCount === 0) return null;
  return (
    <div className="rail-card">
      <div className="rail-head"><span>{sport} · your players</span></div>
      {top.length === 0 ? <p className="empty-state" style={{ padding: "8px 0", fontSize: "0.8rem" }}>Loading…</p> : (
        <div className="rail-leaders">
          {top.map((p, i) => (
            <Link key={p.id} to={`/player/${p.id}`} className="rl-row">
              <span className="rl-rank">{i + 1}</span>
              <div><strong>{p.name}</strong><span>{p.team || "FA"} · {p.position || "—"}</span></div>
              {p.jersey && <b>#{p.jersey}</b>}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Up next: scheduled games involving the user's teams ── */
function nickname(name?: string) {
  return (name || "").toLowerCase().split(" ").pop() || "";
}
function UpNext({ league, favTeams }: { league: League; favTeams: { name: string; sport: string; abbreviation: string }[] }) {
  const { data: upcoming = [] } = useUpcomingGames() as {
    data?: { id: number; sport: string; game_date: string | null; home_team: { name: string | null }; away_team: { name: string | null }; already_predicted?: boolean }[];
  };
  const leagueFavs = favTeams.filter((t) => t.sport === league);
  if (!leagueFavs.length) return null;
  const favNicks = new Set(leagueFavs.map((t) => nickname(t.name)));
  const games = upcoming
    .filter((g) => g.sport === league && (favNicks.has(nickname(g.home_team.name || "")) || favNicks.has(nickname(g.away_team.name || ""))))
    .slice(0, 5);
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>Up next · your teams</span><h2>Upcoming games</h2></div></div>
      {games.length === 0 ? (
        <p className="empty-state" style={{ padding: "8px 0", fontSize: "0.85rem" }}>No scheduled {league} games for your teams right now.</p>
      ) : (
        <div className="upnext-list">
          {games.map((g) => (
            <Link key={g.id} to={`/game/${g.id}`} className="upnext-row">
              <div className="upnext-teams"><strong>{g.away_team.name}</strong><span>@</span><strong>{g.home_team.name}</strong></div>
              <div className="upnext-meta">
                <span>{g.game_date ? new Date(g.game_date).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "TBD"}</span>
                <em className={g.already_predicted ? "picked" : ""}>{g.already_predicted ? "Picked ✓" : "Make a pick →"}</em>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Your stars: compact season line for followed players ── */
function YourStars({ league, players }: { league: League; players: FollowedPlayer[] }) {
  const leaguePlayers = players.filter((p) => p.sport === league);
  const { data: statMap = {} } = usePlayerStats(league, leaguePlayers.map((p) => p.id));
  if (!leaguePlayers.length) return null;
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>Your stars · {league}</span><h2>Players you follow</h2></div></div>
      <div className="stars-strip">
        {leaguePlayers.map((p) => {
          const line = statMap[String(p.id)]?.line ?? [];
          return (
            <Link key={p.id} to={`/player/${p.id}`} className="star-chip">
              <div className="star-chip-head"><strong>{p.name}</strong><span>{p.team || "FA"} · {p.position || "—"}</span></div>
              {line.length > 0 ? (
                <div className="star-chip-line">{line.slice(0, 3).map((s) => <span key={s.label}><b>{s.value}</b> {s.label}</span>)}</div>
              ) : (
                <div className="star-chip-line muted">Season line updates as games post</div>
              )}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

/* ── Recent results: latest finals for the user's teams ── */
function RecentResults({ games }: { games: Game[] }) {
  const navigate = useNavigate();
  const finals = games.filter((g) => g.status === "final").slice(0, 6);
  if (!finals.length) return null;
  return (
    <section className="dash-panel">
      <div className="panel-heading"><div><span>Recent results · your teams</span><h2>Latest games</h2></div>
        <button className="btn-ghost" onClick={() => navigate("/season")}>See full season →</button></div>
      <div className="games-grid compact">{finals.map((g) => <ScoreCard key={g.id} game={g} />)}</div>
    </section>
  );
}

/* ── Feature spotlight (discoverability for narrated reels + newsletter) ── */
function FeatureSpotlight() {
  const navigate = useNavigate();
  return (
    <div className="feature-spotlight">
      <button className="fs-card fs-reel" onClick={() => navigate("/reels")}>
        <span className="fs-badge">NEW</span>
        <strong>AI Reel Director</strong>
        <p>Tell the AI what reel to build in plain language, or launch a full Broadcast mode.</p>
        <span className="fs-go">Open reel director →</span>
      </button>
      <button className="fs-card fs-season" onClick={() => navigate("/newsletter")}>
        <span className="fs-badge">NEW</span>
        <strong>Weekly Newsletter</strong>
        <p>Your personalized sports digest: team results, player stats, hot takes, and picks.</p>
        <span className="fs-go">Read this week's issue →</span>
      </button>
    </div>
  );
}

/* ── Dashboard shell ── */
export default function Feed() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const activeTab: Tab = PATH_TO_TAB[pathname] ?? "dashboard";
  const [league, setLeague] = useState<League>("NBA");
  const [moreOpen, setMoreOpen] = useState(false);

  const { data: user } = useCurrentUser();
  const { data: feed, isLoading } = useFeed();
  const { data: liveData } = useGames({ sport: league, status: "live", limit: 12 });

  const favoriteTeams = useMemo(
    () => (user?.favorite_teams ?? []) as FavoriteTeam[],
    [user?.favorite_teams],
  );
  const followedPlayers = useMemo(
    () => (user?.followed_players ?? []) as FollowedPlayer[],
    [user?.followed_players],
  );

  // Auto-select the league of the picked teams so the dashboard isn't blank when
  // a fan follows NFL teams but the toggle defaulted to NBA.
  useEffect(() => {
    if (favoriteTeams.length && !favoriteTeams.some((t) => t.sport === league)) {
      const id = window.setTimeout(() => setLeague(favoriteTeams[0].sport as League), 0);
      return () => window.clearTimeout(id);
    }
  }, [favoriteTeams, league]);

  const games: Game[] = ((feed?.games ?? []) as Game[]).filter((g) => g.sport === league);
  const onboarded = feed?.onboarded ?? false;
  const live = (liveData?.games ?? []) as Game[];
  void live; // live count available for future use
  const latestFinal = games.find((g) => g.status === "final");

  return (
    <div className={`dash league-${league.toLowerCase()}`}>
      <aside className="dash-sidebar">
        <Link to="/" className="dash-brand"><img src="/replaysai-logo.svg" alt="" />Replays<b>AI</b></Link>
        <nav className="dash-nav">
          {TABS.map((tab) => <button key={tab.id} className={activeTab === tab.id ? "on" : ""} onClick={() => navigate(tab.path)}>{tab.label}</button>)}
          <div className="dash-nav-divider" />
          <Link to="/reels" className="dash-nav-link">Reels <span className="nav-new">NEW</span></Link>
          <Link to="/newsletter" className="dash-nav-link">Newsletter <span className="nav-new">NEW</span></Link>
        </nav>
        <div className="dash-side-card">
          <span>Following</span>
          <strong>{favoriteTeams.length} teams · {followedPlayers.length} players</strong>
          <Link to="/demo">Edit →</Link>
        </div>
      </aside>

      <main className="dash-main">
        <header className="dash-header">
          <div>
            <p className="dashboard-kicker">Live sports desk</p>
            <h1>{user?.display_name || `${league} feed`}</h1>
          </div>
          <div className="dash-header-right">
            <div className="league-switch">
              {(["NBA", "NFL"] as League[]).map((l) => (
                <button key={l} className={league === l ? "active" : ""} onClick={() => setLeague(l)}>{l}</button>
              ))}
            </div>
          </div>
        </header>

        {!onboarded && (
          <div className="setup-banner">
            <div><strong>Set up your feed.</strong><p>Pick teams and players to filter everything to your selections.</p></div>
            <Link to="/demo" className="btn-primary">Pick teams</Link>
          </div>
        )}

        {activeTab === "dashboard" && (
          <div className="dash-layout">
            <div className="dash-main-col">
              <ScoresTicker sport={league} games={games} />
              <YourStars league={league} players={followedPlayers} />
              <RecentResults games={games} />
              <UpNext league={league} favTeams={favoriteTeams} />
              <FeatureSpotlight />
              <details className="dash-more" onToggle={(e) => setMoreOpen((e.target as HTMLDetailsElement).open)}>
                <summary>Analysis: predictions, what-ifs, player stats</summary>
                {moreOpen && (
                  <div className="dash-more-body">
                    <PredictionLab league={league} teams={favoriteTeams} games={games} />
                    <WhatIf gameId={latestFinal?.id} title={latestFinal ? gameTitle(latestFinal) : ""} />
                    <StatsBlock league={league} players={followedPlayers} />
                  </div>
                )}
              </details>
            </div>
            <aside className="dash-rail">
              <StandingsRail sport={league} favs={new Set(favoriteTeams.filter((t) => t.sport === league).map((t) => t.abbreviation))} />
              <LeadersRail sport={league} teams={favoriteTeams} />
              <div className="rail-card">
                <div className="rail-head"><span>News</span></div>
                <NewsBlock league={league} teams={favoriteTeams} players={followedPlayers} embedded />
              </div>
            </aside>
          </div>
        )}

        {activeTab === "season" && (
          <>
            <SeasonShape league={league} teams={favoriteTeams} games={games} />
            <section className="dash-panel">
              <div className="panel-heading">
                <div><span>{league} season</span><h2>All games {games.length ? `(${games.length})` : ""}</h2></div>
                <button className="btn-ghost" onClick={() => navigate("/reels")}>Make a reel →</button>
              </div>
              {isLoading && <p className="loading-text">Loading games…</p>}
              {!isLoading && games.length === 0 && <p className="empty-state">No {league} games yet. <Link to="/demo">Pick teams →</Link></p>}
              <div className="games-grid">{games.map((g) => <ScoreCard key={g.id} game={g} />)}</div>
            </section>
          </>
        )}

        {activeTab === "stats" && (
          <>
            <StatsExplorer league={league} teams={favoriteTeams} followed={followedPlayers} />
            <StatsBlock league={league} players={followedPlayers} />
          </>
        )}

        {activeTab === "extras" && (
          <>
            <PicksPanel league={league} />
            <RosterPanel league={league} />
            <LeaderboardPanel />
            <section className="dash-panel">
              <div className="panel-heading"><div><span>Your account · points from correct picks</span><h2>Points & badges</h2></div></div>
              <div className="leaders-stats">
                <div className="dashboard-stat"><strong>{user?.total_points ?? 0}</strong><span>Points</span></div>
                <div className="dashboard-stat"><strong>{user?.login_streak ?? 0}</strong><span>Streak</span></div>
                <div className="dashboard-stat"><strong>{Math.round((user?.prediction_accuracy ?? 0) * 100)}%</strong><span>Accuracy</span></div>
                <div className="dashboard-stat"><strong>{user?.correct_predictions ?? 0}/{user?.total_predictions ?? 0}</strong><span>Correct</span></div>
              </div>
              {(user?.badges ?? []).length > 0 && (
                <div className="badge-row">
                  {(user?.badges ?? []).map((b: { slug: string; name: string; icon: string }) => (
                    <span key={b.slug} className="badge-chip" title={b.name}>{b.icon} {b.name}</span>
                  ))}
                </div>
              )}
              {(user?.total_predictions ?? 0) === 0 && (
                <p className="panel-note">Lock a pick in the board above. When the game finishes, correct picks earn points and badges, and you climb the ladder.</p>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
