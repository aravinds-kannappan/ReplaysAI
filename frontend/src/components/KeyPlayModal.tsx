import { useMemo } from "react";
import FootballPlayAnimation from "./FootballPlayAnimation";
import { buildPlaySchema } from "../lib/playSchema";

export type PlayFacts = {
  play_type: string;
  description: string;
  period: number;
  clock: string | null;
  away_score: number;
  home_score: number;
  prev_away: number;
  prev_home: number;
  kicking_team: string | null;
  fg_distance: number | null;
  yards_to_goal: number | null;
};

export type AgentRead = { agent: string; headline: string; detail: string; metric_label?: string | null; metric_value?: string | null };

export type PlayAnalysis = {
  score_impact: { points: number; new_score: { away: number; home: number }; label: string };
  clock_context: string;
  field_position: string | null;
  expected_points: { attempt: number; scored: number; make_prob: number; label: string } | null;
  win_prob: { before: number; after: number; delta_pct: number; label: string };
  why_it_mattered: string;
  agents: AgentRead[];
  disclaimer: string;
};

export type KeyPlay = {
  play: PlayFacts;
  analysis: PlayAnalysis;
  awayAbbr: string;
  homeAbbr: string;
  heading?: string;
};

const AGENT_META: Record<string, { color: string; what: string }> = {
  Scout: { color: "#3b82f6", what: "Alignment & field position" },
  Stat: { color: "#22c55e", what: "The numbers" },
  Ref: { color: "#f59e0b", what: "Rules & officiating" },
  Predict: { color: "#06b6d4", what: "Win-prob / expected-points proxy" },
};

function cleanDesc(d: string) {
  return d.replace(/\s*\*\*?\s*Injury Update:.*$/i, "").replace(/,\s*(Center|Holder)-[A-Z]\.[A-Za-z'-]+/g, "").trim();
}

export default function KeyPlayModal({ data, onClose }: { data: KeyPlay; onClose: () => void }) {
  const { play, analysis, awayAbbr, homeAbbr } = data;
  const schema = useMemo(
    () => buildPlaySchema({
      playType: play.play_type,
      description: play.description,
      fgDistance: play.fg_distance,
      yardsToGoal: play.yards_to_goal,
      kickingAbbr: play.kicking_team || awayAbbr,
      defenseAbbr: play.kicking_team === awayAbbr ? homeAbbr : awayAbbr,
    }),
    [play, awayAbbr, homeAbbr],
  );
  const wp = analysis.win_prob;

  return (
    <div className="kp-overlay" role="dialog" aria-label="Key play breakdown" onClick={onClose}>
      <div className="kp-modal" onClick={(e) => e.stopPropagation()}>
        <header className="kp-head">
          <div>
            <span className="kp-kicker">Key play{data.heading ? ` · ${data.heading}` : ""}</span>
            <strong>{cleanDesc(play.description) || play.play_type}</strong>
          </div>
          <button className="kp-close" onClick={onClose}>✕</button>
        </header>

        <FootballPlayAnimation
          schema={schema}
          awayAbbr={awayAbbr}
          homeAbbr={homeAbbr}
          scoreBefore={{ away: play.prev_away, home: play.prev_home }}
          scoreAfter={{ away: play.away_score, home: play.home_score }}
        />

        <div className="kp-analysis">
          <div className="kp-metrics">
            <div className="kp-metric">
              <span>Score impact</span>
              <b>+{analysis.score_impact.points}</b>
              <i>{analysis.score_impact.label}</i>
            </div>
            <div className="kp-metric">
              <span>Game situation</span>
              <b>{play.clock || "—"}</b>
              <i>{analysis.clock_context}</i>
            </div>
            {analysis.field_position && (
              <div className="kp-metric">
                <span>Field position</span>
                <b>{play.fg_distance ? `${play.fg_distance} yd` : "—"}</b>
                <i>{analysis.field_position}</i>
              </div>
            )}
            {analysis.expected_points && (
              <div className="kp-metric">
                <span>Expected points (proxy)</span>
                <b>~{analysis.expected_points.attempt}</b>
                <i>make-rate proxy {Math.round(analysis.expected_points.make_prob * 100)}%</i>
              </div>
            )}
            <div className="kp-metric">
              <span>Win prob (proxy)</span>
              <b className={wp.delta_pct >= 0 ? "up" : "down"}>{wp.delta_pct >= 0 ? "+" : ""}{wp.delta_pct} pts</b>
              <i>{wp.label}</i>
            </div>
          </div>

          <div className="kp-why">
            <span>Why it mattered</span>
            <p>{analysis.why_it_mattered}</p>
          </div>

          <div className="kp-agents">
            <div className="kp-agents-head">Agent breakdown</div>
            {analysis.agents.map((a) => (
              <div className="kp-agent" key={a.agent}>
                <div className="kp-agent-tag" style={{ ["--c" as string]: AGENT_META[a.agent]?.color || "#8b99b3" }}>
                  <b>{a.agent}</b><span>{AGENT_META[a.agent]?.what}</span>
                </div>
                <div className="kp-agent-body">
                  <strong>{a.headline}</strong>
                  <p>{a.detail}</p>
                  {a.metric_label && <span className="kp-agent-metric">{a.metric_label}: <b>{a.metric_value}</b></span>}
                </div>
              </div>
            ))}
          </div>

          <p className="kp-disclaimer">{analysis.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}
