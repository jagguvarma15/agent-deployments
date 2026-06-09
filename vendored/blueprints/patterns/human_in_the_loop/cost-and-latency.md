# Cost & Latency: Human in the Loop

The pattern's compute cost is essentially zero. Its dominant constraint is **human wall-clock time**: a HITL gate's latency floor is "how long until the human looks at Slack." The interesting design work is sizing the approver pool and tuning TTLs so SLA targets are met without burning out the humans.

---

## At a Glance

|                                  | Typical (P50 estimate)             | High end (P95 estimate)           |
|----------------------------------|------------------------------------|-----------------------------------|
| Compute cost per gated proposal  | ~$0 (no LLM call inside the gate) | ~$0                               |
| Surface delivery latency         | 100ms – 2s                         | 5s+ (rate-limited Slack / SMTP)   |
| Time-to-decision (Slack)         | 1–10 min                           | 30+ min (off-hours)               |
| Time-to-decision (email)         | 30–120 min                         | 4+ hours                          |
| Time-to-decision (web queue)     | 5–30 min                           | 2+ hours                          |
| Cost per 1,000 proposals (infra) | < $0.10                            | < $1                              |

Relative cost tier: Low (matches `metadata.json`). Latency tier: very-high — the gate's median latency is in **minutes**, not milliseconds.

---

## Per-Gate Cost Breakdown

The compute footprint of a gate is tiny. The expensive resource is **approver attention**, which doesn't show up on the AWS bill.

| Component                | Source                                              | Typical $ per 1k proposals |
|--------------------------|------------------------------------------------------|----------------------------|
| Pending store writes     | One INSERT per proposal + one UPDATE per decision    | < $0.01                    |
| Surface delivery         | Slack webhook / SMTP / WebSocket push                | < $0.10                    |
| Decision webhook handling| One POST per decision                                | < $0.01                    |
| Audit log append         | One INSERT per decision                              | < $0.01                    |
| LLM cost                 | Zero (the gate itself doesn't call LLMs)             | $0                         |

The proposal-creation step before the gate may have an LLM cost (the agent reasoned its way to the proposal) and the post-decision execute step may have an LLM cost (if the action is itself LLM-driven). The gate itself doesn't.

The *real* cost is approver minutes:

| Approver class | Loaded cost / hour | Cost per decision (5 min avg) |
|----------------|--------------------:|-------------------------------:|
| Ops engineer   | $80                | $7                             |
| Manager        | $120               | $10                            |
| Compliance officer | $200            | $17                            |
| Specialist (legal, finance) | $300+ | $25+                           |

A gate that fires 100 times a day with a manager-tier approver costs ~$1,000/day in human time. That's the budget every "should we add this gate?" decision is implicitly weighed against.

---

## Latency Breakdown

Wall-clock time, single proposal:

| Stage                       | Typical | Notes                                                  |
|----------------------------|---------|--------------------------------------------------------|
| Proposal create + persist  | 5–20ms  | DB INSERT                                              |
| Surface delivery           | 100ms–2s | Slack webhook usually < 1s; email queue up to 5s     |
| **Human review + decide**  | **1–120 min** | Dominant component; covered below                |
| Decision webhook + resume  | 10–50ms | DB UPDATE + agent resume via checkpointer              |
| Audit append               | 5–20ms  | One INSERT                                             |

Time-to-decision per surface (rule-of-thumb production data):

| Surface | P50 | P95 | Typical SLA target |
|---------|-----|-----|---------------------|
| CLI prompt (live ops) | 5–30s | 2 min | 60s |
| Slack (active channel, business hours) | 2 min | 15 min | 15 min |
| Slack (off-hours) | 30 min | 4 hours | 1 hour (after which: escalate) |
| Email | 60 min | 6 hours | 4 hours |
| Web admin queue (checked hourly) | 30 min | 2 hours | 1 hour |
| Web admin queue (checked daily) | 4 hours | 24 hours | 8 hours (most don't fit a same-day SLA) |

Pick the surface to match the SLA. Asking for a 5-minute decision via email is asking for the timeout policy to fire.

---

## What Drives Cost Up

- **Over-flagging.** A `needs_review` policy that flags 50% of actions burns approver attention; track `approval_rate` per gate and tighten the policy when it's > 90% (most flags are no-ops; the gate isn't doing useful work).
- **Expensive approver class.** Routing routine $50 decisions to a compliance officer at $200/hr is overkill; route by value tier — ops engineers handle the bulk, specialists only see the cases that genuinely need them.
- **Long TTLs paired with escalation.** A proposal that escalates from L1 → L2 → L3 burns 3× the approver minutes for a single decision; track `escalation_rate` and fix the L1 staffing if it's > 15%.
- **Re-deliveries on retry.** A flaky webhook that loses decisions causes the surface to re-deliver; approvers see duplicates and lose trust in the channel. Idempotent webhook handlers fix this.

---

## What Drives Latency Up

- **Wrong surface for the SLA.** Sending a Slack message to a channel nobody monitors yields email-tier latency. Match surface to attentiveness.
- **TTL too short.** Most decisions auto-deny / auto-approve before the actual approver responds; the cost is wrong decisions, not lower latency.
- **No on-call rotation.** A pool of 5 approvers where only 1 is paying attention has effectively the latency of 1 approver. Wire approver pools to the on-call schedule.
- **High proposal volume hits a fixed approver pool.** Approvers serialize on their own attention. Volume-spike → queue depth → P95 climbs.
- **Approver context-switch cost.** Each proposal includes "load the case → understand → decide." Richer pre-rendered context (the web admin queue's full timeline view, vs Slack's small tile) cuts this materially.

---

## Cost & Latency Control Knobs

**Tighten the `needs_review` policy.** Every gated action that didn't need a human is wasted attention. Track the `approval_rate` per proposal class; if > 95%, the gate is theatre — remove the gate or raise the threshold. If < 30%, the gate is correctly catching dangerous proposals; investigate why the agent is producing so many.

**Route by approver class.** A tiered policy ("ops for < $200, manager for $200–$1000, compliance for > $1000") puts the cheapest qualified approver in front of each proposal. Big savings on approver budget at minimal SLA cost.

**Pre-render context.** A Slack tile with 3 lines of context yields longer human-review time than a web UI with the full case timeline. Investing in surface quality reduces approver minutes per decision.

**Auto-approve the bottom tier with audit.** For the lowest-risk gated class, auto-approve immediately and emit the audit row for after-the-fact review. The team scans the audit log once a day; the gate's P50 latency drops to zero for that class.

**Match TTL to the actual P95 response time per surface.** Pull metrics, set TTL to ~1.3× P95. Below that and timeouts fire on legitimate slow approvals; above that and bad approvals stay open longer.

**Pool sizing formula.** Required-pool-size ≈ `(daily_proposals × avg_decision_minutes) / (approver_hours_per_day × 60)`, then 2× for headroom. 100 proposals/day × 5 min ÷ (8 hr × 60 min/hr) × 2 = ~2 approvers. Track actual utilization and adjust.

---

## Comparison to Related Patterns

| Pattern         | Est. LLM calls | Est. cost tier | Est. latency  | Best when                                              |
|-----------------|----------------|----------------|---------------|--------------------------------------------------------|
| Tool Use        | 2+ per round   | Low-Medium     | Low           | Auto-execute is safe                                   |
| Reflection      | 2-N per task   | Medium         | Low-Medium    | The agent can critique itself; no governance need      |
| Saga            | 1 per step     | Medium         | Medium-High   | Multi-step with compensation                           |
| Human-in-the-Loop | 0 in the gate | Low (compute) / Variable (humans) | **Very high** (minutes-hours) | Action needs a named human accountable; compliance + irreversible work |

The distinctive cost shape of HITL: **compute cost is decoupled from value at risk**. Gating a $5 action and a $5000 action both cost the same compute; the gate's job is to make the human-attention spend correlate with the value at risk.
