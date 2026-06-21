import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { toPng } from "html-to-image";
import { apiPath } from "../lib/api";
import { useRosterPlayers, useRosters, useSaveRoster } from "../hooks/usePredictions";
import "./DreamTeam.css";

type League = "NBA" | "NFL";

type RosterPlayer = { id: number; name: string; team: string | null; position: string | null; impact_score: number };

type SimRoster = {
  id: number; name: string; team: string | null; position: string | null;
  overall: number; vector: { offense: number; defense: number; playmaking: number; efficiency: number }; rated: boolean;
};

type SimResult = {
  sport: League;
  iterations: number;
  roster: SimRoster[];
  chemistry: { multiplier: number; read: string; generated_by: string };
  championship_odds_pct: number;
  projected_record: { wins: number; losses: number };
  playoff_round_distribution: Record<string, number>;
  avg_seed: number | null;
  x_factor: { blurb: string; generated_by: string };
  generated_by: string;
  cached: boolean;
};

const ROUND_ORDER: [string, string][] = [
  ["miss", "Missed"], ["r1", "Round 1"], ["r2", "Round 2"],
  ["conf", "Conf. Finals"], ["finals", "Finals"], ["champ", "Champion"],
];

/* A circular odds ring drawn as SVG — matches the app's hand-rolled chart idiom. */
function OddsRing({ pct }: { pct: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const filled = Math.min(100, Math.max(0, pct)) / 100;
  return (
    <svg className="dt-ring" viewBox="0 0 130 130" role="img" aria-label={`${pct}% championship odds`}>
      <circle cx="65" cy="65" r={r} className="dt-ring-track" />
      <circle
        cx="65" cy="65" r={r} className="dt-ring-fill"
        strokeDasharray={`${c * filled} ${c}`} transform="rotate(-90 65 65)"
      />
      <text x="65" y="60" className="dt-ring-val">{pct}%</text>
      <text x="65" y="82" className="dt-ring-cap">TITLE ODDS</text>
    </svg>
  );
}

/* Playoff-round distribution as an SVG bar chart. */
function PlayoffChart({ dist, iterations }: { dist: Record<string, number>; iterations: number }) {
  const max = Math.max(1, ...ROUND_ORDER.map(([k]) => dist[k] ?? 0));
  return (
    <div className="dt-chart">
      {ROUND_ORDER.map(([key, label]) => {
        const count = dist[key] ?? 0;
        const pct = Math.round((count / iterations) * 100);
        return (
          <div key={key} className="dt-bar-row">
            <span className="dt-bar-label">{label}</span>
            <div className="dt-bar-track">
              <div
                className={`dt-bar-fill ${key === "champ" ? "is-champ" : ""} ${key === "miss" ? "is-miss" : ""}`}
                style={{ width: `${(count / max) * 100}%` }}
              />
            </div>
            <span className="dt-bar-val">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

export default function DreamTeam() {
  const [league, setLeague] = useState<League>("NBA");
  const { data: players = [] } = useRosterPlayers(league) as { data?: RosterPlayer[] };
  const { data: rosters = [] } = useRosters() as { data?: { sport: string; player_ids: number[] }[] };
  const save = useSaveRoster();
  const cardRef = useRef<HTMLDivElement>(null);

  // Seed the picker from any roster saved in the Feed Extras tab.
  const saved = rosters.find((r) => r.sport === league.toUpperCase());
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const savedKey = (saved?.player_ids ?? []).join(",");
  useEffect(() => {
    // Re-seed the picker from any saved lineup when league/lineup changes.
    const id = window.setTimeout(() => setPicked(new Set(savedKey ? savedKey.split(",").map(Number) : [])), 0);
    return () => window.clearTimeout(id);
  }, [league, savedKey]);

  const playerById = useMemo(() => new Map(players.map((p) => [p.id, p])), [players]);
  // Only surface the top stars, ranked by production, so they're easy to draft.
  const topPlayers = useMemo(
    () => [...players].sort((a, b) => b.impact_score - a.impact_score).slice(0, 30),
    [players],
  );

  const sim = useMutation({
    mutationFn: async (): Promise<SimResult> => {
      const ids = [...picked];
      const hints = ids.map((id) => {
        const p = playerById.get(id);
        return { id, name: p?.name, position: p?.position };
      });
      const res = await axios.post(apiPath("/api/dream-team/simulate"), {
        sport: league, player_ids: ids, players: hints, iterations: 10000,
      });
      return res.data;
    },
  });

  function toggle(id: number) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 10) next.add(id);
      return next;
    });
    sim.reset();
  }

  function switchLeague(next: League) {
    setLeague(next);
    sim.reset();
  }

  async function downloadCard() {
    if (!cardRef.current) return;
    try {
      const dataUrl = await toPng(cardRef.current, { pixelRatio: 2, backgroundColor: "#0b0d0e" });
      const link = document.createElement("a");
      link.download = `replaysai-dream-team-${league.toLowerCase()}.png`;
      link.href = dataUrl;
      link.click();
    } catch {
      /* export is best-effort */
    }
  }

  const result = sim.data;

  return (
    <div className="dt-page">
      <header className="dt-head">
        <Link to="/feed" className="dt-back">← Dashboard</Link>
        <div>
          <span className="dt-kicker">All-Star Lab · CoachAgent + Monte Carlo</span>
          <h1>Build Your Dream Team</h1>
          <p>Draft real {league} stars, then simulate 10,000 seasons for championship odds. The roster and stats are real ESPN data; the title projection is a model forecast.</p>
        </div>
        <div className="dt-league-toggle">
          {(["NBA", "NFL"] as League[]).map((l) => (
            <button key={l} className={l === league ? "on" : ""} onClick={() => switchLeague(l)}>{l}</button>
          ))}
        </div>
      </header>

      <div className="dt-grid">
        <section className="dt-builder">
          <div className="dt-builder-head">
            <h2>Roster <span>({picked.size}/10)</span></h2>
            <div className="dt-builder-actions">
              <button className="btn-ghost" disabled={picked.size === 0 || save.isPending}
                onClick={() => save.mutate({ sport: league, player_ids: [...picked] })}>
                {save.isPending ? "Saving…" : "Save lineup"}
              </button>
              <button className="btn-primary" disabled={picked.size === 0 || sim.isPending}
                onClick={() => sim.mutate()}>
                {sim.isPending ? "Simulating 10k…" : "Run simulation"}
              </button>
            </div>
          </div>
          <div className="dt-pool">
            {players.length === 0 && <p className="empty-state">Loading {league} players…</p>}
            {topPlayers.map((p) => (
              <button key={p.id} className={`dt-pool-player ${picked.has(p.id) ? "on" : ""}`} onClick={() => toggle(p.id)}>
                <div><strong>{p.name}</strong><span>{p.team || "FA"} · {p.position || "UTIL"}</span></div>
                <b>{p.impact_score}</b>
              </button>
            ))}
          </div>
        </section>

        <section className="dt-results">
          {sim.isError && <p className="empty-state">Simulation failed — pick at least one player and retry.</p>}
          {!result && !sim.isPending && !sim.isError && (
            <div className="dt-empty-results">
              <p>Draft your squad and hit <strong>Run simulation</strong>. The CoachAgent grades chemistry, then 10,000 Monte Carlo seasons project your title run.</p>
            </div>
          )}
          {sim.isPending && <div className="dt-empty-results"><p className="loading-text">Running 10,000 seasons…</p></div>}

          {result && (
            <>
              <div className="dt-card" ref={cardRef}>
                <div className="dt-card-top">
                  <span className="dt-card-brand">ReplaysAI · Dream Team</span>
                  <span className="dt-card-league">{result.sport}</span>
                </div>
                <div className="dt-card-main">
                  <OddsRing pct={result.championship_odds_pct} />
                  <div className="dt-card-stats">
                    <div className="dt-stat"><span>Projected record</span><strong>{result.projected_record.wins}–{result.projected_record.losses}</strong></div>
                    <div className="dt-stat"><span>Avg. playoff seed</span><strong>{result.avg_seed ?? "—"}</strong></div>
                    <div className="dt-stat"><span>Chemistry</span><strong>×{result.chemistry.multiplier}</strong></div>
                  </div>
                </div>
                <PlayoffChart dist={result.playoff_round_distribution} iterations={result.iterations} />
                <div className="dt-card-roster">
                  {result.roster.slice(0, 10).map((p) => (
                    <span key={p.id} className="dt-chip" title={`OVR ${p.overall}`}>
                      {p.name} <b>{p.overall}</b>
                    </span>
                  ))}
                </div>
                <div className="dt-card-watermark">replaysai · forecast, not a real result</div>
              </div>

              <div className="dt-analysis">
                <div className="dt-analysis-block">
                  <span className="dt-tag">CoachAgent · chemistry {result.chemistry.generated_by === "anthropic" ? "(AI)" : "(model)"}</span>
                  <p>{result.chemistry.read}</p>
                </div>
                <div className="dt-analysis-block">
                  <span className="dt-tag">AnalystAgent · X-factor {result.x_factor.generated_by === "anthropic" ? "(AI)" : "(model)"}</span>
                  <p>{result.x_factor.blurb}</p>
                </div>
                <div className="dt-result-actions">
                  <button className="btn-primary" onClick={downloadCard}>Download result card</button>
                  <button className="btn-ghost" onClick={() => sim.mutate()}>Re-run</button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
