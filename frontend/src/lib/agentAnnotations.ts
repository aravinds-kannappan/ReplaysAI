import type { Annotation } from "./playSchema";

type AgentLike = { agent: string; headline: string; metric_value?: string | null };

const TIMES = [0.16, 0.4, 0.62, 0.85];
const VALID = new Set(["Scout", "Stat", "Ref", "Predict"]);

/** Map the (deterministic) analysis agents onto timed pop-ups across the play. */
export function agentAnnotations(agents: AgentLike[]): Annotation[] {
  return agents
    .filter((a) => VALID.has(a.agent))
    .slice(0, 4)
    .map((a, i) => ({
      t: TIMES[i] ?? 0.5,
      agent: a.agent as Annotation["agent"],
      text: a.metric_value ? `${a.headline} · ${a.metric_value}` : a.headline,
    }));
}
