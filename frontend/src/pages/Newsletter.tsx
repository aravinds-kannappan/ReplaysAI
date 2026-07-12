import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import axios from "axios";
import { apiPath } from "../lib/api";
import { useCurrentUser } from "../hooks/useUser";
import { getDeviceId } from "../lib/device";
import "./ReelsBroadcastNewsletter.css";

type Newsletter = {
  id?: string;
  user_id: string;
  week_key: string;
  content_md: string;
  teams_snapshot?: unknown;
  share_token?: string;
  source?: string;      // "trained" | "llm" | "fallback"
  curation?: string;    // e.g. "heuristic curation ranker"
  created_at?: string;
};

// Honest provenance label: never claim "trained" or a model that did not run.
function sourceLabel(source?: string): string {
  if (source === "trained") return "Trained newsletter writer";
  if (source === "llm") return "Claude (LLM)";
  return "Deterministic writer (data only)";
}

function currentWeekKey(): string {
  const d = new Date();
  const jan1 = new Date(d.getFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - jan1.getTime()) / 86400000 + jan1.getDay() + 1) / 7);
  return `${d.getFullYear()}-W${String(week).padStart(2, "0")}`;
}

export function NewsletterShare() {
  const { token } = useParams<{ token: string }>();
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    axios
      .get(apiPath(`/api/newsletter/share/${token}`))
      .then((r) => setNewsletter(r.data as Newsletter))
      .catch(() => setNewsletter(null))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="nl-loading">Loading shared newsletter…</div>;
  if (!newsletter) return <div className="nl-not-found">Newsletter not found or link has expired.</div>;

  return (
    <div className="nl-page nl-shared">
      <div className="nl-shell">
      <div className="nl-masthead">
        <div className="nl-masthead-logo">ReplaysAI Weekly</div>
        <div className="nl-masthead-meta">{newsletter.week_key} · Shared digest</div>
      </div>
      <div className="nl-body">
        <div className="nl-content">
          <ReactMarkdown>{newsletter.content_md}</ReactMarkdown>
        </div>
      </div>
      <div className="nl-shared-footer">
        <p>Want your own personalized sports newsletter? <Link to="/">Try ReplaysAI →</Link></p>
      </div>
      </div>
    </div>
  );
}

export default function NewsletterPage() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [generating, setGenerating] = useState(false);
  const [weekKey] = useState(currentWeekKey);
  const [copied, setCopied] = useState(false);

  const userId = getDeviceId();
  const favoriteTeams = (user?.favorite_teams ?? []).map(
    (t: { sport: string; abbreviation: string }) => `${t.sport}:${t.abbreviation}`,
  );
  const followedPlayers = (user?.followed_players ?? []).map(
    (p: { name: string }) => p.name,
  );

  async function generate() {
    if (!userId) return;
    setGenerating(true);
    try {
      const res = await axios.post(apiPath("/api/newsletter/generate"), {
        user_id: userId,
        display_name: user?.display_name ?? null,
        favorite_teams: favoriteTeams,
        followed_players: followedPlayers,
        week_key: weekKey,
      });
      // The backend persists the issue (Redis, when configured) and returns a
      // share_token for the public link. Render the returned digest directly.
      setNewsletter(res.data as Newsletter);
    } finally {
      setGenerating(false);
    }
  }

  async function copyShareLink() {
    if (!newsletter?.share_token) return;
    const url = `${window.location.origin}/newsletter/share/${newsletter.share_token}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function printNewsletter() {
    window.print();
  }

  return (
    <div className="nl-page">
      <div className="nl-shell">
      <header className="nl-header no-print">
        <button className="nl-back btn-ghost" onClick={() => navigate("/feed")}>← Dashboard</button>
        <div className="nl-header-actions">
          {newsletter && (
            <>
              {newsletter.share_token && (
                <button className="btn-ghost" onClick={copyShareLink}>
                  {copied ? "Copied!" : "Share link"}
                </button>
              )}
              <button className="btn-ghost" onClick={printNewsletter}>Download PDF</button>
            </>
          )}
          {favoriteTeams.length === 0 ? (
            <Link to="/demo" className="btn-primary">Pick teams first →</Link>
          ) : (
            <button className="btn-primary" disabled={generating} onClick={() => void generate()}>
              {generating ? "Writing…" : newsletter ? "Regenerate" : "Generate newsletter"}
            </button>
          )}
        </div>
      </header>

      {generating && (
        <div className="nl-generating">
          <div className="nl-gen-spinner" />
          <h3>Writing your newsletter</h3>
          <p>Pulling results, stats, and hot takes. About 10 seconds.</p>
        </div>
      )}

      {!generating && !newsletter && (
        <div className="nl-empty">
          <div className="nl-empty-eyebrow">Weekly digest</div>
          <h2>Your teams.<br /><span>Your story.</span></h2>
          <p>
            A personalized newsletter covering your teams' results, player stats, upcoming
            games, and analytical takes. Curated and written fresh for you every week.
          </p>
          {favoriteTeams.length === 0 ? (
            <Link to="/demo" className="btn-primary">Pick your teams first →</Link>
          ) : (
            <button className="btn-primary" onClick={() => void generate()}>
              Generate this week's newsletter
            </button>
          )}
          <div className="nl-preview-teams">
            {favoriteTeams.slice(0, 6).map((t) => (
              <span key={t} className="nl-team-chip">{t.split(":")[1]}</span>
            ))}
          </div>
        </div>
      )}

      {!generating && newsletter && (
        <div className="nl-body">
          <div className="nl-masthead">
            <div className="nl-masthead-logo">ReplaysAI Weekly</div>
            <div className="nl-masthead-meta">
              {newsletter.week_key} · {user?.display_name ?? "Your digest"}
              {newsletter.share_token && (
                <span className="nl-share-badge" onClick={() => void copyShareLink()} title="Click to copy share link">
                  Shareable
                </span>
              )}
            </div>
            <div className="nl-masthead-teams no-print">
              {favoriteTeams.map((t) => <span key={t} className="nl-team-chip">{t.split(":")[1]}</span>)}
            </div>
          </div>

          <div className="nl-content">
            <ReactMarkdown>{newsletter.content_md}</ReactMarkdown>
          </div>

          <div className="nl-footer no-print">
            <p>
              {sourceLabel(newsletter.source)}
              {newsletter.curation ? ` · ${newsletter.curation}` : ""} · real ESPN data · {newsletter.week_key}
            </p>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
