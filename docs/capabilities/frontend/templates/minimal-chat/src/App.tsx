import { useState, type FormEvent } from "react";

// The backend URL. The scaffold wires VITE_AGENT_URL to the host-mapped backend
// port; the default works for the local docker sandbox (backend on :8000).
const AGENT_URL: string =
  (import.meta.env.VITE_AGENT_URL as string | undefined) ?? "http://localhost:8000";

// The agent's display name. The scaffold derives it from the "describe your
// agent" step and passes it as the VITE_AGENT_TITLE build arg.
const AGENT_TITLE: string =
  (import.meta.env.VITE_AGENT_TITLE as string | undefined) ?? "Agent Chat";
document.title = AGENT_TITLE;

interface Msg {
  role: "user" | "agent";
  text: string;
}

/** Pull the reply text out of whatever shape the backend returns. */
async function readReply(res: Response): Promise<string> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    const data = (await res.json()) as Record<string, unknown>;
    const reply = data.reply ?? data.answer ?? data.message ?? data.output;
    return typeof reply === "string" ? reply : JSON.stringify(data, null, 2);
  }
  return res.text();
}

export function App() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const res = await fetch(`${AGENT_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const reply = res.ok
        ? await readReply(res)
        : `Request failed (${res.status}). Is the backend running at ${AGENT_URL}?`;
      setMessages((m) => [...m, { role: "agent", text: reply }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "agent", text: `Could not reach the agent at ${AGENT_URL}: ${String(err)}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>{AGENT_TITLE}</h1>
        <span className="endpoint">{AGENT_URL}</span>
      </header>
      <main className="messages">
        {messages.length === 0 && (
          <p className="empty">Say hello to your agent…</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.text}</div>
          </div>
        ))}
        {busy && <div className="msg agent"><div className="bubble">…</div></div>}
      </main>
      <form className="composer" onSubmit={send}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Message the agent…"
          autoFocus
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
