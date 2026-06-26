import { Link, useLocation } from "react-router-dom";

// The global navbar is hidden anywhere a surface already owns its chrome:
//  • the landing page renders its own .lp-nav
//  • the dashboard has a left sidebar
//  • full-screen feature pages (reels, broadcast, newsletter, dream team) each
//    have their own header with a back link
// That leaves only the lightweight "detail" pages (demo, game, player, profile),
// where a slim top bar back to the dashboard is genuinely useful.
const HIDE_EXACT = new Set([
  "/",
  "/feed", "/dashboard", "/season", "/games", "/stats", "/extras", "/picks",
  "/predictions", "/roster", "/news", "/chat", "/leaderboard",
  "/reels", "/newsletter", "/dream-team",
]);
const HIDE_PREFIX = ["/broadcast/", "/reel/", "/newsletter/share/"];

export default function Navbar() {
  const { pathname } = useLocation();
  if (HIDE_EXACT.has(pathname) || HIDE_PREFIX.some((p) => pathname.startsWith(p))) return null;

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-logo">
        <img src="/replaysai-logo.svg" alt="" />
        Replays<span>AI</span>
      </Link>

      <div className="navbar-right">
        <Link to="/feed" className="btn-ghost">Dashboard</Link>
        <Link to="/demo" className="btn-ghost">Edit teams</Link>
      </div>
    </nav>
  );
}
