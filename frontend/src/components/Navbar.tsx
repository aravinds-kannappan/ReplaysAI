import { Link, useLocation } from "react-router-dom";

// The dashboard has its own left sidebar nav, so the top navbar is hidden there
// to avoid showing the same tabs twice.
const DASHBOARD_ROUTES = new Set([
  "/feed", "/dashboard", "/season", "/games", "/reels", "/extras", "/picks",
  "/predictions", "/roster", "/news", "/chat", "/leaderboard", "/stats",
]);

export default function Navbar() {
  const { pathname } = useLocation();
  const isLanding = pathname === "/";

  if (DASHBOARD_ROUTES.has(pathname)) return null;

  return (
    <nav className={`navbar ${isLanding ? "navbar-transparent" : ""}`}>
      <Link to="/" className="navbar-logo">
        <img src="/replaysai-logo.svg" alt="" />
        Replays<span>AI</span>
      </Link>

      <div className="navbar-right">
        {isLanding ? (
          <Link to="/demo" className="btn-primary">Try Demo</Link>
        ) : (
          <>
            <Link to="/feed" className="btn-ghost">Dashboard</Link>
            <Link to="/demo" className="btn-ghost">Edit teams</Link>
          </>
        )}
      </div>
    </nav>
  );
}
