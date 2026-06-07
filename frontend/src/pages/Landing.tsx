import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import "./Landing.css";

const AGENTS = ["Ingest", "Vision", "Narrate", "Forecast", "Personalize"];
const PLAYS = ["Tatum pull-up three", "Mahomes deep shot", "SGA isolation", "McCaffrey red-zone cut"];

export default function Landing() {
  return (
    <main className="landing-v2">
      <section className="arena-hero">
        <div className="arena-copy">
          <div className="brand-lockup">
            <img src="/replaysai-logo.svg" alt="" />
            <span>ReplaysAI</span>
          </div>
          <div className="yc-pill">Built for YC-style sports intelligence</div>
          <p className="arena-kicker">Live sports, rebuilt around your teams</p>
          <h1>Every game becomes your own broadcast.</h1>
          <p>
            ReplaysAI watches NBA and NFL games, finds the moments that matter, cuts reels at the
            depth you choose, explains the game in plain English, and turns it into picks,
            fantasy matchups, and post-game memory.
          </p>
          <div className="arena-actions">
            <SignedOut>
              <Link to="/sign-up">Start with your teams</Link>
              <Link to="/sign-in">Sign in</Link>
            </SignedOut>
            <SignedIn>
              <Link to="/feed">Open command center</Link>
            </SignedIn>
          </div>
        </div>

        <div className="arena-system" aria-label="Agent system in motion">
          <div className="court-lines" />
          {AGENTS.map((agent, index) => (
            <span key={agent} className={`agent-token token-${index + 1}`}>{agent}</span>
          ))}
          <div className="reel-stack">
            <b>2 min</b>
            <b>5 min</b>
            <b>10 min</b>
          </div>
          <div className="play-stream">
            {PLAYS.map((play) => <i key={play}>{play}</i>)}
          </div>
        </div>
      </section>

      <section className="landing-flow">
        <div>
          <span>01</span>
          <strong>Pick teams once</strong>
          <p>The dashboard becomes editable, but your first login starts by activating your NBA/NFL graph.</p>
        </div>
        <div>
          <span>02</span>
          <strong>Agents retrieve context</strong>
          <p>Scores, players, schedules, reels, and news rails spin up around those teams.</p>
        </div>
        <div>
          <span>03</span>
          <strong>Watch smarter</strong>
          <p>Choose short, medium, or explained reels and carry the insight into picks and fantasy.</p>
        </div>
      </section>

      <section className="vision-sections">
        <div className="vision-copy">
          <span>Computer Vision</span>
          <h2>From full game to personal reel.</h2>
          <p>Choose a two-minute pulse check, a five-minute story, or a ten-minute explained cut after every live game.</p>
        </div>
        <div className="film-strip">
          {["Frame 0142", "Dunk", "Crowd shift", "Defining run"].map((item) => <b key={item}>{item}</b>)}
        </div>
      </section>

      <section className="vision-sections reverse">
        <div className="vision-copy">
          <span>Personalization</span>
          <h2>One survey starts the whole product.</h2>
          <p>Pick teams once. ReplaysAI builds the feed, reels, picks, roster battles, and leaderboard context around that graph.</p>
        </div>
        <div className="team-constellation">
          {["LAL", "BOS", "KC", "BUF", "DAL", "NYK"].map((team) => <b key={team}>{team}</b>)}
        </div>
      </section>
    </main>
  );
}
