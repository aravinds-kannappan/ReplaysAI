import { useCallback, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";
import { useCurrentUser } from "../hooks/useUser";
import StoryReelPlayer, { type Story } from "../components/StoryReelPlayer";
import ReelPlayer, { type Clip } from "../components/ReelPlayer";
import "./ReelsBroadcastNewsletter.css";

type IntentResult = {
  game_id: number | null;
  sport: string | null;
  focus: string;
  seconds: number;
  confidence: number;
  game_label: string;
  candidates: { id: number; label: string; date: string; score: string }[];
  intent_source: string;
};

type ReelCut = {
  label: string;
  target_seconds: number;
  blurb: string;
  clip_count: number;
  duration_seconds: number;
  clips: Clip[];
};

type NarrationData = {
  explainer: string;
  voice_script: string;
  voice_source: string;
};

const QUICK_PROMPTS = [
  "Last game for my teams",
  "2-min recap",
  "5-min story",
  "10-min deep cut",
  "Best plays this week",
  "Build a broadcast",
];

const TIER_LABELS: Record<number, string> = { 120: "2 min story", 300: "5 min story", 600: "10 min story" };

export default function ReelsPage() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();
  const [prompt, setPrompt] = useState("");
  const [resolving, setResolving] = useState(false);
  const [intent, setIntent] = useState<IntentResult | null>(null);
  const [confirmedGameId, setConfirmedGameId] = useState<number | null>(null);
  const [confirmedSeconds, setConfirmedSeconds] = useState(300);
  const [story, setStory] = useState<Story | null>(null);
  const [playlist, setPlaylist] = useState<{ label: string; clips: Clip[] } | null>(null);
  const [narration, setNarration] = useState<NarrationData | null>(null);
  const [loadingNarration, setLoadingNarration] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const favoriteTeams = (user?.favorite_teams ?? []).map(
    (t: { sport: string; abbreviation: string }) => `${t.sport}:${t.abbreviation}`,
  );
  const followedPlayers = (user?.followed_players ?? []).map(
    (p: { name: string }) => p.name,
  );

  const gameId = confirmedGameId ?? intent?.game_id;

  const { data: reelData, isLoading: reelLoading } = useQuery({
    queryKey: ["reel-cuts", gameId],
    queryFn: () => axios.get(apiPath(`/api/games/${gameId}/reels`)).then((r) => r.data),
    enabled: !!gameId,
    staleTime: 300_000,
  });

  const cuts: ReelCut[] = reelData?.cuts ?? [];
  const activeCut = cuts.find((c) => c.target_seconds === confirmedSeconds) ?? cuts[0];

  const resolveIntent = useCallback(async (text: string) => {
    if (!text.trim() || resolving) return;
    setResolving(true);
    setIntent(null);
    setConfirmedGameId(null);
    setStory(null);
    setPlaylist(null);
    setNarration(null);
    try {
      const res = await axios.post(apiPath("/api/reels/intent"), {
        prompt: text,
        favorite_teams: favoriteTeams,
        followed_players: followedPlayers,
      });
      setIntent(res.data as IntentResult);
      if (res.data.seconds) setConfirmedSeconds(res.data.seconds);
    } catch (e) {
      console.error("Intent resolution failed", e);
    } finally {
      setResolving(false);
    }
  }, [resolving, favoriteTeams, followedPlayers]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void resolveIntent(prompt);
  }

  function handleQuickPrompt(p: string) {
    setPrompt(p);
    void resolveIntent(p);
  }

  function confirmAndBuild(gameId: number, seconds: number) {
    setConfirmedGameId(gameId);
    setConfirmedSeconds(seconds);
    setStory(null);
    setPlaylist(null);
  }

  async function fetchNarration(seconds: number) {
    if (!gameId) return;
    setLoadingNarration(true);
    try {
      const res = await axios.get(apiPath(`/api/games/${gameId}/reels/narration`), { params: { seconds } });
      setNarration(res.data);
    } finally {
      setLoadingNarration(false);
    }
  }

  function openStoryReels() {
    if (!reelData?.cuts) return;
    const cut = reelData.cuts[0];
    if (cut?.story) setStory(cut.story);
  }

  function playVideoReel(cut: ReelCut) {
    if (cut.clips.length > 0) {
      setPlaylist({ label: cut.label, clips: cut.clips });
      setStory(null);
    }
  }

  const away = reelData ? cuts[0]?.clips[0] : null;
  void away; // used for game label fallback

  return (
    <div className="reels-page">
      {story && (
        <StoryReelPlayer
          story={story}
          awayAbbr={intent?.game_label?.split("@")[0]?.trim() ?? "AWY"}
          homeAbbr={intent?.game_label?.split("@")[1]?.split(" ")[0]?.trim() ?? "HME"}
          onClose={() => setStory(null)}
        />
      )}

      {playlist && <ReelPlayer playlist={playlist} onClose={() => setPlaylist(null)} />}

      <header className="rp-header">
        <Link to="/feed" className="rp-back">← Dashboard</Link>
        <div className="rp-header-center">
          <span className="rp-kicker">AI Reel Director</span>
          <h1>Build your reel</h1>
        </div>
        <div />
      </header>

      {/* ── Prompt interface ── */}
      <div className="rp-prompt-area">
        <form className="rp-prompt-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className="rp-prompt-input"
            value={prompt}
            rows={2}
            placeholder="What reel do you want? e.g. 'last Celtics game', 'every Brunson bucket this week', 'wild 4th quarter'"
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void resolveIntent(prompt); } }}
          />
          <button className="rp-prompt-send btn-primary" type="submit" disabled={!prompt.trim() || resolving}>
            {resolving ? "Finding game…" : "Build reel"}
          </button>
        </form>

        <div className="rp-chips">
          {QUICK_PROMPTS.map((p) => (
            <button key={p} className="rp-chip" disabled={resolving} onClick={() => {
              if (p === "Build a broadcast") {
                if (gameId) navigate(`/broadcast/${gameId}`);
                else { setPrompt(p); void resolveIntent("last game for my teams"); }
              } else {
                handleQuickPrompt(p);
              }
            }}>{p}</button>
          ))}
        </div>

        {favoriteTeams.length === 0 && (
          <p className="rp-setup-hint">
            <Link to="/demo">Pick your teams</Link> for better reel matching — otherwise we'll search across all recent games.
          </p>
        )}
      </div>

      {/* ── Intent confirmation ── */}
      {intent && !resolving && (
        <div className="rp-intent-card">
          <div className="rp-intent-header">
            <span className="rp-intent-label">Resolved:</span>
            <strong>{intent.game_label}</strong>
            <span className="rp-intent-focus">Focus: {intent.focus}</span>
            <span className="rp-intent-tier">{TIER_LABELS[intent.seconds] ?? `${Math.round(intent.seconds / 60)} min`}</span>
          </div>

          {intent.game_id && (
            <div className="rp-intent-actions">
              <button
                className="btn-primary"
                onClick={() => confirmAndBuild(intent.game_id!, intent.seconds)}
              >
                Build this reel
              </button>
              <button
                className="btn-ghost"
                onClick={() => navigate(`/broadcast/${intent.game_id}`)}
              >
                Broadcast mode
              </button>
              <button
                className="btn-ghost"
                onClick={() => navigate(`/reel/${intent.game_id}`)}
              >
                Full reel studio →
              </button>
            </div>
          )}

          {intent.candidates.length > 1 && (
            <div className="rp-candidates">
              <span>Other matches:</span>
              {intent.candidates.slice(1, 5).map((c) => (
                <button
                  key={c.id}
                  className="rp-candidate-chip"
                  onClick={() => confirmAndBuild(c.id, intent.seconds)}
                >
                  {c.label} <small>{c.date}</small>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Reel results ── */}
      {gameId && (
        <div className="rp-results">
          {reelLoading && (
            <div className="rp-skeleton-area">
              <div className="rp-skeleton rp-skeleton-title" />
              <div className="rp-skeleton rp-skeleton-row" />
              <div className="rp-skeleton rp-skeleton-row" />
              <div className="rp-skeleton rp-skeleton-row" />
            </div>
          )}

          {!reelLoading && cuts.length > 0 && (
            <>
              <div className="rp-tier-row">
                <span className="rp-tier-label">Tier:</span>
                {cuts.map((cut) => (
                  <button
                    key={cut.label}
                    className={`rp-tier-btn ${cut.target_seconds === confirmedSeconds ? "on" : ""}`}
                    onClick={() => setConfirmedSeconds(cut.target_seconds)}
                  >
                    {cut.label}
                    <small>{cut.clip_count > 0 ? `${cut.clip_count} clips` : "story only"}</small>
                  </button>
                ))}
              </div>

              {activeCut && (
                <div className="rp-active-cut">
                  <div className="rp-cut-meta">
                    <strong>{activeCut.label}</strong>
                    <span>{activeCut.clip_count} clips · ~{Math.round(activeCut.duration_seconds / 60)} min</span>
                  </div>
                  <div className="rp-cut-actions">
                    {activeCut.clips.length > 0 && (
                      <button className="btn-primary" onClick={() => playVideoReel(activeCut)}>
                        ▶ Play video reel
                      </button>
                    )}
                    <button className="btn-ghost" onClick={openStoryReels}>
                      Story mode
                    </button>
                    <button
                      className="btn-ghost"
                      disabled={loadingNarration}
                      onClick={() => void fetchNarration(activeCut.target_seconds)}
                    >
                      {loadingNarration ? "Loading…" : "Get narration script"}
                    </button>
                    <button
                      className="btn-ghost"
                      onClick={() => navigate(`/broadcast/${gameId}`)}
                    >
                      Broadcast →
                    </button>
                    <Link to={`/reel/${gameId}`} className="btn-ghost">
                      Full studio →
                    </Link>
                  </div>
                </div>
              )}

              {narration && (
                <details className="rp-narration-panel">
                  <summary>Narration script · {narration.voice_source === "anthropic" ? "AI-written" : "data-built"}</summary>
                  <pre className="rp-narration-text">{narration.voice_script}</pre>
                </details>
              )}
            </>
          )}

          {!reelLoading && cuts.length === 0 && (
            <div className="rp-empty">
              <p>No highlight clips published for this game yet.</p>
              <p>Story mode and narration scripts are still available — <button className="btn-ghost" onClick={openStoryReels}>open story mode</button></p>
            </div>
          )}
        </div>
      )}

      {/* ── Empty state before first prompt ── */}
      {!intent && !resolving && (
        <div className="rp-landing">
          <div className="rp-landing-grid">
            <div className="rp-landing-card">
              <strong>Story mode</strong>
              <p>Scene-by-scene visual narrative with score animations, possession viz, and stat reveals.</p>
            </div>
            <div className="rp-landing-card">
              <strong>Video reel</strong>
              <p>Real ESPN highlight clips assembled by the AI director, narrated by TTS voiceover.</p>
            </div>
            <div className="rp-landing-card">
              <strong>Broadcast mode</strong>
              <p>Two-host AI podcast conversation about the game — like NotebookLM for sports.</p>
            </div>
            <div className="rp-landing-card">
              <strong>Interrupt &amp; ask</strong>
              <p>Pause any reel and ask the analyst about a play, a rule, or a player's season.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
