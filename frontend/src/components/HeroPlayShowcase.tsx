import { useEffect, useState } from "react";
import PlayAnimation from "./PlayAnimation";
import { buildPlaySchema, type Annotation } from "../lib/playSchema";

type Show = {
  label: string;
  away: string; home: string;
  before: { away: number; home: number };
  after: { away: number; home: number };
  schema: ReturnType<typeof buildPlaySchema>;
  ann: Annotation[];
};

const SHOWS: Show[] = [
  {
    label: "NFL · touchdown",
    away: "BUF", home: "KC", before: { away: 14, home: 13 }, after: { away: 14, home: 20 },
    schema: buildPlaySchema({ sport: "NFL", playType: "touchdown", description: "Mahomes pass deep right to Kelce for 38 yards, TOUCHDOWN", offAbbr: "KC", defAbbr: "BUF" }),
    ann: [
      { t: 0.12, agent: "Scout", text: "Play-action — safety bites" },
      { t: 0.46, agent: "Stat", text: "38 air yards" },
      { t: 0.8, agent: "Ref", text: "Toe-tap, in bounds" },
      { t: 0.9, agent: "Predict", text: "Win prob +18%" },
    ],
  },
  {
    label: "NBA · dunk",
    away: "BOS", home: "NYK", before: { away: 98, home: 99 }, after: { away: 98, home: 101 },
    schema: buildPlaySchema({ sport: "NBA", playType: "dunk", description: "Brunson makes 1-foot running dunk (Bridges assists)", offAbbr: "NYK", defAbbr: "BOS" }),
    ann: [
      { t: 0.18, agent: "Scout", text: "Bridges threads the lob" },
      { t: 0.5, agent: "Stat", text: "Brunson, alley-oop" },
      { t: 0.7, agent: "Ref", text: "Clean — no foul" },
      { t: 0.8, agent: "Predict", text: "+2, lead extends" },
    ],
  },
];

export default function HeroPlayShowcase() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((p) => (p + 1) % SHOWS.length), 9000);
    return () => window.clearInterval(id);
  }, []);
  const s = SHOWS[i];
  return (
    <div className="lp-showcase">
      <PlayAnimation
        key={i}
        schema={s.schema}
        awayAbbr={s.away}
        homeAbbr={s.home}
        annotations={s.ann}
        scoreBefore={s.before}
        scoreAfter={s.after}
        compact
        loop
      />
      <div className="lp-showcase-foot">
        <span className="lp-showcase-live">● LIVE</span>
        <span>{s.label}</span>
        <span className="lp-showcase-dots">{SHOWS.map((_, k) => <i key={k} className={k === i ? "on" : ""} />)}</span>
      </div>
    </div>
  );
}
