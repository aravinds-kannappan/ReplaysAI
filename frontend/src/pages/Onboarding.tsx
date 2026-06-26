import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";
import {
  setLocalFavoriteTeams,
  setLocalFollowedPlayers,
  type FollowedPlayer,
} from "../hooks/useUser";
import "./Onboarding.css";

type Team = {
  id: number;
  abbreviation: string;
  name: string;
  sport: string;
  logo?: string | null;
};

type League = "NBA" | "NFL";

const BUILD_JOBS = [
  "Saving teams and star players",
  "Running Anthropic personalization",
  "Retrieving games, stats, news, and clips",
  "Preparing picks, reels, and recaps",
  "Opening your personalized feed",
];

function teamKey(team: Pick<Team, "sport" | "abbreviation">) {
  return `${team.sport}:${team.abbreviation}`;
}

const LEAGUE_CARDS: { id: League | "BOTH"; emoji: string; title: string; sub: string }[] = [
  { id: "NBA", emoji: "🏀", title: "NBA", sub: "Pro basketball" },
  { id: "NFL", emoji: "🏈", title: "NFL", sub: "Pro football" },
  { id: "BOTH", emoji: "🏀🏈", title: "Both", sub: "NBA + NFL" },
];

// Per-team card that loads the real ESPN roster and offers one-tap player follows.
function TeamPlayerCard({
  team,
  followedIds,
  onToggle,
}: {
  team: Team;
  followedIds: Set<number>;
  onToggle: (player: FollowedPlayer) => void;
}) {
  const { data: roster = [], isLoading } = useQuery<FollowedPlayer[]>({
    queryKey: ["team-roster", team.id, team.sport],
    queryFn: () =>
      axios.get(apiPath(`/api/teams/${team.id}/players`), { params: { sport: team.sport } }).then((r) => r.data),
    staleTime: 600_000,
  });
  return (
    <div className="wz-player-card">
      <div className="wz-player-head">
        {team.logo && <img src={team.logo} alt="" />}
        <div>
          <strong>{team.abbreviation}</strong>
          <span>Top 10 stars</span>
        </div>
      </div>
      {isLoading ? (
        <p className="loading-text">Loading stars…</p>
      ) : roster.length === 0 ? (
        <p className="empty-state" style={{ padding: "10px 0" }}>Roster unavailable.</p>
      ) : (
        <div className="wz-chip-row">
          {roster.map((player) => {
            const on = followedIds.has(player.id);
            return (
              <button
                key={player.id}
                className={`wz-player-chip ${on ? "on" : ""}`}
                onClick={() => onToggle({ ...player, sport: team.sport, team: team.abbreviation, team_name: team.name })}
              >
                {player.name}
                {player.position ? <i>{player.position}</i> : null}
                <span>{on ? "✓" : "+"}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function BuildingScreen({ teams, players }: { teams: Team[]; players: FollowedPlayer[] }) {
  const [done, setDone] = useState(0);
  useEffect(() => {
    const timers = BUILD_JOBS.map((_, i) => setTimeout(() => setDone(i + 1), 6200 * (i + 1)));
    return () => timers.forEach(clearTimeout);
  }, []);
  return (
    <div className="wz-building">
      <div className="wz-building-orb"><span /><span /><span /></div>
      <p className="wz-kicker">Building feed</p>
      <h2>Building your dashboard</h2>
      <p>Following {teams.length} team{teams.length !== 1 ? "s" : ""}{players.length ? ` · ${players.length} player${players.length !== 1 ? "s" : ""}` : ""}. This takes about 30 seconds because the backend is generating your personalized feed.</p>
      <div className="wz-jobs">
        {BUILD_JOBS.map((job, i) => (
          <div key={job} className={`wz-job ${i < done ? "done" : i === done ? "active" : ""}`}>
            <span className="wz-job-dot">{i < done ? "✓" : ""}</span>
            {job}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Onboarding() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [step, setStep] = useState(0); // 0 league, 1 teams, 2 players, 3 building
  const [leagues, setLeagues] = useState<League[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // The wizard owns its own player selection so a new demo run never inherits
  // stale follows; we only commit to localStorage (replacing prior picks) on finish.
  const [selectedPlayers, setSelectedPlayers] = useState<Map<number, FollowedPlayer>>(new Map());
  const [query, setQuery] = useState("");

  const { data: nbaTeams = [], isLoading: nbaLoading, isError: nbaError } = useQuery<Team[]>({
    queryKey: ["teams", "NBA"],
    queryFn: () => axios.get(apiPath("/api/teams"), { params: { sport: "NBA" } }).then((r) => r.data),
    staleTime: 600_000,
  });
  const { data: nflTeams = [], isLoading: nflLoading, isError: nflError } = useQuery<Team[]>({
    queryKey: ["teams", "NFL"],
    queryFn: () => axios.get(apiPath("/api/teams"), { params: { sport: "NFL" } }).then((r) => r.data),
    staleTime: 600_000,
  });

  const followedPlayers = [...selectedPlayers.values()];
  const followedIds = new Set<number>(selectedPlayers.keys());

  function togglePlayer(player: FollowedPlayer) {
    setSelectedPlayers((prev) => {
      const next = new Map(prev);
      if (next.has(player.id)) next.delete(player.id);
      else next.set(player.id, player);
      return next;
    });
  }

  const leagueTeams = useMemo(() => {
    const pool: Team[] = [];
    if (leagues.includes("NBA")) pool.push(...nbaTeams);
    if (leagues.includes("NFL")) pool.push(...nflTeams);
    return pool;
  }, [leagues, nbaTeams, nflTeams]);

  const filteredTeams = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return leagueTeams;
    return leagueTeams.filter((t) => t.name.toLowerCase().includes(q) || t.abbreviation.toLowerCase().includes(q));
  }, [leagueTeams, query]);

  const selectedTeams = leagueTeams.filter((t) => selected.has(teamKey(t)));
  const teamsLoading = (leagues.includes("NBA") && nbaLoading) || (leagues.includes("NFL") && nflLoading);
  const teamsError = (leagues.includes("NBA") && nbaError) || (leagues.includes("NFL") && nflError);

  function chooseLeague(id: League | "BOTH") {
    setLeagues(id === "BOTH" ? ["NBA", "NFL"] : [id]);
    setStep(1);
  }

  function toggleTeam(team: Team) {
    setSelected((prev) => {
      const next = new Set(prev);
      const key = teamKey(team);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function warmDownstream(teams: Team[]) {
    const favoriteKeys = teams.map((team) => teamKey(team)).join(",");
    try {
      const feed = await queryClient.fetchQuery({
        queryKey: ["feed", favoriteKeys],
        queryFn: () => axios.get(apiPath("/api/feed"), { params: { favorite_teams: favoriteKeys } }).then((r) => r.data),
      });
      const topGames = ((feed?.games ?? []) as { id: number; status: string }[])
        .filter((g) => g.status !== "scheduled")
        .slice(0, 3);
      await Promise.allSettled(
        topGames.map((g) =>
          queryClient.prefetchQuery({
            queryKey: ["reel-cuts", g.id],
            queryFn: () => axios.get(apiPath(`/api/games/${g.id}/reels`)).then((r) => r.data),
            staleTime: 300_000,
          }),
        ),
      );
    } catch {
      /* best-effort warm-up */
    }
  }

  async function finish() {
    if (!selectedTeams.length) return;
    // Replace prior picks entirely so the dashboard only reflects this run.
    setLocalFavoriteTeams(selectedTeams);
    setLocalFollowedPlayers([...selectedPlayers.values()]);
    window.localStorage.setItem("replaysai:onboarded", "true");
    queryClient.invalidateQueries({ queryKey: ["me"] });
    queryClient.invalidateQueries({ queryKey: ["feed"] });
    setStep(3);
    try {
      await axios.post(apiPath("/api/personalization/generate"), {
        teams: selectedTeams,
        players: [...selectedPlayers.values()],
        min_seconds: 32,
      });
    } catch {
      // If Anthropic is not configured locally, still warm the dashboard data.
    }
    await warmDownstream(selectedTeams);
    navigate("/feed");
  }

  const stepLabels = ["League", "Teams", "Players"];

  return (
    <div className="wizard">
      {step < 3 && (
        <div className="wz-progress">
          {stepLabels.map((label, i) => (
            <div key={label} className={`wz-progress-step ${i === step ? "on" : ""} ${i < step ? "done" : ""}`}>
              <span className="wz-num">{i < step ? "✓" : i + 1}</span>
              <span className="wz-label">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Step 0 — league */}
      {step === 0 && (
        <div className="wz-panel">
          <p className="wz-kicker">Try the demo · no login</p>
          <h1>Build your personalized sports feed</h1>
          <p className="wz-sub">In three quick steps, ReplaysAI sets up a feed, reels, news, picks, and an assistant around what you care about. Start by choosing a league.</p>
          <div className="wz-league-cards">
            {LEAGUE_CARDS.map((card) => (
              <button key={card.id} className="wz-league-card" onClick={() => chooseLeague(card.id)}>
                <span className="wz-league-emoji">{card.emoji}</span>
                <strong>{card.title}</strong>
                <span>{card.sub}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 1 — teams */}
      {step === 1 && (
        <div className="wz-panel">
          <p className="wz-kicker">Step 2 of 3</p>
          <h1>Pick your teams</h1>
          <p className="wz-sub">Choose teams to follow. Your feed, reels, news, picks, stats, and player boards rank around them.</p>
          <input className="wz-search" placeholder="Search teams…" value={query} onChange={(e) => setQuery(e.target.value)} />
          {selectedTeams.length > 0 && (
            <div className="wz-selected-summary">
              {selectedTeams.map((t) => (
                <button key={teamKey(t)} className="wz-selected-chip" onClick={() => toggleTeam(t)}>{t.abbreviation} ✕</button>
              ))}
            </div>
          )}
          <div className="wz-team-grid">
            {teamsLoading && <p className="empty-state">Loading teams from the backend…</p>}
            {teamsError && <p className="empty-state">Could not load teams. Make sure the backend is running on port 8001.</p>}
            {!teamsLoading && !teamsError && filteredTeams.length === 0 && <p className="empty-state">No teams found.</p>}
            {filteredTeams.map((team) => {
              const on = selected.has(teamKey(team));
              return (
                <button key={teamKey(team)} className={`wz-team-card ${on ? "on" : ""}`} onClick={() => toggleTeam(team)}>
                  {team.logo ? <img src={team.logo} alt="" /> : <span className="wz-team-fallback">{team.abbreviation}</span>}
                  <strong>{team.abbreviation}</strong>
                  <span>{team.name}</span>
                </button>
              );
            })}
          </div>
          <div className="wz-nav">
            <button className="btn-ghost" onClick={() => { setStep(0); setQuery(""); }}>← Back</button>
            <button className="btn-hero-primary" disabled={selectedTeams.length === 0} onClick={() => setStep(2)}>
              {selectedTeams.length === 0 ? "Pick at least one team" : `Next: follow players →`}
            </button>
          </div>
        </div>
      )}

      {/* Step 2 — players */}
      {step === 2 && (
        <div className="wz-panel">
          <p className="wz-kicker">Step 3 of 3 · optional</p>
          <h1>Follow players</h1>
          <p className="wz-sub">Tap the star players you care about from each team. Your feed, stats, reels, and assistant will track them throughout the dashboard. You can skip this.</p>
          <div className="wz-player-grid">
            {selectedTeams.map((team) => (
              <TeamPlayerCard key={teamKey(team)} team={team} followedIds={followedIds} onToggle={togglePlayer} />
            ))}
          </div>
          <div className="wz-nav">
            <button className="btn-ghost" onClick={() => setStep(1)}>← Back</button>
            <button className="btn-hero-primary" onClick={finish}>
              {followedPlayers.length ? `Build my feed (${followedPlayers.length} player${followedPlayers.length !== 1 ? "s" : ""}) →` : "Build my feed →"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3 — building */}
      {step === 3 && <BuildingScreen teams={selectedTeams} players={followedPlayers} />}
    </div>
  );
}
