import { useState } from "react";
import { Link } from "react-router-dom";
import { useGames } from "../hooks/useGames";
import ScoreCard from "../components/ScoreCard";

type League = "NBA" | "NFL";

const CV_TAGS = {
  NBA: ["Dunk", "Three", "Block", "Assist", "Clutch run", "Transition"],
  NFL: ["Touchdown", "Sack", "Interception", "Explosive pass", "Red zone", "Two-minute"],
};

export default function Reels() {
  const [league, setLeague] = useState<League>("NBA");
  const { data } = useGames({ sport: league, limit: 8 });
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

      <section className="reels-stage">
        <div className="reel-screen">
          <div className="scan-line" />
          <div className="frame-target target-one" />
          <div className="frame-target target-two" />
          <div className="reel-copy">
            <span>Vision queue</span>
            <strong>{league === "NBA" ? "Late-clock shot, weak-side contest, bench reaction" : "Pocket pressure, release angle, safety rotation"}</strong>
            <p>CV agent extracts frames, labels play types, and hands the best moments to the recap agent.</p>
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
          <p className="empty-state">No {league} games loaded yet. The vision studio is ready once ingestion has games.</p>
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
