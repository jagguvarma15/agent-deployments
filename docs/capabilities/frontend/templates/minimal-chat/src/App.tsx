import { useEffect, useState, type FormEvent } from "react";

// The backend URL. The scaffold wires VITE_AGENT_URL to the host-mapped backend
// port; the default works for the local docker sandbox (backend on :8000).
const AGENT_URL: string =
  (import.meta.env.VITE_AGENT_URL as string | undefined) ?? "http://localhost:8000";

// The agent's display name (scaffold passes VITE_AGENT_TITLE).
const AGENT_TITLE: string =
  (import.meta.env.VITE_AGENT_TITLE as string | undefined) ?? "Agent Chat";
document.title = AGENT_TITLE;

interface Msg {
  role: "user" | "agent";
  text: string;
}

interface Field {
  name: string;
  required: boolean;
  hint: string;
  set: boolean;
}

// null = ready (show the chat). Otherwise a full-screen gate replaces the chat.
type Gate = { type: "setup"; setupUrl: string; fields: Field[] } | { type: "unreachable" } | null;

function absUrl(path: string): string {
  return path.startsWith("http") ? path : `${AGENT_URL}${path}`;
}

// The secure-setup URL with a validated return_to (so the backend redirects back
// here after saving) and an optional error to display. Secrets are entered on
// that page and POSTed to the backend — never held in this chat page.
function setupHref(setupUrl: string, error?: string): string {
  const base = absUrl(setupUrl);
  const sep = base.includes("?") ? "&" : "?";
  const ret = `return_to=${encodeURIComponent(window.location.href)}`;
  const err = error ? `&error=${encodeURIComponent(error)}` : "";
  return `${base}${sep}${ret}${err}`;
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
  const [gate, setGate] = useState<Gate>(null);
  const [checking, setChecking] = useState(true);

  async function checkReady(): Promise<void> {
    setChecking(true);
    try {
      const res = await fetch(`${AGENT_URL}/ready`);
      if (!res.ok) {
        setGate(null); // backend without a /ready endpoint — don't block the chat
        return;
      }
      const data = (await res.json()) as { ready?: boolean; setup_url?: string; fields?: Field[] };
      if (data.ready) setGate(null);
      else setGate({ type: "setup", setupUrl: data.setup_url ?? "/setup", fields: data.fields ?? [] });
    } catch {
      setGate({ type: "unreachable" });
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    void checkReady();
    // Re-check when the user returns to this tab (e.g. back from the setup page).
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
      if (res.status === 409) {
        // Missing or invalid credential → go to the secure setup page (full-page
        // redirect; the backend sends us back here, and /ready re-checks).
        let path = "/setup";
        let error: string | undefined;
        try {
          const d = (await res.json()) as { setup_url?: string; error?: string };
          if (typeof d.setup_url === "string") path = d.setup_url;
          if (typeof d.error === "string") error = d.error;
        } catch {
          /* defaults */
        }
        window.location.href = setupHref(path, error);
        return;
      }
      const reply = res.ok ? await readReply(res) : `Request failed (${res.status}).`;
      setMessages((m) => [...m, { role: "agent", text: reply }]);
    } catch {
      setGate({ type: "unreachable" });
      setMessages((m) => [
        ...m,
        { role: "agent", text: `Can't reach the agent at ${AGENT_URL}. Is it running?` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  // --- Full-screen gates (replace the chat until the agent can communicate) ---

  if (gate?.type === "unreachable") {
    return (
      <div className="app gate">
        <div className="gate-card">
          <h1>Can't reach the agent</h1>
          <p>
            The backend at <code>{AGENT_URL}</code> isn't responding. Make sure the stack is up:
          </p>
          <pre>docker compose up</pre>
          <button type="button" onClick={() => void checkReady()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (gate?.type === "setup") {
    const required = gate.fields.filter((f) => f.required);
    const optional = gate.fields.filter((f) => !f.required);
    const renderRows = (fields: Field[]) =>
      fields.map((f) => (
        <li key={f.name}>
          <code>{f.name}</code>
          {f.hint ? ` — ${f.hint}` : ""}
        </li>
      ));
    return (
      <div className="app gate">
        <div className="gate-card">
          <h1>Set up {AGENT_TITLE}</h1>
          <p>
            This agent needs a few environment values before it can reply. You'll enter them on a{" "}
            <strong>secure page</strong> — they go straight to the agent's backend, never into this
            chat.
          </p>
          {required.length > 0 && (
            <>
              <h3>Required</h3>
              <ul>{renderRows(required)}</ul>
            </>
          )}
          {optional.length > 0 && (
            <>
              <h3>Optional</h3>
              <ul>{renderRows(optional)}</ul>
            </>
          )}
          <button type="button" onClick={() => (window.location.href = setupHref(gate.setupUrl))}>
            Configure →
          </button>
        </div>
      </div>
    );
  }

  if (checking) {
    return (
      <div className="app gate">
        <div className="gate-card">
          <p>Checking agent…</p>
        </div>
      </div>
    );
  }

  // --- Ready: the chat ---

  return (
    <div className="app">
      <header>
        <h1>{AGENT_TITLE}</h1>
        <span className="endpoint">{AGENT_URL}</span>
        <a className="settings" href={setupHref("/setup")} title="Configure environment">
          ⚙
        </a>
      </header>
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
