import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { useRecap, triggerRecapGeneration } from "../hooks/useGames";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  gameId: number;
  gameStatus: string;
}

export default function RecapViewer({ gameId, gameStatus }: Props) {
  const { data, isLoading, refetch } = useRecap(gameId);
  const [generating, setGenerating] = useState(false);
  const queryClient = useQueryClient();

  async function handleGenerate() {
    setGenerating(true);
    try {
      await triggerRecapGeneration(gameId);
      // poll for result every 5s
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        await refetch();
        const updated = queryClient.getQueryData<{ content: string | null }>(["recap", gameId]);
        if (updated?.content || attempts > 24) {
          clearInterval(interval);
          setGenerating(false);
        }
      }, 5000);
    } catch {
      setGenerating(false);
    }
  }

  if (isLoading) {
    return <div className="recap-placeholder">Loading recap...</div>;
  }

  if (!data?.content) {
    return (
      <div className="recap-placeholder">
        <p>No recap generated yet.</p>
        {(gameStatus === "final" || gameStatus === "live") && (
          <button
            className="btn-generate"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating recap… (this takes ~30s)" : "Generate AI Recap"}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="recap-content">
      <ReactMarkdown>{data.content}</ReactMarkdown>
      {data.cv_classifications !== undefined && (
        <p className="recap-meta">
          {data.cv_classifications} notable plays shaped this recap
        </p>
      )}
    </div>
  );
}
