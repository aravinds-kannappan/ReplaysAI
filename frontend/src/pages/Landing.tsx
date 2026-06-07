import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import heroImage from "../assets/hero.png";
import "./Landing.css";

const METRICS = [
  { value: "NBA + NFL", label: "sports graph" },
  { value: "10 seasons", label: "backfill target" },
  { value: "60 sec", label: "live refresh" },
  { value: "4 agents", label: "recap pipeline" },
];

const WORKFLOWS = [
  "Personal feed from favorite teams and players",
  "Live game stream that turns into post-game summaries",
  "Conversational assistant for what happened and what might happen next",
  "Roster simulator for future-season and what-if analysis",
];

const AGENTS = [
  { name: "Ingest", detail: "ESPN schedules, scores, plays, and box scores" },
  { name: "Detect", detail: "Momentum swings, key moments, player impact" },
  { name: "Explain", detail: "Recaps, fan angle, and post-game takeaways" },
  { name: "Predict", detail: "Picks, roster outlook, and future scenarios" },
];

const TICKER = ["BOS 112", "MIA 98", "KC 27", "BUF 24", "LAL 104", "DAL 99", "SF 31", "PHI 28"];

function ProductPreview() {
  return (
    <div className="product-preview" aria-label="Replays AI product preview">
      <div className="preview-topbar">
        <span className="preview-brand">ReplaysAI</span>
        <span className="preview-live">Live</span>
      </div>
      <div className="preview-ticker">
        {TICKER.map((item) => <span key={item}>{item}</span>)}
      </div>
      <div className="preview-body">
        <aside className="preview-rail">
          {["Feed", "Games", "Roster", "Picks"].map((item, index) => (
            <span key={item} className={index === 0 ? "active" : ""}>{item}</span>
          ))}
        </aside>
        <main className="preview-main">
          <div className="preview-game">
            <div>
              <span className="preview-label">Tonight</span>
              <strong>LAL vs BOS</strong>
            </div>
            <span className="preview-score">104-101</span>
          </div>
          <div className="preview-feed-item">
            <span className="preview-dot" />
            <p>ReplaysAI flags a 14-2 run and drafts a Celtics-focused recap.</p>
          </div>
          <div className="preview-grid">
            <div>
              <span>Win model</span>
              <strong>68%</strong>
            </div>
            <div>
              <span>Roster outlook</span>
              <strong>+11.4</strong>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="landing-copy">
          <p className="landing-kicker">Sports intelligence for the personalized fan era</p>
          <h1>ReplaysAI</h1>
          <p className="landing-subtitle">
            A sharper home for NBA and NFL fans where every live game becomes a personalized feed,
            a clear recap, a prediction surface, and a roster simulation.
          </p>
          <div className="landing-actions">
            <SignedOut>
              <Link to="/sign-up" className="landing-primary">Start tracking your teams</Link>
              <Link to="/sign-in" className="landing-secondary">Sign in</Link>
            </SignedOut>
            <SignedIn>
              <Link to="/feed" className="landing-primary">Open dashboard</Link>
            </SignedIn>
          </div>
          <div className="landing-proof">
            {METRICS.map((metric) => (
              <div key={metric.label}>
                <strong>{metric.value}</strong>
                <span>{metric.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="landing-visual">
          <img src={heroImage} alt="" className="hero-mark" />
          <ProductPreview />
        </div>
      </section>

      <section className="landing-section problem-section">
        <div>
          <p className="section-eyebrow">Why now</p>
          <h2>Sports content is everywhere. Personalized context is still missing.</h2>
        </div>
        <p>
          Fans do not just want scores. They want to know why the game moved, how it affects their
          teams, which players matter next, and what to do before the next matchup. ReplaysAI
          turns structured sports data into a daily command center for that loop.
        </p>
      </section>

      <section className="landing-section workflow-section">
        <div>
          <p className="section-eyebrow">Product</p>
          <h2>One dashboard after login. Four daily jobs.</h2>
        </div>
        <div className="workflow-list">
          {WORKFLOWS.map((workflow) => (
            <div key={workflow} className="workflow-row">
              <span />
              <p>{workflow}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section agent-section">
        <div>
          <p className="section-eyebrow">System</p>
          <h2>Agents handle the dashboard, not just the recap.</h2>
        </div>
        <div className="agent-grid">
          {AGENTS.map((agent, index) => (
            <div key={agent.name} className="agent-card">
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{agent.name}</strong>
              <p>{agent.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section cta-band">
        <div>
          <p className="section-eyebrow">Next game</p>
          <h2>Follow teams, build a roster, and let the app explain the season as it unfolds.</h2>
        </div>
        <SignedOut>
          <Link to="/sign-up" className="landing-primary">Create account</Link>
        </SignedOut>
        <SignedIn>
          <Link to="/feed" className="landing-primary">Go to dashboard</Link>
        </SignedIn>
      </section>
    </div>
  );
}
