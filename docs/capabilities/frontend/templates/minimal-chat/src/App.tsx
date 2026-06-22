import { useEffect, useState, type FormEvent } from "react";

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

interface SetupState {
  url: string;
  missing: string[];
}

function absUrl(path: string): string {
  return path.startsWith("http") ? path : `${AGENT_URL}${path}`;
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
  // Proactive readiness: the backend's /setup URL + which required vars are still
  // missing (null = ready, or no setup endpoint); and whether the backend is
  // reachable at all (distinguishes "needs config" from "not running").
  const [setup, setSetup] = useState<SetupState | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  async function checkReady(): Promise<void> {
    try {
      const res = await fetch(`${AGENT_URL}/ready`);
      setUnreachable(false);
      if (!res.ok) {
        setSetup(null); // backend without a /ready endpoint — don't block
        return;
      }
      const data = (await res.json()) as {
        ready?: boolean;
        missing_required?: string[];
        setup_url?: string;
      };
      if (data.ready) {
        setSetup(null);
      } else {
        setSetup({
          url: absUrl(data.setup_url ?? "/setup"),
          missing: Array.isArray(data.missing_required) ? data.missing_required : [],
        });
      }
    } catch {
      setUnreachable(true); // couldn't reach the backend at all
    }
  }

  useEffect(() => {
    void checkReady();
    // Re-check when the user returns from the /setup tab (focus the window).
    const onFocus = () => void checkReady();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      setUnreachable(false);
      if (res.status === 409) {
        let path = "/setup";
        try {
          const data = (await res.json()) as { setup_url?: string };
          if (typeof data.setup_url === "string") path = data.setup_url;
        } catch {
          /* fall back to /setup */
        }
        setSetup({ url: absUrl(path), missing: [] });
        setMessages((m) => [
          ...m,
          {
            role: "agent",
            text: `I'm not configured yet — use "Configure your agent" above, then send again.`,
          },
        ]);
      } else {
        const reply = res.ok
          ? await readReply(res)
          : `Request failed (${res.status}).`;
        if (res.ok) setSetup(null); // working now — hide the banner
        setMessages((m) => [...m, { role: "agent", text: reply }]);
      }
    } catch {
      setUnreachable(true);
      setMessages((m) => [
        ...m,
        {
          role: "agent",
          text: `Can't reach the agent at ${AGENT_URL}. Is it running? Try \`docker compose up\`.`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const banner = unreachable ? (
    <div className="setup-banner unreachable">
      <span>
        Can't reach the agent at {AGENT_URL} — is it running? Try <code>docker compose up</code>.
      </span>
      <button type="button" onClick={() => void checkReady()}>
        Retry
      </button>
    </div>
  ) : setup ? (
    <div className="setup-banner">
      <span>
        Configure your agent{setup.missing.length ? ` — missing: ${setup.missing.join(", ")}` : ""}.
      </span>
      <span className="actions">
        <button type="button" onClick={() => window.open(setup.url, "_blank", "noopener")}>
          Configure
        </button>
        <button type="button" className="ghost" onClick={() => void checkReady()}>
          Re-check
        </button>
      </span>
    </div>
  ) : null;

  return (
    <div className="app">
      <header>
        <h1>{AGENT_TITLE}</h1>
        <span className="endpoint">{AGENT_URL}</span>
      </header>
      {banner}
      <main className="messages">
        {messages.length === 0 && <p className="empty">Say hello to your agent…</p>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.text}</div>
          </div>
        ))}
        {busy && (
          <div className="msg agent">
            <div className="bubble">…</div>
          </div>
        )}
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
