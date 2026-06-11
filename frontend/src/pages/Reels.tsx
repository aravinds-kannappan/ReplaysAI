import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { useGames } from "../hooks/useGames";
import { useFeed } from "../hooks/usePredictions";
import { getLocalFavoriteTeams } from "../hooks/useUser";
import ScoreCard from "../components/ScoreCard";
import StoryReelPlayer, { type Story } from "../components/StoryReelPlayer";
import { apiPath } from "../lib/api";
import type { Game } from "../types";

type League = "NBA" | "NFL";

type Cut = {
  label: string;
  duration_seconds: number;
  story: Story;
};

const CV_TAGS = {
  NBA: ["Comeback story", "Star takeover", "Clutch run", "Defensive collapse", "Full summary"],
  NFL: ["Comeback story", "QB duel", "Defensive battle", "Explosive plays", "Full summary"],
};

const QUICK_PROMPTS = [
  ["30s punchline", "Give me the 30 second emotional punchline of this game"],
  ["2 min story", "Make the 2 minute story reel of this game"],
  ["5 min mini-doc", "Make a 5 minute mini-documentary of this game"],
  ["10 min deep dive", "Make the 10 minute deep tactical story of this game"],
];

function ReelAgentChat({
  gameId,
  onStory,
}: {
  gameId: number;
  onStory: (story: Story) => void;
}) {
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState<{ role: "user" | "assistant"; text: string }[]>([
    {
      role: "assistant",
      text: "Tell me the reel you want from this game — the storyline (a comeback, a star's takeover, the full game) and how deep to go: 30 seconds, 2, 5, or 10 minutes.",
    },
  ]);

  async function send(prompt: string) {
    if (!prompt || loading) return;
    const history = [...log, { role: "user" as const, text: prompt }];
    setLog(history);
    setLoading(true);
    try {
      const res = await axios.post(apiPath(`/api/games/${gameId}/reels/generate`), {
        prompt,
        messages: history,
      });
      if (res.data.action === "ask") {
        setLog((prev) => [...prev, { role: "assistant", text: res.data.question }]);
      } else {
        const story: Story = res.data.story;
        setLog((prev) => [...prev, { role: "assistant", text: `${res.data.note}. Rolling it now — ${story.scene_count} scenes.` }]);
        onStory(story);
      }
    } catch {
      setLog((prev) => [...prev, {
        role: "assistant",
        text: "I couldn't build that reel because play-by-play is not available for this game yet. Try a live or finished game.",
      }]);
    } finally {
      setLoading(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const prompt = draft.trim();
    setDraft("");
    void send(prompt);
  }

  return (
    <div className="chat-shell reel-agent">
      <div className="chat-log">
        {log.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`chat-bubble ${message.role}`}>{message.text}</div>
        ))}
      </div>
      <div className="quick-prompts">
        {QUICK_PROMPTS.map(([label, prompt]) => (
          <button key={label} disabled={loading} onClick={() => void send(prompt)}>{label}</button>
        ))}
      </div>
      <form className="chat-form" onSubmit={submit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="e.g. 2 minute reel of Wembanyama taking over..."
        />
        <button type="submit" disabled={loading}>{loading ? "directing..." : "Send"}</button>
      </form>
    </div>
  );
}

export default function Reels() {
  const [league, setLeague] = useState<League>("NBA");
  const [mode, setMode] = useState<"studio" | "cuts" | "explain">("studio");
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [story, setStory] = useState<Story | null>(null);
  const { data } = useGames({ sport: league, limit: 8 });
  const { data: feed } = useFeed();

  // Favorite-team games come first: the feed is already filtered to the teams
  // picked in onboarding, so reels build around them by default.
  const hasFavorites = getLocalFavoriteTeams().length > 0;
  const favoriteGames = ((feed?.games ?? []) as Game[]).filter((game) => game.sport === league);
  const leagueGames = data?.games ?? [];
  const sourceGames = hasFavorites && favoriteGames.length > 0 ? favoriteGames : leagueGames;
  // Scheduled games have no play-by-play yet, so default to the latest
  // finished or live game unless the user explicitly picks one.
  const playableGames = sourceGames.filter((game) => game.status !== "scheduled");
  const featuredGame = sourceGames.find((game) => game.id === selectedGameId) ?? playableGames[0] ?? sourceGames[0];

  // Story manifests are built as soon as a game is featured (often already
  // prefetched by onboarding), not only after the cuts tab is opened.
  const { data: reelData, isLoading: reelsLoading } = useQuery({
    queryKey: ["reel-cuts", featuredGame?.id],
    queryFn: () => axios.get(apiPath(`/api/games/${featuredGame?.id}/reels`)).then((r) => r.data),
    enabled: !!featuredGame?.id,
    staleTime: 300_000,
  });
  const featuredTitle = featuredGame
    ? `${featuredGame.away_team.abbreviation} @ ${featuredGame.home_team.abbreviation}`
    : "";

  return (
    <div className={`experience-page league-${league.toLowerCase()}`}>
      <header className="experience-hero">
        <div>
          <p className="dashboard-kicker">Story reel studio</p>
          <h1>{league} games, retold by agents</h1>
          <p>The agent reads the play-by-play, finds the storyline, and rebuilds the game as an animated story — score swings, key possessions, stat overlays, and narration that explains why each moment mattered.</p>
        </div>
        <div className="league-switch">
          {(["NBA", "NFL"] as League[]).map((item) => (
            <button key={item} className={league === item ? "active" : ""} onClick={() => setLeague(item)}>{item}</button>
          ))}
        </div>
      </header>

      <div className="inner-tabs">
        {[
          ["studio", "Reel Studio"],
          ["cuts", "2 / 5 / 10 Min Reels"],
          ["explain", "Explain The Game"],
        ].map(([id, label]) => (
          <button key={id} className={mode === id ? "active" : ""} onClick={() => setMode(id as typeof mode)}>{label}</button>
        ))}
      </div>

      <section className="reels-stage">
        <div className="reel-screen">
          <div className="scan-line" />
          <div className="frame-target target-one" />
          <div className="frame-target target-two" />
          <div className="reel-copy">
            <span>Story engine</span>
            <strong>
              {mode === "cuts"
                ? "30 seconds is the punchline. 2 minutes is the narrative. 10 minutes is the documentary."
                : mode === "explain"
                  ? "Slow the game down and explain why each moment mattered"
                  : "Play-by-play in, storyline out: comebacks, takeovers, collapses, duels"}
            </strong>
            <p>The agent decides what the reel should focus on, then writes scene-by-scene narration grounded in the real data — the longer the reel, the deeper the story becomes.</p>
          </div>
        </div>
        <aside className="reel-controls">
          <strong>Storylines the agent detects</strong>
          <div className="cv-tags">
            {CV_TAGS[league].map((tag) => <span key={tag}>{tag}</span>)}
          </div>
        </aside>
      </section>

      {mode === "cuts" && (
        <section className="dashboard-panel">
          <div className="panel-heading">
            <div>
              <span>Agent-built story reels</span>
              <h2>{featuredGame ? `${featuredTitle} — 2, 5, and 10 minute stories` : "Choose a game source"}</h2>
            </div>
          </div>

          {story && featuredGame && (
            <StoryReelPlayer
              story={story}
              awayAbbr={featuredGame.away_team.abbreviation || "AWY"}
              homeAbbr={featuredGame.home_team.abbreviation || "HME"}
              onClose={() => setStory(null)}
            />
          )}

          {reelsLoading && <p className="loading-text">Reading the play-by-play and building stories...</p>}
          {!featuredGame && <p className="empty-state">No game available for reel generation yet.</p>}
          <div className="summary-list">
            {(reelData?.cuts as Cut[] | undefined)?.map((cut) => (
              <div key={cut.label} className="summary-row reel-cut-row">
                <div>
                  <strong>{cut.label} · {cut.story.scene_count} scenes · ~{Math.round(cut.story.duration_seconds / 60)} min</strong>
                  <span>{cut.story.title}</span>
                </div>
                <button className="btn-primary reel-play-btn" onClick={() => setStory(cut.story)}>
                  ▶ Play story
                </button>
              </div>
            ))}
            {reelData && (reelData.cuts?.length ?? 0) === 0 && (
              <p className="empty-state">Play-by-play has not published for this game yet.</p>
            )}
          </div>

          <div className="panel-heading reel-agent-heading">
            <div>
              <span>Reel director</span>
              <h2>Prompt the reel you want</h2>
            </div>
          </div>
          {featuredGame && (
            <ReelAgentChat
              key={featuredGame.id}
              gameId={featuredGame.id}
              onStory={setStory}
            />
          )}
        </section>
      )}

      <section className="dashboard-panel">
        <div className="panel-heading">
          <div>
            <span>Game source</span>
            <h2>{hasFavorites && favoriteGames.length > 0 ? "Your teams' games" : "Attach reels to real games"}</h2>
          </div>
        </div>
        <div className="games-grid compact">
          {sourceGames.map((game) => (
            <div key={game.id} className={`reel-source${featuredGame?.id === game.id ? " selected" : ""}`}>
              <ScoreCard game={game} />
              <button
                className="btn-ghost"
                onClick={() => {
                  setSelectedGameId(game.id);
                  setStory(null);
                  setMode("cuts");
                }}
              >
                {featuredGame?.id === game.id ? "Stories shown above" : "Build story reels"}
              </button>
            </div>
          ))}
        </div>
        {sourceGames.length === 0 && (
          <p className="empty-state">No {league} games returned yet. Stored ingestions and ESPN public schedules will appear here as soon as either source has games.</p>
        )}
      </section>

      <section className="agent-motion-row">
        {["Read plays", "Find storyline", "Write scenes", "Roll reel"].map((step) => (
          <div key={step} className="motion-node">
            <span />
            <strong>{step}</strong>
          </div>
        ))}
        <Link to="/feed" className="motion-link">Send to feed</Link>
      </section>
    </div>
  );
}
