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

function AssistantChat({ games }: { games: Game[] }) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "Ask about your teams, a live game, a player trend, or a roster what-if. I will use the games loaded in your dashboard first.",
    },
  ]);

  function respond(question: string) {
    const featured = games[0];
    const answer = featured
      ? `${formatGameTitle(featured)} is the best starting point. The dashboard has it marked ${featured.status}, with ${featured.away_score ?? 0}-${featured.home_score ?? 0} on the board. Next step: open the game card for the play timeline, recap, and fan-mode summary.`
      : "I do not see personalized games yet. Pick favorite teams in onboarding or run the historical backfill so I can ground answers in real game data.";

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

export default function Feed() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("feed");
  const { data: user } = useCurrentUser();
  const { data: feed, isLoading } = useFeed();
  const { data: liveGames } = useGames({ status: "live", limit: 12 });
  const { data: upcomingGames = [] } = useUpcomingGames();
  const { data: rosterPlayers = [] } = useRosterPlayers();

  const games: Game[] = feed?.games ?? [];
  const onboarded = feed?.onboarded ?? false;
  const favoriteCount = user?.favorite_teams?.length ?? 0;
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

  return (
    <div className="app-shell">
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
            <h1>{user?.display_name || user?.username || "Your sports dashboard"}</h1>
            <p>
              Personalized feed, live games, post-game summaries, picks, chat, and roster forecasts
              in one place.
            </p>
          </div>
          <div className="dashboard-stats">
            <DashboardStat label="Points" value={user?.total_points ?? 0} />
            <DashboardStat label="Streak" value={user?.login_streak ?? 0} />
            <DashboardStat label="Live" value={live.length} />
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

        {activeTab === "feed" && (
          <section className="dashboard-grid">
            <div className="dashboard-panel span-2">
              <div className="panel-heading">
                <div>
                  <span>{onboarded ? "For you" : "Recent games"}</span>
                  <h2>{onboarded ? "Personalized feed" : "Start with recent games"}</h2>
                </div>
                <Link to="/predictions">Make picks</Link>
              </div>
              {isLoading && <p className="loading-text">Loading games...</p>}
              {!isLoading && games.length === 0 && (
                <p className="empty-state">No games loaded yet. Run ingestion or pick teams to personalize the feed.</p>
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
                <span>Every 30 seconds</span>
                <h2>Live game feed</h2>
              </div>
            </div>
            {live.length === 0 ? (
              <p className="empty-state">No live games right now. Scheduled and final games still appear in your feed.</p>
            ) : (
              <div className="games-grid compact">
                {live.map((game) => <ScoreCard key={game.id} game={game} />)}
              </div>
            )}
          </section>
        )}

        {activeTab === "chat" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>Conversational layer</span>
                <h2>Ask ReplaysAI</h2>
              </div>
            </div>
            <AssistantChat games={games} />
          </section>
        )}

        {activeTab === "predictions" && (
          <section className="dashboard-panel">
            <div className="panel-heading">
              <div>
                <span>Forecast</span>
                <h2>Upcoming picks</h2>
              </div>
              <Link to="/predictions">Open picks</Link>
            </div>
            <div className="prediction-queue">
              {upcomingGames.length === 0 && <p className="empty-state">No scheduled games available for picks.</p>}
              {upcomingGames.slice(0, 6).map((game: { id: number; sport: string; home_team: { name: string }; away_team: { name: string }; game_date: string | null }) => (
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
                <span>What-if lab</span>
                <h2>Roster outlook</h2>
              </div>
              <Link to="/roster">Build roster</Link>
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
