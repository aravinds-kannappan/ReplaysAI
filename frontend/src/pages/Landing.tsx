import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import "./Landing.css";

const SIGNALS = ["Live score", "Player tracking", "Clip intent", "Fan context"];
const TIMELINE = [
  { time: "Q3 8:14", label: "Run detected", detail: "BOS 14-2 swing tagged for recap" },
  { time: "Q4 2:06", label: "Reel cut", detail: "5 min explained version queued" },
  { time: "Post", label: "Fantasy impact", detail: "Roster delta moved +7.8" },
];
const LEAGUES = ["NBA", "NFL"];

export default function Landing() {
  return (
    <main className="landing-v3">
      <section className="vision-hero">
        <div className="hero-copy">
          <div className="brand-lockup">
            <img src="/replaysai-logo.svg" alt="" />
            <span>ReplaysAI</span>
          </div>
          <p className="hero-kicker">Personalized sports AI for NBA + NFL fans</p>
          <h1>Turn every game into a feed built around your teams.</h1>
          <p>
            ReplaysAI follows the teams you care about, detects the moments that changed the game,
            builds short or explained reels, and carries that context into picks, fantasy battles,
            roster planning, and a live assistant.
          </p>
          <div className="hero-actions">
            <SignedOut>
              <Link to="/sign-up">Get Started</Link>
              <Link to="/sign-in">Sign In</Link>
            </SignedOut>
            <SignedIn>
              <Link to="/feed">Open Dashboard</Link>
            </SignedIn>
          </div>
        </div>

        <div className="analysis-stage" aria-label="ReplaysAI agent interface preview">
          <div className="stage-topbar">
            <span>ReplaysAI Vision Room</span>
            <b>Live</b>
          </div>
          <div className="stage-body">
            <div className="tracking-window">
              <div className="field-grid" />
              {LEAGUES.map((league, index) => (
                <span key={league} className={`league-node league-node-${index + 1}`}>{league}</span>
              ))}
              <span className="ball-trace" />
              <span className="cut-marker">Clip</span>
            </div>
            <div className="signal-rail">
              {SIGNALS.map((signal) => <span key={signal}>{signal}</span>)}
            </div>
          </div>
          <div className="stage-footer">
            {TIMELINE.map((item) => (
              <div key={item.time} className="timeline-row">
                <span>{item.time}</span>
                <strong>{item.label}</strong>
                <p>{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-proof">
        <p>One fan graph powers the whole product</p>
        <div>
          <span>Teams</span>
          <span>Games</span>
          <span>Reels</span>
          <span>Picks</span>
          <span>Rosters</span>
          <span>Assistant</span>
        </div>
      </section>

      <section className="product-band">
        <div className="band-copy">
          <span>Video intelligence</span>
          <h2>Choose the replay length, not the work.</h2>
          <p>
            After live games, the reel tab is designed around 2, 5, and 10 minute cuts:
            quick pulse checks, story recaps, or fully explained breakdowns.
          </p>
        </div>
        <div className="reel-lab">
          <div className="reel-frame primary">Defining Run</div>
          <div className="reel-frame">Player Spotlight</div>
          <div className="reel-frame">Tactical Explain</div>
          <div className="duration-control">
            <span>2 min</span>
            <span>5 min</span>
            <span>10 min</span>
          </div>
        </div>
      </section>

      <section className="product-band inverse">
        <div className="matchup-lab">
          {["LAL", "BOS", "KC", "BUF"].map((team) => <b key={team}>{team}</b>)}
          <div className="matchup-line" />
        </div>
        <div className="band-copy">
          <span>Fantasy + predictions</span>
          <h2>Compare players, rosters, and future outcomes.</h2>
          <p>
            Picks, rosters, and leaders use the same team context as the feed, so every tab feels
            connected instead of separate dashboards stitched together.
          </p>
        </div>
      </section>
    </main>
  );
}
