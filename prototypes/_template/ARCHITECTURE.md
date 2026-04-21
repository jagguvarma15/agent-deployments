# Architecture — <prototype-name>

## Data flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant Ag as Agent
    participant L as LLM
    participant T as Tools
    participant D as Database

    C->>A: POST /<endpoint>
    A->>Ag: Process request
    Ag->>L: Generate response
    L-->>Ag: Response
    Ag->>T: Call tool (if needed)
    T-->>Ag: Tool result
    Ag->>D: Persist state
    Ag-->>A: Result
    A-->>C: JSON response
```

## Component overview

| Component | Responsibility |
|-----------|---------------|
| `app/main.py` / `src/index.ts` | API entrypoint, middleware setup |
| `app/agent/` / `src/agent/` | Agent graph/logic |
| `app/api/` / `src/api/` | Route handlers |
| `app/models/` / `src/schemas/` | Request/response schemas |
| `app/tools/` / `src/tools/` | Tool implementations |
| `app/db/` / `src/db/` | Database models and migrations |

## Decision log

| Decision | Rationale |
|----------|-----------|
| | |
