import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useFeed, useRosterPlayers, useUpcomingGames } from "../hooks/usePredictions";
import { useCurrentUser } from "../hooks/useUser";
import { useGames } from "../hooks/useGames";
import ScoreCard from "../components/ScoreCard";
import type { Game } from "../types";

type DashboardTab = "feed" | "live" | "chat" | "predictions" | "roster" | "agents";

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
};

type League = "NBA" | "NFL";

const TABS: { id: DashboardTab; label: string }[] = [
  { id: "feed", label: "Feed" },
  { id: "live", label: "Live" },
  { id: "chat", label: "Chat" },
  { id: "predictions", label: "Predictions" },
  { id: "roster", label: "Roster" },
  { id: "agents", label: "Agents" },
];

const AGENTS = [
  { name: "Live ingest", status: "Watching schedules, scores, and play-by-play every 60 seconds." },
  { name: "Recap writer", status: "Creates post-game summaries for final and live games." },
  { name: "Personalizer", status: "Ranks games from your favorite teams and followed players." },
  { name: "Forecast", status: "Prepares picks, roster outlooks, and what-if simulations." },
];

const LEAGUE_META: Record<League, { name: string; search: string; stream: string; cues: string[] }> = {
  NBA: {
    name: "NBA",
    search: "https://www.google.com/search?q=NBA+highlights+today",
    stream: "https://www.espn.com/nba/",
    cues: ["Shot quality", "Run detector", "Star usage", "Clutch swings"],
  },
  NFL: {
    name: "NFL",
    search: "https://www.google.com/search?q=NFL+highlights+today",
    stream: "https://www.espn.com/nfl/",
    cues: ["Drive success", "Explosive plays", "QB pressure", "Red-zone swings"],
  },
};

function formatGameTitle(game?: Game) {
  if (!game) return "No game selected";
  const away = game.away_team.abbreviation || game.away_team.name || "Away";
  const home = game.home_team.abbreviation || game.home_team.name || "Home";
  return `${away} at ${home}`;
}

function DashboardStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="dashboard-stat">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function AgentPanel() {
  return (
    <div className="agent-panel">
      {AGENTS.map((agent) => (
        <div key={agent.name} className="agent-status-card">
          <span className="agent-light" />
          <div>
            <strong>{agent.name}</strong>
            <p>{agent.status}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function PersonalizationLoader({ teams }: { teams: { abbreviation: string; sport: string; name: string }[] }) {
  return (
    <div className="personalization-loader">
      <div>
        <span>Agents retrieving context</span>
        <h2>Your teams are activated</h2>
        <p>ReplaysAI is ready to pull schedules, players, reels, news, predictions, and matchup context for your selected teams.</p>
      </div>
      <div className="team-activation-list">
        {teams.map((team) => (
          <div key={`${team.sport}-${team.abbreviation}`}>
            <strong>{team.abbreviation}</strong>
            <span>{team.name}</span>
          </div>
        ))}
      </div>
      <div className="agent-panel">
        {["Schedule scan", "Player graph", "News rails", "Reel queue"].map((job) => (
          <div key={job} className="agent-status-card"><span className="agent-light" /><div><strong>{job}</strong><p>Queued for this team graph.</p></div></div>
        ))}
      </div>
      <Link to="/onboarding" className="btn-ghost">Edit teams</Link>
    </div>
  );
}

function AssistantChat({ games, league }: { games: Game[]; league: League }) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "Ask about your teams, a live game, a player trend, or a roster what-if. I will use the selected league and loaded dashboard games first.",
    },
  ]);

  function respond(question: string) {
    const featured = games[0];
    const answer = featured
      ? `${formatGameTitle(featured)} is the best ${league} starting point. It is marked ${featured.status}, with ${featured.away_score ?? 0}-${featured.home_score ?? 0} on the board. Next step: open the game card for the play timeline, recap, and fan-mode summary.`
      : `I do not see ${league} games yet. Pick favorite teams in onboarding or run the historical backfill so I can ground answers in real game data.`;

    setMessages((prev) => [
      ...prev,
      { role: "user", text: question },
      { role: "assistant", text: answer },
    ]);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const question = draft.trim();
    if (!question) return;
    setDraft("");
    respond(question);
  }

  return (
    <div className="chat-shell">
      <div className="chat-log">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>
            {message.text}
          </div>
        ))}
      </div>
      <form className="chat-form" onSubmit={submit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask what happened, what matters next, or who to roster..."
        />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}

function LeagueSwitch({ league, onChange }: { league: League; onChange: (league: League) => void }) {
  return (
    <div className="league-switch" aria-label="League switch">
      {(["NBA", "NFL"] as League[]).map((item) => (
        <button key={item} className={league === item ? "active" : ""} onClick={() => onChange(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}

function SignalBoard({ league }: { league: League }) {
  return (
    <div className="signal-board">
      {LEAGUE_META[league].cues.map((cue, index) => (
        <div key={cue} className="signal-row">
          <span>{String(index + 1).padStart(2, "0")}</span>
          <strong>{cue}</strong>
          <i style={{ width: `${68 + index * 7}%` }} />
        </div>
      ))}
    </div>
  );
}

export default function Feed() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("feed");
  const [league, setLeague] = useState<League>("NBA");
  const { data: user } = useCurrentUser();
  const { data: feed, isLoading } = useFeed();
  const { data: liveGames } = useGames({ sport: league, status: "live", limit: 12 });
  const { data: upcomingGames = [] } = useUpcomingGames();
  const { data: rosterPlayers = [] } = useRosterPlayers(league);

  const games: Game[] = (feed?.games ?? []).filter((game: Game) => game.sport === league);
  const onboarded = feed?.onboarded ?? false;
  const favoriteCount = user?.favorite_teams?.length ?? 0;
  const favoriteTeams = (user?.favorite_teams ?? []) as { abbreviation: string; sport: string; name: string }[];
  const topRosterPlayers = rosterPlayers.slice(0, 5) as {
    id: number;
    name: string;
    team: string | null;
    position: string | null;
    impact_score: number;
  }[];

  const postGameSummaries = useMemo(
    () => games.filter((game) => game.status === "final").slice(0, 3),
    [games],
  );

  const live = liveGames?.games ?? [];
  const leagueUpcoming = upcomingGames.filter((game: { sport: string }) => game.sport === league);

  return (
    <div className={`app-shell league-${league.toLowerCase()}`}>
      <aside className="app-sidebar">
        <Link to="/" className="sidebar-brand">ReplaysAI</Link>
        <nav className="sidebar-nav">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={activeTab === tab.id ? "active" : ""}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-card">
          <span>Personalization</span>
          <strong>{onboarded ? `${favoriteCount} teams active` : "Needs setup"}</strong>
            <Link to="/onboarding">Edit teams</Link>
        </div>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <p className="dashboard-kicker">Command center</p>
            <h1>{user?.display_name || user?.username || `${league} dashboard`}</h1>
            <p>
              Personalized {league} feed, live games, post-game summaries, picks, chat, and roster forecasts
              in one place.
            </p>
          </div>
          <div className="dashboard-actions">
            <LeagueSwitch league={league} onChange={setLeague} />
            <div className="dashboard-stats">
              <DashboardStat label="Points" value={user?.total_points ?? 0} />
              <DashboardStat label="Streak" value={user?.login_streak ?? 0} />
              <DashboardStat label="Live" value={live.length} />
            </div>
          </div>
        </header>

        {!onboarded && (
          <div className="setup-banner">
            <div>
              <strong>Choose favorite teams to unlock personalization.</strong>
              <p>Your feed, summaries, predictions, and roster suggestions will rank around them.</p>
            </div>
            <Link to="/onboarding" className="btn-primary">Choose teams</Link>
          </div>
        )}
        {onboarded && (
          <div className="setup-banner">
            <div>
              <strong>{favoriteCount} teams active.</strong>
              <p>Agents will use these teams to rank games, reels, predictions, and roster recommendations.</p>
            </div>
            <Link to="/onboarding" className="btn-primary">Edit teams</Link>
          </div>
        )}

        {activeTab === "feed" && (
          <section className="dashboard-grid">
            <div className="dashboard-panel span-2">
              <div className="panel-heading">
                <div>
                  <span>{onboarded ? `${league} for you` : `${league} recent games`}</span>
                  <h2>{onboarded ? "Personalized feed" : "Start with recent games"}</h2>
                </div>
                <Link to="/predictions">Make picks</Link>
              </div>
              {isLoading && <p className="loading-text">Loading games...</p>}
              {!isLoading && games.length === 0 && (
                onboarded ? <PersonalizationLoader teams={favoriteTeams} /> : <p className="empty-state">No games loaded yet. Pick teams to personalize the feed.</p>
              )}
              <div className="games-grid compact">
                {games.slice(0, 6).map((game) => <ScoreCard key={game.id} game={game} />)}
              </div>
            </div>

            <div className="dashboard-panel">
              <div className="panel-heading">
                <div>
                  <span>Post-game</span>
                  <h2>Summary queue</h2>
                </div>
              </div>
              <div className="summary-list">
                {postGameSummaries.length === 0 && <p className="empty-state">No final games in your feed yet.</p>}
                {postGameSummaries.map((game) => (
                  <Link to={`/game/${game.id}`} key={game.id} className="summary-row">
                    <strong>{formatGameTitle(game)}</strong>
                    <span>Generate recap and fan view</span>
                  </Link>
                ))}
              </div>
            </div>

            <div className="dashboard-panel">
              <div className="panel-heading">
                <div>
                  <span>Agents</span>
                  <h2>Today</h2>
                </div>
              </div>
              <AgentPanel />
            </div>
          </section>
        )}

        {activeTab === "live" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>{league} every 30 seconds</span>
                <h2>Live highlight control room</h2>
              </div>
              <a href={LEAGUE_META[league].stream} target="_blank" rel="noreferrer">ESPN hub</a>
            </div>
            <div className="live-command-grid">
              <div className="live-rink">
                <div className="live-rink-line" />
                <div className="live-puck">{league}</div>
                <div className="live-rink-copy">
                  <strong>{live.length ? `${live.length} games live` : "No live games right now"}</strong>
                  <span>When games are active, this panel becomes the fast lane into highlights, play timeline, and recap generation.</span>
                </div>
              </div>
              <SignalBoard league={league} />
            </div>
            <div className="games-grid compact">
              {live.map((game) => <ScoreCard key={game.id} game={game} />)}
            </div>
          </section>
        )}

        {activeTab === "chat" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>Conversational layer</span>
                <h2>Ask ReplaysAI about {league}</h2>
              </div>
              <a href={LEAGUE_META[league].search} target="_blank" rel="noreferrer">Google highlights</a>
            </div>
            <div className="research-layout">
              <AssistantChat games={games} league={league} />
              <aside className="research-panel">
                <strong>Research rails</strong>
                <a href={LEAGUE_META[league].search} target="_blank" rel="noreferrer">Search today&apos;s highlights</a>
                <a href={LEAGUE_META[league].stream} target="_blank" rel="noreferrer">Open ESPN league page</a>
                <Link to="/roster">Simulate roster impact</Link>
                <Link to="/predictions">Turn answer into a pick</Link>
              </aside>
            </div>
          </section>
        )}

        {activeTab === "predictions" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>{league} forecast</span>
                <h2>Prediction board</h2>
              </div>
              <Link to="/predictions">Open picks</Link>
            </div>
            <div className="prediction-stage">
              <div className="prediction-orbit">
                <span>Model</span>
                <strong>{league === "NBA" ? "Pace + shot profile" : "Drive + field position"}</strong>
                <small>Use live context, matchup history, and roster form before locking picks.</small>
              </div>
              <SignalBoard league={league} />
            </div>
            <div className="prediction-queue">
              {leagueUpcoming.length === 0 && <p className="empty-state">No scheduled {league} games available for picks.</p>}
              {leagueUpcoming.slice(0, 6).map((game: { id: number; sport: string; home_team: { name: string }; away_team: { name: string }; game_date: string | null }) => (
                <Link to="/predictions" key={game.id} className="prediction-row">
                  <span>{game.sport}</span>
                  <strong>{game.away_team.name} at {game.home_team.name}</strong>
                  <small>{game.game_date ? new Date(game.game_date).toLocaleString() : "TBD"}</small>
                </Link>
              ))}
            </div>
          </section>
        )}

        {activeTab === "roster" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>{league} what-if lab</span>
                <h2>Roster simulator</h2>
              </div>
              <Link to="/roster">Build roster</Link>
            </div>
            <div className="simulator-strip">
              <div>
                <span>Scenario</span>
                <strong>{league === "NBA" ? "Small-ball closing lineup" : "Pass-heavy two-minute drill"}</strong>
              </div>
              <div>
                <span>Projection</span>
                <strong>{topRosterPlayers.length ? `+${Math.round(topRosterPlayers[0].impact_score)} impact` : "Waiting for players"}</strong>
              </div>
            </div>
            <div className="roster-outlook">
              {topRosterPlayers.length === 0 && <p className="empty-state">No players loaded yet. Backfill box scores to unlock forecasts.</p>}
              {topRosterPlayers.map((player) => (
                <div key={player.id} className="roster-outlook-row">
                  <div>
                    <strong>{player.name}</strong>
                    <span>{player.team || "FA"} · {player.position || "UTIL"}</span>
                  </div>
                  <b>{player.impact_score}</b>
                </div>
              ))}
            </div>
          </section>
        )}

        {activeTab === "agents" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>Orchestration</span>
                <h2>Dashboard agents</h2>
              </div>
            </div>
            <AgentPanel />
          </section>
        )}
      </main>
    </div>
  );
}
