# Agent Chat (Vite + React + TypeScript)

The minimal default chat UI for the generated agent. It talks to the backend's
`POST /chat` endpoint and renders the reply.

## In the docker sandbox (default)

Brought up automatically as the `frontend` container alongside the backend:

```bash
agent-scaffold up        # or /up in the scaffold REPL
```

- Frontend: http://localhost:3000
- Backend:  http://localhost:8000

## Local dev (without docker)

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000
```

## Configuration

- `VITE_AGENT_URL` — the backend base URL the browser calls. Defaults to
  `http://localhost:8000`. Baked at build time (Vite client env); override with
  `--build-arg VITE_AGENT_URL=...` or a `.env` for local dev.

## Backend contract

Sends `POST {VITE_AGENT_URL}/chat` with `{"message": "<text>"}` and renders the
response — JSON `{"reply": "..."}` / `{"answer": "..."}` or plain text. The agent
backend should expose a `POST /chat` route.
