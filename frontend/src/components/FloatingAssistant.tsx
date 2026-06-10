import { useState, type FormEvent } from "react";
import { SignedIn, useAuth } from "@clerk/clerk-react";
import axios from "axios";
import { apiPath } from "../lib/api";
import { getLocalFavoriteTeams } from "../hooks/useUser";

type Message = { role: "assistant" | "user"; text: string };

export default function FloatingAssistant() {
  const { getToken } = useAuth();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "I can help pick teams, compare players, explain reels, or turn a game into a prediction." },
  ]);

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

  return (
    <SignedIn>
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
    </SignedIn>
  );
}
