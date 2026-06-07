import { useState, type FormEvent } from "react";
import { SignedIn } from "@clerk/clerk-react";

type Message = { role: "assistant" | "user"; text: string };

export default function FloatingAssistant() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "I can help pick teams, compare players, explain reels, or turn a game into a prediction." },
  ]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    setMessages((prev) => [
      ...prev,
      { role: "user", text },
      { role: "assistant", text: "Got it. I would start with your selected league, favorite teams, and the latest games on the current tab, then make the next action obvious." },
    ]);
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
              <button type="submit">Send</button>
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
