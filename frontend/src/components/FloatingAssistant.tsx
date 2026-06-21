import { useEffect, useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import axios from "axios";
import { apiPath } from "../lib/api";
import { getLocalFavoriteTeams, getLocalFollowedPlayers } from "../hooks/useUser";

type Message = { role: "assistant" | "user"; text: string };

export default function FloatingAssistant() {
  const { getToken } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "I coordinate ReplaysAI's specialist agents: stats, predictions, reels, fan recaps, news, picks, and roster strategy. Ask for a detailed answer and I will ground it in your selected teams, players, and current page." },
  ]);

  useEffect(() => {
    function handlePrompt(event: Event) {
      const prompt = (event as CustomEvent<{ prompt?: string }>).detail?.prompt;
      if (!prompt) return;
      setOpen(true);
      setDraft(prompt);
    }
    window.addEventListener("replaysai:assistant-prompt", handlePrompt);
    return () => window.removeEventListener("replaysai:assistant-prompt", handlePrompt);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    const nextMessages = [...messages, { role: "user" as const, text }];
    setMessages(nextMessages);
    setLoading(true);
    try {
      const token = await getToken();
      const res = await axios.post(
        apiPath("/api/chat"),
        {
          message: text,
          context: `${window.location.pathname}${window.location.search}`,
          favorite_teams: getLocalFavoriteTeams().map((team) => `${team.sport}:${team.abbreviation}`),
          followed_players: getLocalFollowedPlayers().map((player) => `${player.sport}:${player.name}${player.team ? ` (${player.team})` : ""}`),
          messages: nextMessages,
        },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      setMessages((prev) => [...prev, { role: "assistant", text: res.data.reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", text: "I could not reach the assistant service yet. Check the backend environment and Anthropic key." }]);
    } finally {
      setLoading(false);
    }
  }

  // Keep the marketing landing page clean; the guide rides along everywhere else.
  if (pathname === "/") return null;

  return (
    <div className={`floating-assistant ${open ? "open" : ""}`}>
      {open && (
        <div className="floating-panel">
          <div className="floating-head">
            <strong>Replays Guide</strong>
            <button onClick={() => setOpen(false)}>Close</button>
          </div>
          <div className="floating-log">
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`floating-msg ${message.role}`}>
                {message.text}
              </div>
            ))}
          </div>
          <form className="floating-form" onSubmit={submit}>
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask for help..." />
            <button type="submit" disabled={loading}>{loading ? "..." : "Send"}</button>
          </form>
        </div>
      )}
      <button className="floating-launcher" onClick={() => setOpen((value) => !value)}>
        AI
      </button>
    </div>
  );
}
