import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/clerk-react";
import axios from "axios";
import { apiPath } from "../lib/api";
import { useGame } from "../hooks/useGames";
import { useCurrentUser } from "../hooks/useUser";
import { useCreatePrediction } from "../hooks/usePredictions";
import RecapViewer from "../components/RecapViewer";
import HighlightReel from "../components/HighlightReel";
import PlayTimeline from "../components/PlayTimeline";

type Tab = "recap" | "fan" | "reels" | "plays";

async function authFetch(getToken: () => Promise<string | null>, url: string, options: Record<string, unknown> = {}) {
  const token = await getToken();
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await axios({ url: apiPath(url), headers, ...options });
  return res.data;
}

export default function GameDetail() {
  const { id } = useParams<{ id: string }>();
  const gameId = Number(id);
  const { data: game, isLoading } = useGame(gameId);
  const { data: user } = useCurrentUser();
  const { getToken } = useAuth();
  const [tab, setTab] = useState<Tab>("recap");
  const [fanGenerating, setFanGenerating] = useState(false);
  const qc = useQueryClient();
  const createPrediction = useCreatePrediction();
  const [picked, setPicked] = useState<number | null>(null);

  // Which of the user's favorite teams is playing in this game — the fan recap
  // is written from that team's perspective.
  const favTeams = (user?.favorite_teams ?? []) as { id: number; sport: string; abbreviation: string | null }[];
  const fanTeamAbbr = game
    ? favTeams.find((t) =>
        t.sport === game.sport &&
        (t.abbreviation === game.home_team.abbreviation || t.abbreviation === game.away_team.abbreviation),
      )?.abbreviation ?? null
    : null;

  const { data: fanRecap } = useQuery({
    queryKey: ["fan-recap", gameId, fanTeamAbbr],
    queryFn: () =>
      authFetch(getToken, `/api/games/${gameId}/fan-recap`, { params: fanTeamAbbr ? { team: fanTeamAbbr } : {} }),
    enabled: tab === "fan",
  });

  async function generateFanRecap() {
    setFanGenerating(true);
    try {
      await authFetch(getToken, `/api/games/${gameId}/fan-recap/generate`, {
        method: "post",
        params: fanTeamAbbr ? { team: fanTeamAbbr } : {},
      });
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await qc.invalidateQueries({ queryKey: ["fan-recap", gameId, fanTeamAbbr] });
        const data = qc.getQueryData<{ content: string | null }>(["fan-recap", gameId, fanTeamAbbr]);
        if (data?.content || attempts > 24) {
          clearInterval(poll);
          setFanGenerating(false);
        }
      }, 5000);
    } catch {
      setFanGenerating(false);
    }
  }

  function handlePick(winnerId: number) {
    if (!game || game.status === "final") return;
    setPicked(winnerId);
    createPrediction.mutate({ game_id: gameId, predicted_winner_team_id: winnerId });
  }

  if (isLoading) return <div className="page-center">Loading game…</div>;
  if (!game) return <div className="page-center">Game not found.</div>;

  const dateLabel = game.game_date
    ? new Date(game.game_date).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })
    : "";

  const userFavTeams = (user?.favorite_teams ?? []) as { id: number; sport: string; abbreviation: string | null }[];
  const userFavTeamIds = new Set(userFavTeams.map((t) => t.id));
  const userFavTeamKeys = new Set(userFavTeams.map((t) => `${t.sport}:${t.abbreviation}`));
  const userHasTeamInGame =
    userFavTeamIds.has(game.home_team.id ?? 0) ||
    userFavTeamIds.has(game.away_team.id ?? 0) ||
    userFavTeamKeys.has(`${game.sport}:${game.home_team.abbreviation}`) ||
    userFavTeamKeys.has(`${game.sport}:${game.away_team.abbreviation}`);

  return (
    <div className="page-game-detail">
      <Link to="/feed" className="back-link">← Back to Feed</Link>

      <div className="game-header">
        <div className="game-sport-date">
          <span className="sport-tag">{game.sport}</span>
          <span className="game-date">{dateLabel}</span>
          <span className={`badge badge-${game.status}`}>{game.status.toUpperCase()}</span>
        </div>

        <div className="scoreboard">
          <div className="scoreboard-team">
            <span className="sb-abbr">{game.away_team.abbreviation}</span>
            <span className="sb-name">{game.away_team.name}</span>
            <span className={`sb-score ${(game.away_score ?? 0) > (game.home_score ?? 0) ? "score-winner" : ""}`}>
              {game.status === "scheduled" ? "—" : game.away_score ?? "—"}
            </span>
          </div>
          <div className="scoreboard-divider">@</div>
          <div className="scoreboard-team">
            <span className="sb-abbr">{game.home_team.abbreviation}</span>
            <span className="sb-name">{game.home_team.name}</span>
            <span className={`sb-score ${(game.home_score ?? 0) > (game.away_score ?? 0) ? "score-winner" : ""}`}>
              {game.status === "scheduled" ? "—" : game.home_score ?? "—"}
            </span>
          </div>
        </div>

        {/* Quick prediction for upcoming games */}
        {game.status === "scheduled" && (
          <div className="game-prediction">
            <p className="pred-prompt">Who wins?</p>
            <div className="pred-btns">
              <button
                className={`pred-btn ${picked === game.away_team.id ? "selected" : ""}`}
                onClick={() => handlePick(game.away_team.id!)}
                disabled={!!picked}
              >
                {game.away_team.abbreviation}
              </button>
              <button
                className={`pred-btn ${picked === game.home_team.id ? "selected" : ""}`}
                onClick={() => handlePick(game.home_team.id!)}
                disabled={!!picked}
              >
                {game.home_team.abbreviation}
              </button>
            </div>
            {picked && <p className="pred-submitted">Pick locked ✓ +10 pts</p>}
          </div>
        )}
      </div>

      <div className="tab-bar">
        {(["recap", ...(userHasTeamInGame ? ["fan"] : []), "reels", "plays"] as Tab[]).map((t) => (
          <button key={t} className={`tab-btn ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t === "fan" ? "My Team" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {tab === "recap" && <RecapViewer gameId={gameId} gameStatus={game.status} />}
        {tab === "fan" && (
          <div className="fan-recap">
            {fanRecap?.content ? (
              <div className="recap-content fan-recap-content">
                <div className="fan-badge">🏀 Your Team's Perspective</div>
                <ReactMarkdown>{fanRecap.content}</ReactMarkdown>
              </div>
            ) : (
              <div className="recap-placeholder">
                <p>Get a recap written just for your team's fans.</p>
                <button className="btn-generate" onClick={generateFanRecap} disabled={fanGenerating}>
                  {fanGenerating ? "Generating fan recap… (~10s)" : "Generate My Team's Recap"}
                </button>
              </div>
            )}
          </div>
        )}
        {tab === "reels" && <HighlightReel gameId={gameId} />}
        {tab === "plays" && <PlayTimeline gameId={gameId} />}
      </div>
    </div>
  );
}
