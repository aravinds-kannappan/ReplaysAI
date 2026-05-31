import { memo, useState } from "react";
import { usePlays } from "../hooks/useGames";

interface Props {
  gameId: number;
}

const PLAY_TYPE_OPTIONS = [
  "all", "dunk", "three_pointer", "block", "steal",
  "touchdown", "interception", "sack", "field_goal",
];

function PlayTimeline({ gameId }: Props) {
  const [period, setPeriod] = useState<number | undefined>();
  const [playType, setPlayType] = useState<string | undefined>();

  const { data, isLoading } = usePlays(gameId, {
    period,
    play_type: playType === "all" || !playType ? undefined : playType,
    limit: 200,
  });

  return (
    <div className="play-timeline">
      <div className="timeline-filters">
        <select onChange={(e) => setPeriod(e.target.value ? Number(e.target.value) : undefined)} value={period ?? ""}>
          <option value="">All Periods</option>
          {[1, 2, 3, 4].map((p) => <option key={p} value={p}>Q{p}</option>)}
        </select>
        <select onChange={(e) => setPlayType(e.target.value)} value={playType ?? "all"}>
          {PLAY_TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>{t === "all" ? "All Play Types" : t.replace(/_/g, " ")}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="loading-text">Loading plays…</p>}

      <div className="plays-list">
        {data?.plays.map((play) => (
          <div key={play.id} className={`play-row play-type-${play.play_type}`}>
            <span className="play-period">Q{play.period}</span>
            <span className="play-clock">{play.clock}</span>
            <span className="play-desc">{play.description}</span>
            {play.home_score != null && (
              <span className="play-score">{play.away_score}–{play.home_score}</span>
            )}
          </div>
        ))}
      </div>

      {data && <p className="plays-count">{data.total} total plays</p>}
    </div>
  );
}

export default memo(PlayTimeline);
