import { Link } from "react-router-dom";
import { SignedIn, SignedOut } from "@clerk/clerk-react";

const FEATURES = [
  {
    icon: "🤖",
    title: "AI Recaps",
    desc: "Three parallel agents — event extraction, computer vision, and LLM summarization — generate your game recaps in seconds.",
  },
  {
    icon: "🎯",
    title: "Predictions",
    desc: "Pick winners before tipoff. Earn points for accuracy. Climb the leaderboard against fans nationwide.",
  },
  {
    icon: "🏀",
    title: "Fan Mode",
    desc: "Every recap rewritten from your team's perspective. Win or lose, get the story your team deserves.",
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
            <div className="mock-tag">NBA · FINAL</div>
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
              <span className="mock-label">🤖 AI Recap</span>
              <p>The Spurs opened strong with a 9-0 run in Q1, Wembanyama anchoring the paint...</p>
            </div>
            <div className="mock-badges">
              <span className="badge badge-live">🔥 7-day streak</span>
              <span className="badge badge-final">🔮 Prediction correct</span>
            </div>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="stats-bar">
        {STATS.map((s) => (
          <div key={s.label} className="stat-item">
            <span className="stat-value">{s.value}</span>
            <span className="stat-label">{s.label}</span>
          </div>
        ))}
      </section>

      {/* Features */}
      <section className="features-section">
        <h2>Everything serious fans need</h2>
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
        <div className="how-steps">
          <div className="how-step">
            <div className="step-num">01</div>
            <h4>Ingest</h4>
            <p>Real ESPN play-by-play data flows into PostgreSQL — every dunk, block, and turnover.</p>
          </div>
          <div className="how-arrow">→</div>
          <div className="how-step">
            <div className="step-num">02</div>
            <h4>Analyze</h4>
            <p>Three parallel agents: statistical extraction, CV video classification, and LLM summarization run concurrently.</p>
          </div>
          <div className="how-arrow">→</div>
          <div className="how-step">
            <div className="step-num">03</div>
            <h4>Personalize</h4>
            <p>Fan Mode rewrites every recap from your team's perspective. Win or lose, you get your story.</p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <h2>Join the fans who get it</h2>
        <p>No credit card. Set up in 60 seconds. Pick your team and start getting recaps your way.</p>
        <SignedOut>
          <Link to="/sign-up" className="btn-hero-primary">Create Free Account</Link>
        </SignedOut>
        <SignedIn>
          <Link to="/feed" className="btn-hero-primary">Go to My Feed →</Link>
        </SignedIn>
      </section>

      <footer className="landing-footer">
        <span>Replays AI · Built with Claude Sonnet + Computer Vision</span>
      </footer>
    </div>
  );
}
