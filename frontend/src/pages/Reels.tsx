import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useGames } from "../hooks/useGames";
import { useFeed } from "../hooks/usePredictions";
import { getLocalFavoriteTeams } from "../hooks/useUser";
import ScoreCard from "../components/ScoreCard";
import ReelPlayer, { type Clip, type Playlist } from "../components/ReelPlayer";
import { apiPath } from "../lib/api";
import type { Game } from "../types";

type League = "NBA" | "NFL";

type Cut = {
  label: string;
  duration_seconds: number;
  estimated_seconds: number;
  status: string;
  clips: Clip[];
  segments: { description: string; clock: string; period: number; play_type: string }[];
};

const CV_TAGS = {
  NBA: ["Dunk", "Three", "Block", "Assist", "Clutch run", "Transition"],
  NFL: ["Touchdown", "Sack", "Interception", "Explosive pass", "Red zone", "Two-minute"],
};

function ReelAgentChat({ gameId, onReel }: { gameId: number; onReel: (playlist: Playlist) => void }) {
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<{ role: "user" | "assistant"; text: string }[]>([
    {
      role: "assistant",
      text: "What kind of reel do you want from this game? Tell me who or what to feature and how long it should be — or just say \"surprise me\".",
    },
  ]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const prompt = draft.trim();
    if (!prompt || loading) return;
    setDraft("");
    const history = [...log, { role: "user" as const, text: prompt }];
    setLog(history);
    setLoading(true);
    try {
      const res = await axios.post(apiPath(`/api/games/${gameId}/reels/generate`), {
        prompt,
        messages: history,
      });
      if (res.data.action === "ask") {
        setLog((prev) => [...prev, { role: "assistant", text: res.data.question }]);
      } else {
        const { label, clips, note, estimated_seconds } = res.data as Playlist & { note: string; estimated_seconds: number };
        setLog((prev) => [...prev, { role: "assistant", text: `${note} Playing ${clips.length} clips (~${estimated_seconds}s).` }]);
        if (clips?.length) onReel({ label: label || prompt, clips });
      }
    } catch {
      setLog((prev) => [...prev, {
        role: "assistant",
        text: "I couldn't build that reel — ESPN may not have published video clips for this game yet. Try a recently finished game.",
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-shell reel-agent">
      <div className="chat-log">
        {log.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>{message.text}</div>
        ))}
      </div>
      <form className="chat-form" onSubmit={submit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="e.g. 2 minute reel of Wembanyama plays..."
        />
        <button type="submit" disabled={loading}>{loading ? "..." : "Send"}</button>
      </form>
    </div>
  );
}

export default function Reels() {
  const [league, setLeague] = useState<League>("NBA");
  const [mode, setMode] = useState<"studio" | "cuts" | "explain">("studio");
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const { data } = useGames({ sport: league, limit: 8 });
  const { data: feed } = useFeed();

  // Favorite-team games come first: the feed is already filtered to the teams
  // picked in onboarding, so reels build around them by default.
  const hasFavorites = getLocalFavoriteTeams().length > 0;
  const favoriteGames = ((feed?.games ?? []) as Game[]).filter((game) => game.sport === league);
  const leagueGames = data?.games ?? [];
  const sourceGames = hasFavorites && favoriteGames.length > 0 ? favoriteGames : leagueGames;
  // Scheduled games have no highlight clips yet, so default to the latest
  // finished or live game unless the user explicitly picks one.
  const playableGames = sourceGames.filter((game) => game.status !== "scheduled");
  const featuredGame = sourceGames.find((game) => game.id === selectedGameId) ?? playableGames[0] ?? sourceGames[0];

  // Cut manifests are built as soon as a game is featured (often already
  // prefetched by onboarding), not only after the cuts tab is opened.
  const { data: reelData, isLoading: reelsLoading } = useQuery({
    queryKey: ["reel-cuts", featuredGame?.id],
    queryFn: () => axios.get(apiPath(`/api/games/${featuredGame?.id}/reels`)).then((r) => r.data),
    enabled: !!featuredGame?.id,
    staleTime: 300_000,
  });
  const searchUrl = `https://www.google.com/search?q=${league}+highlights+today`;
  const featuredTitle = featuredGame
    ? `${featuredGame.away_team.abbreviation} @ ${featuredGame.home_team.abbreviation}`
    : "";

  function playCut(cut: Cut) {
    if (!cut.clips?.length) return;
    setPlaylist({ label: `${cut.label} — ${featuredTitle}`, clips: cut.clips });
  }

  return (
    <div className={`experience-page league-${league.toLowerCase()}`}>
      <header className="experience-hero">
        <div>
          <p className="dashboard-kicker">Computer vision studio</p>
          <h1>{league} reels without the noise</h1>
          <p>Find the important frames, classify the moment, then turn the clip into a recap, prediction, or player comparison.</p>
        </div>
        <div className="league-switch">
          {(["NBA", "NFL"] as League[]).map((item) => (
            <button key={item} className={league === item ? "active" : ""} onClick={() => setLeague(item)}>{item}</button>
          ))}
        </div>
      </header>

      <div className="inner-tabs">
        {[
          ["studio", "Vision Studio"],
          ["cuts", "2 / 5 / 10 Min Cuts"],
          ["explain", "Explain The Game"],
        ].map(([id, label]) => (
          <button key={id} className={mode === id ? "active" : ""} onClick={() => setMode(id as typeof mode)}>{label}</button>
        ))}
      </div>

      <section className="reels-stage">
        <div className="reel-screen">
          <div className="scan-line" />
          <div className="frame-target target-one" />
          <div className="frame-target target-two" />
          <div className="reel-copy">
            <span>Vision queue</span>
            <strong>
              {mode === "cuts"
                ? "Generate a short reel, full story reel, or detailed film-room cut"
                : mode === "explain"
                  ? "Slow the game down and explain why each moment mattered"
                  : league === "NBA" ? "Late-clock shot, weak-side contest, bench reaction" : "Pocket pressure, release angle, safety rotation"}
            </strong>
            <p>{mode === "studio" ? "CV agent extracts frames, labels play types, and hands the best moments to the recap agent." : "The fan chooses how detailed the reel should be, and the agent changes clip length plus narration depth."}</p>
          </div>
        </div>
        <aside className="reel-controls">
          <strong>Moment classifier</strong>
          <div className="cv-tags">
            {CV_TAGS[league].map((tag) => <span key={tag}>{tag}</span>)}
          </div>
          <a href={searchUrl} target="_blank" rel="noreferrer" className="btn-primary">Search highlight streams</a>
          <a href={`https://www.espn.com/${league.toLowerCase()}/`} target="_blank" rel="noreferrer" className="btn-ghost">Open ESPN video hub</a>
        </aside>
      </section>

      {mode === "cuts" && (
        <section className="dashboard-panel">
          <div className="panel-heading">
            <div>
              <span>Generated reel cuts</span>
              <h2>{featuredGame ? `${featuredTitle} — 2, 5, and 10 minute reels` : "Choose a game source"}</h2>
            </div>
          </div>

          {playlist && <ReelPlayer playlist={playlist} onClose={() => setPlaylist(null)} />}

          {reelsLoading && <p className="loading-text">Building reels from ESPN clips...</p>}
          {!featuredGame && <p className="empty-state">No game available for reel generation yet.</p>}
          <div className="summary-list">
            {(reelData?.cuts as Cut[] | undefined)?.map((cut) => (
              <div key={cut.label} className="summary-row reel-cut-row">
                <div>
                  <strong>
                    {cut.label} · {cut.clips?.length
                      ? `${cut.clips.length} clips · ${cut.estimated_seconds}s of video`
                      : cut.status === "ready" ? `${cut.estimated_seconds}s manifest` : "no segments"}
                  </strong>
                  <span>
                    {cut.clips?.length
                      ? cut.clips.slice(0, 2).map((clip) => clip.headline).join(" | ")
                      : cut.segments.slice(0, 2).map((segment) => `Q${segment.period} ${segment.clock} ${segment.play_type}: ${segment.description}`).join(" | ") || "ESPN has no eligible play labels for this cut yet."}
                  </span>
                </div>
                {cut.clips?.length > 0 && (
                  <button className="btn-primary reel-play-btn" onClick={() => playCut(cut)}>▶ Play reel</button>
                )}
              </div>
            ))}
          </div>
          {reelData && reelData.clip_count === 0 && (
            <p className="empty-state">{reelData.rendering?.reason}</p>
          )}

          <div className="panel-heading reel-agent-heading">
            <div>
              <span>Reel agent</span>
              <h2>Ask for the exact reel you want</h2>
            </div>
          </div>
          {featuredGame && <ReelAgentChat key={featuredGame.id} gameId={featuredGame.id} onReel={setPlaylist} />}
        </section>
      )}

      <section className="dashboard-panel">
        <div className="panel-heading">
          <div>
            <span>Game source</span>
            <h2>{hasFavorites && favoriteGames.length > 0 ? "Your teams' games" : "Attach reels to real games"}</h2>
          </div>
        </div>
        <div className="games-grid compact">
          {sourceGames.map((game) => (
            <div key={game.id} className={`reel-source${featuredGame?.id === game.id ? " selected" : ""}`}>
              <ScoreCard game={game} />
              <button
                className="btn-ghost"
                onClick={() => {
                  setSelectedGameId(game.id);
                  setPlaylist(null);
                  setMode("cuts");
                }}
              >
                {featuredGame?.id === game.id ? "Cuts shown above" : "Build 2/5/10 reels"}
              </button>
            </div>
          ))}
        </div>
        {sourceGames.length === 0 && (
          <p className="empty-state">No {league} games returned yet. Stored ingestions and ESPN public schedules will appear here as soon as either source has games.</p>
        )}
      </section>

      <section className="agent-motion-row">
        {["Search", "Extract", "Classify", "Summarize"].map((step) => (
          <div key={step} className="motion-node">
            <span />
            <strong>{step}</strong>
          </div>
        ))}
        <Link to="/feed" className="motion-link">Send to feed</Link>
      </section>
    </div>
  );
}
