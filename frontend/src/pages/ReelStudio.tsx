import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import Hls from "hls.js";
import ReactMarkdown from "react-markdown";
import { apiPath } from "../lib/api";
import { useCurrentUser } from "../hooks/useUser";
import "./ReelStudio.css";

/* ── Types ── */
type Overlay =
  | { type: "scorebug"; away: { abbr: string; score: number | null }; home: { abbr: string; score: number | null } }
  | { type: "statline"; player: string; team: string; stat_line: string; category: string }
  | { type: "winprob"; team: string; value: number; model: boolean };

type Segment = {
  id: string; headline: string; description: string; duration: number;
  url: string; thumbnail: string; narration?: string; overlays?: Overlay[];
};

type Cut = {
  label: string; target_seconds: number; blurb: string;
  clip_count: number; duration_seconds: number; clips: Segment[]; explainer?: string;
};

type ChatTurn = { role: "user" | "assistant"; text: string };

const TIERS = [
  { key: "pulse", name: "Pulse", sub: "2 min · key moments" },
  { key: "story", name: "Story", sub: "5 min · why it mattered" },
  { key: "deep", name: "Deep Cut", sub: "10 min · fantasy + rules" },
];

/* ── Minimal Web Speech API typing (no DOM lib coverage) ── */
type RecognitionLike = {
  lang: string; interimResults: boolean; continuous: boolean;
  start: () => void; stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null; onerror: (() => void) | null;
};
function getRecognition(): RecognitionLike | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => RecognitionLike;
    webkitSpeechRecognition?: new () => RecognitionLike;
  };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

function speak(text: string, onEnd?: () => void) {
  if (typeof window === "undefined" || !window.speechSynthesis || !text) {
    onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.rate = 1.02;
  utter.pitch = 1.0;
  if (onEnd) utter.onend = onEnd;
  window.speechSynthesis.speak(utter);
}

/* ── Overlay layers rendered over the video ── */
function OverlayLayers({ overlays }: { overlays?: Overlay[] }) {
  if (!overlays?.length) return null;
  return (
    <>
      {overlays.map((o, i) => {
        if (o.type === "scorebug") {
          return (
            <div key={i} className="rs-ov rs-scorebug">
              <span><b>{o.away.abbr}</b> {o.away.score ?? "—"}</span>
              <span><b>{o.home.abbr}</b> {o.home.score ?? "—"}</span>
            </div>
          );
        }
        if (o.type === "statline") {
          return (
            <div key={i} className="rs-ov rs-statline">
              <strong>{o.player}</strong> <span>{o.team} · {o.stat_line}</span>
            </div>
          );
        }
        return (
          <div key={i} className="rs-ov rs-winprob" title="Model win-probability read">
            <span className="rs-wp-label">WIN PROB · {o.team}</span>
            <div className="rs-wp-track"><div className="rs-wp-fill" style={{ width: `${o.value}%` }} /></div>
            <span className="rs-wp-val">{o.value}%</span>
          </div>
        );
      })}
    </>
  );
}

export default function ReelStudio() {
  const { gameId } = useParams<{ gameId: string }>();
  const { data: user } = useCurrentUser();
  const videoRef = useRef<HTMLVideoElement>(null);

  const { data: reelData, isLoading } = useQuery({
    queryKey: ["reel-studio", gameId],
    queryFn: () => axios.get(apiPath(`/api/games/${gameId}/reels`)).then((r) => r.data),
    enabled: !!gameId,
    staleTime: 300_000,
  });
  const cuts: Cut[] = reelData?.cuts ?? [];

  const [tier, setTier] = useState(0);
  const [seg, setSeg] = useState(0);
  const [started, setStarted] = useState(false);
  const [asking, setAsking] = useState(false);
  const [listening, setListening] = useState(false);
  const [input, setInput] = useState("");
  const [chat, setChat] = useState<ChatTurn[]>([]);
  const [sending, setSending] = useState(false);
  const recognitionRef = useRef<RecognitionLike | null>(null);

  const cut = cuts[tier];
  const segments = cut?.clips ?? [];
  const segment = segments[seg];

  /* Load the current clip (HLS where needed). */
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !segment) return;
    const isHls = segment.url.includes(".m3u8");
    if (isHls && !video.canPlayType("application/vnd.apple.mpegurl") && Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(segment.url);
      hls.attachMedia(video);
      return () => hls.destroy();
    }
    video.src = segment.url;
  }, [segment]);

  /* Narrate each segment with TTS, ducking the clip's own audio underneath. */
  useEffect(() => {
    const video = videoRef.current;
    if (!started || asking || !segment || !video) return;
    video.muted = false;
    video.volume = segment.narration ? 0.12 : 1.0; // duck under narration
    video.play().catch(() => undefined);
    if (segment.narration) {
      speak(segment.narration, () => {
        if (videoRef.current) videoRef.current.volume = 1.0; // restore after narration
      });
    }
    return () => window.speechSynthesis?.cancel();
  }, [segment, started, asking, seg]);

  const advance = useCallback(() => {
    setSeg((i) => Math.min(i + 1, segments.length - 1));
  }, [segments.length]);

  function selectTier(next: number) {
    window.speechSynthesis?.cancel();
    setTier(next);
    setSeg(0);
  }

  function pauseForAsk() {
    window.speechSynthesis?.cancel();
    videoRef.current?.pause();
    setAsking(true);
  }

  function resume() {
    setAsking(false);
    setListening(false);
    recognitionRef.current?.stop();
    const video = videoRef.current;
    if (video && started) {
      video.play().catch(() => undefined);
      if (segment?.narration) speak(segment.narration);
    }
  }

  function toggleMic() {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = getRecognition();
    if (!rec) return;
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e) => {
      const transcript = e.results?.[0]?.[0]?.transcript ?? "";
      if (transcript) setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    rec.start();
    setListening(true);
  }

  async function ask() {
    const question = input.trim();
    if (!question || sending) return;
    setInput("");
    const history = [...chat, { role: "user" as const, text: question }];
    setChat(history);
    setSending(true);
    const context =
      `reel gameId=${gameId}, segmentId=${seg}, ` +
      `clipTimestamp=${Math.round(videoRef.current?.currentTime ?? 0)}s, ` +
      `clipHeadline=${segment?.headline ?? ""}, recentNarration=${segment?.narration ?? ""}`;
    try {
      const res = await axios.post(apiPath("/api/chat"), {
        message: question,
        context,
        favorite_teams: (user?.favorite_teams ?? []).map((t) => `${t.sport}:${t.abbreviation}`),
        followed_players: (user?.followed_players ?? []).map((p) => p.name),
        messages: history.slice(0, -1),
      });
      const reply: string = res.data?.reply ?? "I couldn't reach the analyst just now.";
      setChat([...history, { role: "assistant", text: reply }]);
      speak(reply.replace(/[#*`_>]/g, ""));
    } catch {
      setChat([...history, { role: "assistant", text: "The analyst is unavailable right now — try resuming the reel." }]);
    } finally {
      setSending(false);
    }
  }

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const tierMeta = TIERS[Math.min(tier, TIERS.length - 1)];

  return (
    <div className="rs-page">
      <header className="rs-head">
        <Link to={`/game/${gameId}`} className="rs-back">← Game</Link>
        <div>
          <span className="rs-kicker">Personalized Reel · narrated + interactive</span>
          <h1>{reelData ? "Your reel" : "Reel studio"}</h1>
        </div>
        <Link to="/feed" className="rs-back rs-back-right">Dashboard →</Link>
      </header>

      <div className="rs-tiers">
        {TIERS.map((t, i) => (
          <button key={t.key} className={`rs-tier ${i === tier ? "on" : ""}`} disabled={!cuts[i]} onClick={() => selectTier(i)}>
            <strong>{t.name}</strong><span>{t.sub}</span>
          </button>
        ))}
      </div>

      {isLoading && <p className="loading-text">Assembling your reel…</p>}
      {!isLoading && segments.length === 0 && (
        <p className="empty-state">No highlight video is published for this game yet, so a narrated reel can't be built.</p>
      )}

      {segment && (
        <div className="rs-stage-wrap">
          <div className="rs-stage">
            <video
              ref={videoRef}
              poster={segment.thumbnail || undefined}
              playsInline
              onEnded={advance}
              onClick={() => videoRef.current?.paused ? videoRef.current.play() : videoRef.current?.pause()}
            />
            <OverlayLayers overlays={segment.overlays} />

            {!started && (
              <button className="rs-start" onClick={() => setStarted(true)}>
                ▶ Start narrated reel
                <small>{tierMeta.name} · {segments.length} segments</small>
              </button>
            )}

            {asking && (
              <div className="rs-ask-panel">
                <div className="rs-ask-head">
                  <strong>Paused — ask about this moment</strong>
                  <button className="btn-ghost" onClick={resume}>Resume ▶</button>
                </div>
                <div className="rs-ask-log">
                  {chat.length === 0 && <p className="rs-ask-hint">Ask why this play mattered, the rule behind it, or how a player's line compares.</p>}
                  {chat.map((m, i) => (
                    <div key={i} className={`rs-msg rs-msg-${m.role}`}>
                      {m.role === "assistant" ? <ReactMarkdown>{m.text}</ReactMarkdown> : m.text}
                    </div>
                  ))}
                  {sending && <div className="rs-msg rs-msg-assistant rs-msg-loading">Analyst is thinking…</div>}
                </div>
                <div className="rs-ask-input">
                  <button className={`rs-mic ${listening ? "on" : ""}`} onClick={toggleMic} title="Voice input" aria-label="Voice input">
                    {listening ? "● Listening" : "🎤"}
                  </button>
                  <input
                    value={input}
                    placeholder="Ask the analyst…"
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") ask(); }}
                  />
                  <button className="btn-primary" disabled={!input.trim() || sending} onClick={ask}>Ask</button>
                </div>
              </div>
            )}
          </div>

          <div className="rs-controls">
            <div className="rs-progress">
              {segments.map((_, i) => (
                <button key={i} className={`rs-dot ${i === seg ? "on" : ""} ${i < seg ? "done" : ""}`} onClick={() => setSeg(i)} aria-label={`Segment ${i + 1}`} />
              ))}
            </div>
            <div className="rs-control-row">
              <span className="rs-seg-label">Segment {seg + 1}/{segments.length} · {segment.headline}</span>
              <div className="rs-control-btns">
                <button className="btn-ghost" disabled={seg === 0} onClick={() => setSeg(seg - 1)}>Prev</button>
                {!asking && <button className="rs-interrupt" onClick={pauseForAsk}>⏸ Interrupt &amp; ask</button>}
                <button className="btn-ghost" disabled={seg >= segments.length - 1} onClick={advance}>Next</button>
              </div>
            </div>
            {segment.narration && <p className="rs-narration">“{segment.narration}”</p>}
          </div>
        </div>
      )}

      {cut?.explainer && (
        <details className="rs-explainer">
          <summary>Full game deep dive</summary>
          <div className="recap-content"><ReactMarkdown>{cut.explainer}</ReactMarkdown></div>
        </details>
      )}
    </div>
  );
}
