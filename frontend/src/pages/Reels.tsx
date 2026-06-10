import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useGames } from "../hooks/useGames";
import ScoreCard from "../components/ScoreCard";
import { apiPath } from "../lib/api";

type League = "NBA" | "NFL";

const CV_TAGS = {
  NBA: ["Dunk", "Three", "Block", "Assist", "Clutch run", "Transition"],
  NFL: ["Touchdown", "Sack", "Interception", "Explosive pass", "Red zone", "Two-minute"],
};

export default function Reels() {
  const [league, setLeague] = useState<League>("NBA");
  const [mode, setMode] = useState<"studio" | "cuts" | "explain">("studio");
  const { data } = useGames({ sport: league, limit: 8 });
  const featuredGame = data?.games?.[0];
  const { data: reelData, isLoading: reelsLoading } = useQuery({
    queryKey: ["reel-cuts", featuredGame?.id],
    queryFn: () => axios.get(apiPath(`/api/games/${featuredGame?.id}/reels`)).then((r) => r.data),
    enabled: mode === "cuts" && !!featuredGame?.id,
  });
  const searchUrl = `https://www.google.com/search?q=${league}+highlights+today`;

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
              <h2>{featuredGame ? "2, 5, and 10 minute manifests" : "Choose a game source"}</h2>
            </div>
            {reelData?.video_url && <a href={reelData.video_url} target="_blank" rel="noreferrer">Open source</a>}
          </div>
          {reelsLoading && <p className="loading-text">Building cut manifests...</p>}
          {!featuredGame && <p className="empty-state">No game available for reel generation yet.</p>}
          <div className="summary-list">
            {reelData?.cuts?.map((cut: { label: string; status: string; estimated_seconds: number; segments: { description: string; clock: string; period: number; play_type: string }[] }) => (
              <div key={cut.label} className="summary-row">
                <strong>{cut.label} · {cut.status === "ready" ? `${cut.estimated_seconds}s selected` : "no segments"}</strong>
                <span>{cut.segments.slice(0, 2).map((segment) => `Q${segment.period} ${segment.clock} ${segment.play_type}: ${segment.description}`).join(" | ") || "ESPN has no eligible play labels for this cut yet."}</span>
              </div>
            ))}
          </div>
          {reelData?.rendering && (
            <p className="empty-state">{reelData.rendering.reason}</p>
          )}
        </section>
      )}

      <section className="dashboard-panel">
        <div className="panel-heading">
          <div>
            <span>Game source</span>
            <h2>Attach reels to real games</h2>
          </div>
        </div>
        <div className="games-grid compact">
          {(data?.games ?? []).map((game) => <ScoreCard key={game.id} game={game} />)}
        </div>
        {(!data?.games || data.games.length === 0) && (
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
