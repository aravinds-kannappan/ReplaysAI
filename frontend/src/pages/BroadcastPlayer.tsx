import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiPath } from "../lib/api";
import type { StoryScene } from "../components/StoryReelPlayer";
import "./ReelsBroadcastNewsletter.css";

type BroadcastTurn = {
  host: "play" | "analyst";
  text: string;
  scene_type: StoryScene["type"];
  duration_hint: number;
};

type BroadcastData = {
  game_id: number;
  seconds: number;
  source: string;
  turns: BroadcastTurn[];
  total_duration: number;
  away: { abbreviation: string; name: string };
  home: { abbreviation: string; name: string };
};

const TIER_SECS = [
  { key: "2min", label: "2 min", seconds: 120 },
  { key: "5min", label: "5 min", seconds: 300 },
  { key: "10min", label: "10 min", seconds: 600 },
];

function useTwoVoices() {
  const [voices, setVoices] = useState<[SpeechSynthesisVoice | null, SpeechSynthesisVoice | null]>([null, null]);

  useEffect(() => {
    function pick() {
      const all = window.speechSynthesis?.getVoices() ?? [];
      const en = all.filter((v) => v.lang.toLowerCase().startsWith("en"));
      if (en.length === 0) return;
      // Rank by how natural the voice tends to sound, then choose two distinct
      // voices so the two hosts are clearly different people.
      const quality = (v: SpeechSynthesisVoice) =>
        (/google|natural|neural|enhanced|premium|aria|jenny|siri/i.test(v.name) ? 3 : 0) +
        (v.localService === false ? 1 : 0);
      const ranked = [...en].sort((a, b) => quality(b) - quality(a));
      const play =
        ranked.find((v) => /guy|david|daniel|alex|male|google us/i.test(v.name)) ?? ranked[0];
      const analyst =
        ranked.find((v) => v !== play && /aria|jenny|samantha|karen|victoria|zira|female|google uk/i.test(v.name)) ??
        ranked.find((v) => v !== play) ?? ranked[0];
      setVoices([play, analyst]);
    }
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    pick();
    window.speechSynthesis.addEventListener?.("voiceschanged", pick);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", pick);
  }, []);

  return voices;
}

export default function BroadcastPlayer() {
  const { gameId } = useParams<{ gameId: string }>();
  const [tierSec, setTierSec] = useState(300);
  const voices = useTwoVoices();
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [finished, setFinished] = useState(false);
  const speakingRef = useRef(false);
  const indexRef = useRef(0);

  const { data, isLoading } = useQuery<BroadcastData>({
    queryKey: ["broadcast", gameId, tierSec],
    queryFn: () => axios.post(apiPath(`/api/games/${gameId}/broadcast`), null, { params: { seconds: tierSec } }).then((r) => r.data),
    enabled: !!gameId,
    staleTime: 600_000,
  });

  const turns = data?.turns ?? [];

  const speakTurn = useCallback((turn: BroadcastTurn, turnIndex: number) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(turn.text);
    const [playVoice, analystVoice] = voices;
    if (turn.host === "play" && playVoice) {
      utter.voice = playVoice;
      utter.rate = 1.05;
      utter.pitch = 1.0;
    } else if (turn.host === "analyst" && analystVoice) {
      utter.voice = analystVoice;
      utter.rate = 0.95;
      utter.pitch = 0.92;
    }
    speakingRef.current = true;
    utter.onend = () => {
      speakingRef.current = false;
      const nextIdx = turnIndex + 1;
      if (nextIdx < turns.length) {
        indexRef.current = nextIdx;
        setIndex(nextIdx);
      } else {
        setPlaying(false);
        setFinished(true);
      }
    };
    utter.onerror = () => {
      speakingRef.current = false;
    };
    window.speechSynthesis.speak(utter);
  }, [turns, voices]);

  useEffect(() => {
    if (!playing || turns.length === 0) return;
    if (speakingRef.current) return;
    const turn = turns[index];
    if (!turn) return;
    speakTurn(turn, index);
  }, [playing, index, turns, speakTurn]);

  useEffect(() => {
    return () => window.speechSynthesis?.cancel();
  }, []);

  function start() {
    setIndex(0);
    indexRef.current = 0;
    setFinished(false);
    setPlaying(true);
  }

  function togglePlay() {
    if (finished) { start(); return; }
    if (playing) {
      window.speechSynthesis?.cancel();
      speakingRef.current = false;
      setPlaying(false);
    } else {
      setPlaying(true);
    }
  }

  function jumpTo(i: number) {
    window.speechSynthesis?.cancel();
    speakingRef.current = false;
    setIndex(i);
    indexRef.current = i;
    setFinished(false);
    if (playing) {
      // trigger re-play via the effect
      setTimeout(() => setIndex(i), 50);
    }
  }

  function changeTier(sec: number) {
    window.speechSynthesis?.cancel();
    speakingRef.current = false;
    setPlaying(false);
    setFinished(false);
    setIndex(0);
    setTierSec(sec);
  }

  const currentTurn = turns[index];
  const away = data?.away;
  const home = data?.home;

  const SCENE_BG: Record<string, string> = {
    title: "linear-gradient(135deg, #0d1f2d, #1a3a4a)",
    moment: "linear-gradient(135deg, #1a1000, #3a2200)",
    stat: "linear-gradient(135deg, #0d1a0d, #1a331a)",
    run: "linear-gradient(135deg, #1a0d1a, #33133a)",
    verdict: "linear-gradient(135deg, #0d0d1a, #1a1a33)",
  };

  return (
    <div className="bc-page">
      <div className="bc-shell">
      <header className="bc-header">
        <Link to={gameId ? `/game/${gameId}` : "/reels"} className="bc-back">← Back</Link>
        <div className="bc-header-center">
          <span className="bc-kicker">Broadcast Mode</span>
          <h1>
            {away && home ? `${away.abbreviation} vs ${home.abbreviation}` : "Loading…"}
          </h1>
        </div>
        <Link to="/reels" className="bc-back bc-back-right">All reels →</Link>
      </header>

      <div className="bc-tiers">
        {TIER_SECS.map((t) => (
          <button
            key={t.key}
            className={`bc-tier ${t.seconds === tierSec ? "on" : ""}`}
            onClick={() => changeTier(t.seconds)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="bc-loading">
          <div className="bc-loading-spinner" />
          <p>Writing the broadcast script…</p>
        </div>
      )}

      {!isLoading && turns.length > 0 && (
        <div className="bc-stage" style={{ background: currentTurn ? SCENE_BG[currentTurn.scene_type] ?? SCENE_BG.moment : SCENE_BG.title }}>
          {/* Host indicators */}
          <div className="bc-hosts">
            <div className={`bc-host ${currentTurn?.host === "play" && playing ? "speaking" : ""}`}>
              <div className="bc-host-avatar bc-host-play">
                <span>P</span>
              </div>
              <span>Play-by-Play</span>
            </div>
            <div className={`bc-host ${currentTurn?.host === "analyst" && playing ? "speaking" : ""}`}>
              <div className="bc-host-avatar bc-host-analyst">
                <span>A</span>
              </div>
              <span>Analyst</span>
            </div>
          </div>

          {/* Progress segments */}
          <div className="bc-progress">
            {turns.map((t, i) => (
              <button
                key={i}
                className={`bc-seg ${i === index ? "active" : ""} ${i < index ? "done" : ""} bc-seg-${t.host}`}
                onClick={() => jumpTo(i)}
                title={`${t.host}: ${t.text.slice(0, 60)}…`}
              />
            ))}
          </div>

          {/* Current dialogue */}
          <div className="bc-dialogue">
            <div className={`bc-speaker-tag bc-speaker-${currentTurn?.host}`}>
              {currentTurn?.host === "play" ? "PLAY-BY-PLAY" : "ANALYST"}
            </div>
            <p className="bc-dialogue-text">{currentTurn?.text}</p>
          </div>

          {/* Scene type badge */}
          {currentTurn && (
            <div className={`bc-scene-badge bc-scene-${currentTurn.scene_type}`}>
              {currentTurn.scene_type.toUpperCase()}
            </div>
          )}

          {/* Turn counter */}
          <div className="bc-turn-counter">
            {index + 1} / {turns.length} · {Math.round((data?.total_duration ?? 0) / 60)} min
          </div>
        </div>
      )}

      {!isLoading && turns.length > 0 && (
        <div className="bc-controls">
          <button className="bc-ctrl-btn" disabled={index === 0} onClick={() => jumpTo(Math.max(0, index - 1))}>
            ‹ Prev
          </button>
          <button className="bc-play-btn" onClick={togglePlay}>
            {finished ? "Replay" : playing ? "Pause" : (index === 0 ? "Start broadcast" : "Resume")}
          </button>
          <button className="bc-ctrl-btn" disabled={index >= turns.length - 1} onClick={() => jumpTo(Math.min(turns.length - 1, index + 1))}>
            Next ›
          </button>
        </div>
      )}

      {data?.source === "fallback" && !isLoading && (
        <p className="bc-source-note">Script built from game data (Claude unavailable)</p>
      )}
      </div>
    </div>
  );
}
