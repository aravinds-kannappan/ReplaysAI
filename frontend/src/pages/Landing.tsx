import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";
import "./Landing.css";

const FEATURES = [
  {
    icon: "🤖",
    title: "AI Recaps",
    desc: "Three parallel agents — event extraction, computer vision, and LLM summarization — generate your game recaps in seconds.",
  },
  {
    icon: "🏀",
    title: "Fan Mode",
    desc: "Every recap rewritten from your team's perspective. Win or lose, get the story your team deserves.",
  },
  {
    icon: "🎯",
    title: "Predictions",
    desc: "Pick winners before tipoff. Earn points for accuracy. Climb the leaderboard against fans nationwide.",
  },
  {
    icon: "📊",
    title: "Roster Builder",
    desc: "Build a weekly roster of players. Track their performance across real play-by-play data.",
  },
];

const STATS = [
  { value: "5,597", label: "Plays Tracked" },
  { value: "11", label: "Games Ingested" },
  { value: "3", label: "AI Agents" },
  { value: "2", label: "Sports" },
];

export default function Landing() {
  return (
    <div className="landing">
      {/* Hero */}
      <section className="hero-section">
        {/* Extra floating orb */}
        <div className="hero-orb-extra" />

        <div className="hero-content">
          <div className="hero-badge">NBA · NFL · AI-Powered</div>
          <h1>
            Your team's game.<br />
            <span className="accent">Your AI. Your recap.</span>
          </h1>
          <p className="hero-sub">
            Replays AI combines multimodal AI — computer vision, LLMs, and real play-by-play data —
            to deliver personalized game recaps, smart predictions, and fan-mode highlights.
          </p>
          <div className="hero-ctas">
            <SignedOut>
              <Link to="/sign-up" className="btn-hero-primary">Get Started Free</Link>
              <Link to="/sign-in" className="btn-hero-ghost">Sign In</Link>
            </SignedOut>
            <SignedIn>
              <Link to="/feed" className="btn-hero-primary">Go to My Feed →</Link>
            </SignedIn>
          </div>
        </div>

        <div className="hero-visual">
          <div className="mock-card">
            <div className="mock-tag">NBA · Playoffs · Final</div>
            <div className="mock-teams">
              <div className="mock-team">
                <span className="mock-abbr">SAS</span>
                <span className="mock-score accent">111</span>
              </div>
              <span className="mock-at">@</span>
              <div className="mock-team">
                <span className="mock-abbr">OKC</span>
                <span className="mock-score">103</span>
              </div>
            </div>
            <div className="mock-recap-preview">
              <span className="mock-label">🤖 AI Recap · Fan Mode</span>
              <p>The Spurs opened strong with a 9-0 run in Q1, Wembanyama anchoring the paint with two early blocks that set the tone...</p>
            </div>
            <div className="mock-badges">
              <span className="badge badge-live">🔥 7-day streak</span>
              <span className="badge badge-final">🔮 Prediction correct</span>
            </div>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <div className="stats-bar">
        <div className="stats-bar-inner">
          {STATS.map((s) => (
            <div key={s.label} className="stat-item">
              <span className="stat-value">{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Features */}
      <section className="features-section">
        <h2>Everything serious fans need</h2>
        <p className="section-sub">Real data. Real AI. Built for fans who want more than a box score.</p>
        <div className="features-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature-card">
              <span className="feature-icon">{f.icon}</span>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="how-section">
        <h2>Powered by real multimodal AI</h2>
        <p className="section-sub">Three specialized agents run in parallel so your recap arrives fast.</p>
        <div className="how-steps">
          <div className="how-step">
            <div className="step-num">01 · Ingest</div>
            <h4>Real Play-by-Play</h4>
            <p>ESPN play-by-play data flows into PostgreSQL — every dunk, block, and turnover, stored as structured events.</p>
          </div>
          <div className="how-arrow">→</div>
          <div className="how-step">
            <div className="step-num">02 · Analyze</div>
            <h4>Three Parallel Agents</h4>
            <p>Statistical extraction, CV video classification, and LLM summarization run concurrently via asyncio — no waiting in line.</p>
          </div>
          <div className="how-arrow">→</div>
          <div className="how-step">
            <div className="step-num">03 · Personalize</div>
            <h4>Your Team's Story</h4>
            <p>Fan Mode rewrites the recap from your team's perspective. Win or lose, you get the honest story your fans deserve.</p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <h2>Join fans who get it</h2>
        <p>No credit card. Pick your team in 60 seconds. Your personalized feed starts immediately.</p>
        <SignedOut>
          <Link to="/sign-up" className="btn-hero-primary">Create Free Account</Link>
        </SignedOut>
        <SignedIn>
          <Link to="/feed" className="btn-hero-primary">Go to My Feed →</Link>
        </SignedIn>
      </section>

      <footer className="landing-footer">
        Replays AI · Built with Claude Sonnet + Computer Vision
      </footer>
    </div>
  );
}
