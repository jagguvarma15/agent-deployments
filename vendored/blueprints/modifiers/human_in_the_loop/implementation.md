# Human in the Loop — Implementation

Two concrete implementations of the same proposal flow:

1. **LangGraph `interrupt()` + Slack** — async-resume; the agent persists state, surfaces the proposal to Slack, and resumes when the decision webhook fires.
2. **Web admin queue** — sync from the operator's perspective; richer context display; suitable for high-context manager-tier approvals.

Reference Python code in [`code/python/approval.py`](code/python/approval.py) implements the in-memory equivalent of (1) with three approver surfaces — start there.

---

## LangGraph `interrupt()` + Slack

LangGraph's `interrupt` primitive is purpose-built for HITL: pause the graph, persist state via the checkpointer, resume from a new invocation with the decision injected.

### State

```python
from typing import TypedDict, Literal, Any

class CaseState(TypedDict):
    case_id: str
    proposal: dict | None
    decision: Literal["pending", "approved", "denied", "modified", "timed_out"] | None
    decision_metadata: dict | None
    result: dict | None
```

### Graph

```python
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command

def propose_node(state: CaseState) -> CaseState:
    proposal = build_proposal(state["case_id"])
    state["proposal"] = proposal
    if not needs_review(proposal):
        state["decision"] = "approved"   # auto-approved (low-risk path)
    return state

def gate_node(state: CaseState) -> CaseState | Command:
    if state["decision"] == "approved":
        return state                     # already auto-approved
    # Persist + surface; interrupt blocks the graph here.
    surface_to_slack(
        proposal_id=state["case_id"],
        proposal=state["proposal"],
        channel="#rebooking-approvals",
    )
    decision_payload = interrupt({
        "kind": "awaiting_approval",
        "proposal_id": state["case_id"],
        "ttl_seconds": 900,
    })
    state["decision"] = decision_payload["outcome"]
    state["decision_metadata"] = decision_payload
    return state

def execute_node(state: CaseState) -> CaseState:
    if state["decision"] in ("approved", "modified"):
        proposal = state["proposal"]
        if state["decision"] == "modified":
            proposal = apply_modification(proposal, state["decision_metadata"]["modification"])
        state["result"] = execute(proposal)
    else:
        state["result"] = {"status": "declined", "reason": state["decision"]}
    return state

graph = StateGraph(CaseState)
graph.add_node("propose", propose_node)
graph.add_node("gate", gate_node)
graph.add_node("execute", execute_node)
graph.add_edge("propose", "gate")
graph.add_edge("gate", "execute")
graph.add_edge("execute", END)
graph.set_entry_point("propose")
agent = graph.compile(checkpointer=postgres_saver)
```

### Slack webhook handler

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhooks/slack/approval")
async def slack_approval(req: Request):
    payload = await parse_slack_signed_payload(req)   # verify signature, dedupe
    proposal_id = payload["proposal_id"]
    decision = {
        "outcome": payload["action_id"],              # "approved" | "denied" | "modified"
        "approver": payload["user"]["email"],
        "approver_pool": payload["channel"],
        "decided_at": utcnow(),
        "decided_in_seconds": int(time.time() - payload["proposal_created_at"]),
        "modification": payload.get("modification"),
    }
    # Resume the agent with the decision injected.
    config = {"configurable": {"thread_id": proposal_id}}
    await agent.ainvoke(Command(resume=decision), config=config)
    # Persist to audit log.
    await audit_log.append(proposal_id=proposal_id, **decision)
    return {"ok": True}
```

### TTL handler

A scheduled job (cron or KEDA-driven) scans for stuck proposals and applies the escalation policy:

```python
async def expire_stuck_proposals():
    stuck = await db.fetch("""
        SELECT proposal_id, escalation_policy, escalation_target
        FROM proposals
        WHERE state = 'pending' AND expires_at < now()
    """)
    for row in stuck:
        if row["escalation_policy"] == "auto_approve":
            decision = {"outcome": "approved", "approver": "system:ttl_expired"}
        elif row["escalation_policy"] == "auto_deny":
            decision = {"outcome": "denied", "approver": "system:ttl_expired"}
        elif row["escalation_policy"] == "escalate":
            await surface_to_slack(
                proposal_id=row["proposal_id"],
                channel=row["escalation_target"],
                escalated_from=row["original_target"],
            )
            await db.execute(
                "UPDATE proposals SET expires_at = $1, escalation_level = escalation_level + 1 "
                "WHERE proposal_id = $2",
                utcnow() + timedelta(minutes=15), row["proposal_id"],
            )
            continue
        # Inject decision back into the graph.
        config = {"configurable": {"thread_id": row["proposal_id"]}}
        await agent.ainvoke(Command(resume=decision), config=config)
        await audit_log.append(proposal_id=row["proposal_id"], **decision)
```

### Slack message shape

```json
{
  "channel": "#rebooking-approvals",
  "blocks": [
    {"type": "header", "text": {"type": "plain_text", "text": "Rebook approval — VIP customer"}},
    {"type": "section", "fields": [
      {"type": "mrkdwn", "text": "*Customer:* cust_7 (VIP tier)"},
      {"type": "mrkdwn", "text": "*Original:* Acme 7:00 PM party of 4"},
      {"type": "mrkdwn", "text": "*Proposed:* Acme 8:00 PM party of 4 (Resy)"},
      {"type": "mrkdwn", "text": "*Estimated value:* $245"}
    ]},
    {"type": "actions", "elements": [
      {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Approve"},
       "value": "approved", "action_id": "approved"},
      {"type": "button", "style": "danger", "text": {"type": "plain_text", "text": "Deny"},
       "value": "denied", "action_id": "denied"},
      {"type": "button", "text": {"type": "plain_text", "text": "Modify…"},
       "value": "modified", "action_id": "modified"}
    ]}
  ]
}
```

The `value` and `action_id` carry the outcome back; the webhook handler parses them.

---

## Web admin queue variant

For higher-context decisions (manager-tier refund approval, compliance override), Slack's tile size is too small. A web admin queue lets you render full case context.

### Pattern

```text
GET  /admin/approvals?pool=managers           → paginated list of pending proposals
GET  /admin/approvals/{proposal_id}           → full context: case timeline, related cases, agent reasoning
POST /admin/approvals/{proposal_id}/decision  → {outcome, modification?, reason?}
```

The POST endpoint is the same shape as the Slack webhook — same decision shape, same audit-log append, same agent resume. The surface differs; the gate's contract doesn't.

### Approver pool routing

```sql
CREATE TABLE approver_pools (
    pool_id        TEXT PRIMARY KEY,
    members        TEXT[] NOT NULL,                -- email or user_id list
    surface        TEXT NOT NULL,                  -- "slack:#channel" | "web" | "email"
    sla_minutes    INT NOT NULL,
    escalation_to  TEXT REFERENCES approver_pools(pool_id)
);
```

A proposal's `approver_pool` decides who can decide it and where they see it. RBAC enforcement: the webhook handler must verify the responding approver is a member of the proposal's pool (else any Slack user could approve anything). Cross-cutting: `agent-deployments/docs/cross-cutting/authorization-rbac.md`.

---

## Testing

- **Happy-path test** — agent reaches gate; inject `Command(resume={"outcome": "approved", ...})`; assert agent commits the action.
- **Denial test** — inject `denied`; assert agent terminates without executing.
- **Modification test** — inject `modified` with a payload tweak; assert the executed action reflects the modification.
- **Timeout test** — let the TTL expire with `escalation_policy=auto_deny`; assert the timeout handler injects a denial and the agent terminates.
- **Crash-resilience test** — fire a proposal; kill the agent process; restart; assert the second process sees the pending proposal and resumes correctly when the decision arrives.
- **Concurrent-approval test** — two approvers click "approve" within milliseconds; assert idempotency: exactly one execution, exactly one audit entry (the first wins; the second gets a clear "already decided" response).
- **Authorization test** — non-member of the approver pool tries to decide; assert the webhook returns 403 and no resume occurs.

---

## Operational handles

- **Stuck-proposal alert** — any proposal `pending` past 2× its TTL pages the on-call; the timeout handler should have caught it. If it didn't, the handler itself is broken.
- **Approver-throughput dashboard** — per-pool: P50/P95 time-to-decide, approval rate, modification rate. Used to size approver pools and tune escalation TTLs.
- **Decision-override tool** — operator CLI to re-decide a proposal (with audit) if the original approver clicked the wrong button. Locked behind elevated RBAC.
- **Bypass mode** — for incidents, a documented procedure to disable the gate temporarily (`POST /admin/approvals/bypass?reason=...`). Logged + alerted.
