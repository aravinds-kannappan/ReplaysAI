import { Link, useLocation } from "react-router-dom";
import { SignedIn, SignedOut, UserButton, useAuth } from "@clerk/clerk-react";
import { useNotifications } from "../hooks/useUser";

export default function Navbar() {
  const { pathname } = useLocation();
  const isLanding = pathname === "/";
  const { data: notifs } = useNotifications();
  const unread = (notifs ?? []).filter((n: { read: boolean }) => !n.read).length;

  return (
    <nav className={`navbar ${isLanding ? "navbar-transparent" : ""}`}>
      <Link to="/" className="navbar-logo">
        Replays<span>AI</span>
      </Link>

      <SignedIn>
        <div className="navbar-links">
          <Link to="/feed" className={pathname === "/feed" ? "active" : ""}>Feed</Link>
          <Link to="/predictions" className={pathname === "/predictions" ? "active" : ""}>Picks</Link>
          <Link to="/roster" className={pathname === "/roster" ? "active" : ""}>Roster</Link>
          <Link to="/leaderboard" className={pathname === "/leaderboard" ? "active" : ""}>Leaders</Link>
        </div>
        <div className="navbar-right">
          {unread > 0 && (
            <Link to="/profile" className="notif-badge">{unread}</Link>
          )}
          <UserButton afterSignOutUrl="/" />
        </div>
      </SignedIn>

      <SignedOut>
        <div className="navbar-right">
          <Link to="/sign-in" className="btn-ghost">Sign In</Link>
          <Link to="/sign-up" className="btn-primary">Get Started</Link>
        </div>
      </SignedOut>
    </nav>
  );
}
