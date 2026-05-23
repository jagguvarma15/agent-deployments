# Cross-cutting: Authorization and RBAC

**Concern:** AuthN says "who you are"; AuthZ says "what you can do." JWT alone is just authentication — every protected action also needs an authorization check.
**Library:** stdlib enums + FastAPI `Depends` / Hono middleware; OPA (`opa-python-client`) for external policy.
**Lives in:** Inline below — pair with [auth-jwt.md](./auth-jwt.md) for the authn layer.

## What it provides

- A clear split between AuthN (proving identity) and AuthZ (checking permission).
- Three policy models — RBAC, ABAC, PBAC — with guidance on when each fits.
- A working FastAPI / Hono RBAC pattern.
- Agent-specific authorization: per-intent tool allowlists, per-user tool gating, action-approval gates.
- Tenant-scoped authorization with cross-tenant leak prevention.

## Authentication vs authorization

- **AuthN** — "Who is this?" Identity proof: JWT, mTLS, API key, session cookie. Covered by [auth-jwt.md](./auth-jwt.md).
- **AuthZ** — "Can this identity do this thing on this resource right now?" Evaluated per action, never assumed from authentication.

A user with a valid JWT is not authorized to do anything by virtue of having a token. Every endpoint, every tool call, every read of sensitive data needs its own check.

## Models

| Model | What decides | When to use |
|-------|--------------|-------------|
| **RBAC** (role-based) | User has roles; roles have permissions | Small fixed set of roles (admin / operator / viewer). Simplest and good enough for most internal tools. |
| **ABAC** (attribute-based) | Attributes of user × resource × context | Fine-grained per-tenant policies; "owner of resource can edit" |
| **PBAC** (policy-based) | External policy engine (OPA, Cedar) | Policies evolve independently of code; multiple services share policy; compliance audit needs a policy registry |

**Default to RBAC.** Reach for ABAC when you have a "user can act on resources they own" requirement that RBAC can't express. Reach for PBAC when policy needs to be version-controlled and audited separately from the application.

## RBAC implementation pattern (Python / FastAPI)

```python
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

class Permission(str, Enum):
    rebooking_view    = "rebooking:view"
    rebooking_replay  = "rebooking:replay"
    dlq_view          = "dlq:view"
    dlq_purge         = "dlq:purge"
    customer_pii_read = "customer.pii:read"

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "admin": {
        Permission.rebooking_view, Permission.rebooking_replay,
        Permission.dlq_view, Permission.dlq_purge,
        Permission.customer_pii_read,
    },
    "operator": {
        Permission.rebooking_view, Permission.dlq_view,
    },
    "viewer":   {Permission.rebooking_view},
}

class User(BaseModel):
    sub: str
    roles: list[str]

def get_current_user() -> User:
    """Resolved from JWT; see auth-jwt.md."""
    ...

def require_permission(permission: Permission):
    def dep(user: User = Depends(get_current_user)) -> User:
        granted: set[Permission] = set().union(
            *(ROLE_PERMISSIONS.get(r, set()) for r in user.roles)
        )
        if permission not in granted:
            raise HTTPException(403, detail="forbidden")
        return user
    return dep

router = APIRouter(prefix="/admin")

@router.post(
    "/replay",
    dependencies=[Depends(require_permission(Permission.rebooking_replay))],
)
async def replay(...):
    ...
```

Key choices:

- **Permissions as enums, not strings.** Strings invite typos that fail open silently. Enums force the typo to be a `NameError`.
- **Roles flatten to a permission set at check time.** Don't reason about roles in business code; reason about permissions.
- **Permission strings use the `resource:action` shape.** `rebooking:replay`, not `replayRebooking`. Easy to grep, easy to audit, easy to map to UI.

## RBAC pattern (TypeScript / Hono)

```typescript
import { Hono, MiddlewareHandler } from "hono";

const Permission = {
  RebookingView:    "rebooking:view",
  RebookingReplay:  "rebooking:replay",
  DlqView:          "dlq:view",
  DlqPurge:         "dlq:purge",
} as const;
type Permission = (typeof Permission)[keyof typeof Permission];

const ROLE_PERMISSIONS: Record<string, Set<Permission>> = {
  admin:    new Set([Permission.RebookingView, Permission.RebookingReplay,
                     Permission.DlqView, Permission.DlqPurge]),
  operator: new Set([Permission.RebookingView, Permission.DlqView]),
  viewer:   new Set([Permission.RebookingView]),
};

export const requirePermission = (perm: Permission): MiddlewareHandler =>
  async (c, next) => {
    const user = c.get("user") as { roles: string[] };  // set by auth middleware
    const granted = new Set<Permission>();
    for (const r of user.roles) {
      for (const p of ROLE_PERMISSIONS[r] ?? []) granted.add(p);
    }
    if (!granted.has(perm)) return c.json({ error: "forbidden" }, 403);
    await next();
  };

app.post("/admin/replay", requirePermission(Permission.RebookingReplay), handler);
```

## Tenant-scoped authorization

For multi-tenant apps, every permission check must include the resource's tenant. A `rebooking:view` permission alone doesn't mean a user can view *every* rebooking — only the ones in their tenant.

```python
def require_tenant_permission(permission: Permission):
    def dep(
        resource: Resource = Depends(get_resource),
        user: User = Depends(get_current_user),
    ) -> User:
        if resource.tenant_id != user.tenant_id:
            raise HTTPException(404, detail="not found")   # 404, not 403 — don't leak existence
        if permission not in compute_granted(user):
            raise HTTPException(403, detail="forbidden")
        return user
    return dep
```

Notice the `404` instead of `403` on cross-tenant access — returning `403` confirms the resource exists, which is itself a leak. See `multi-tenancy.md` (PR-J, pending) for the broader pattern (row-level security, tenant propagation, per-tenant quotas).

## Tool-level authorization (agent-specific)

Agents extend the attack surface: each tool the model can call is a potential action. Authz at the endpoint is necessary but not sufficient — the model may chain into tools that the user wasn't authorized for.

Three layers:

### 1. Per-intent tool allowlists

Restrict which tools the model can even see based on the routed intent. A billing-intent request gets billing tools only; a technical-support intent gets KB-search only.

```python
ALLOWED_TOOLS_BY_INTENT: dict[str, set[str]] = {
    "billing":   {"lookup_billing", "issue_refund"},
    "technical": {"search_kb"},
    "rebooking": {"get_waitlist", "check_availability", "notify_customer",
                  "modify_reservation", "emit_outcome_event"},
}

def filter_tools(intent: str, all_tools: list[Tool]) -> list[Tool]:
    allowed = ALLOWED_TOOLS_BY_INTENT.get(intent, set())
    return [t for t in all_tools if t.name in allowed]
```

The LLM can't call a tool it doesn't see. Even if prompt injection succeeds in changing the model's intent, the tool list is fixed before the model gets the request.

### 2. Per-user tool gating

Some tools require specific permissions even if the intent allows them.

```python
TOOL_PERMISSIONS: dict[str, Permission] = {
    "issue_refund":  Permission.refund_issue,
    "purge_dlq":     Permission.dlq_purge,
}

def filter_tools_for_user(intent: str, user: User, all_tools: list[Tool]) -> list[Tool]:
    allowed_by_intent = ALLOWED_TOOLS_BY_INTENT.get(intent, set())
    granted = compute_granted(user)
    return [
        t for t in all_tools
        if t.name in allowed_by_intent
        and (t.name not in TOOL_PERMISSIONS or TOOL_PERMISSIONS[t.name] in granted)
    ]
```

### 3. Action-approval gates

High-stakes tool calls require human approval before execution.

```python
HIGH_STAKES_TOOLS = {"issue_refund", "delete_customer", "broadcast_notification"}

async def execute_tool(tool: Tool, args: dict, ctx: Context) -> Any:
    if tool.name in HIGH_STAKES_TOOLS:
        approval = await request_approval(tool, args, ctx)
        if not approval.approved:
            raise PermissionDenied(f"action requires approval; rejected by {approval.actor}")
    return await tool.invoke(args)
```

For interactive agents, this is a UI confirmation; for event-driven flows, this is a workflow step (write a `pending_approval` row, wait for an admin to flip it).

## OPA (Open Policy Agent) pattern

For complex policies — multiple services, audit-grade policy versioning, policies that evolve faster than code — externalize to OPA. The application calls `opa.evaluate(...)`; the policy is a separate Rego file under version control.

```rego
package rebooking.replay

default allow := false

allow if {
    "operator" in input.user.roles
    input.event.restaurant_id == input.user.restaurant_id
    input.event.created_at >= time.now_ns() - (7 * 24 * 60 * 60 * 1_000_000_000)
}
```

```python
import httpx

async def check_policy(package: str, input_doc: dict) -> bool:
    resp = await opa_client.post(f"/v1/data/{package}/allow", json={"input": input_doc})
    resp.raise_for_status()
    return bool(resp.json().get("result", False))

if not await check_policy("rebooking.replay",
                          {"user": user.model_dump(), "event": event.model_dump()}):
    raise HTTPException(403)
```

When to reach for OPA:

- Policies need to change without redeploying the application.
- Multiple services share the same policy (centralized auth).
- Auditors / compliance need policy-as-code in a separate repo.

For a single-service mise / rebooking deployment, the inline RBAC above is plenty.

## Tests

- **Permission positive test** — user with the role can perform the action.
- **Permission negative test** — user without the role gets `403`.
- **Cross-tenant test** — user with permission cannot reach another tenant's resource (must return `404`, not `403`).
- **Tool-filter test** — `filter_tools("billing", ...)` returns only billing tools regardless of input.
- **Approval-gate test** — high-stakes tool call without approval raises; with approval, executes.

## Pitfalls

- **AuthN only, no AuthZ** — any authenticated user can do anything. The most common mistake.
- **AuthZ check on the endpoint but not on the tool** — agent bypasses by calling the tool path directly (or via injection).
- **Permission strings as raw strings** — typo = silent bypass. Always use enums / typed unions.
- **403 on cross-tenant access** — confirms existence. Return 404.
- **Role hierarchy without cycle detection** — infinite recursion on resolve.
- **Missing tenant scope on queries** — `SELECT * FROM rebookings` instead of `WHERE tenant_id = ?`. Use row-level security where possible.
- **Approval gates that auto-expire to "approved"** — silent privilege escalation. Auto-expire to denied.
- **Logging the permission check result but not the decision input** — un-auditable. Log both.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — admin endpoints (`/admin/replay`, `/admin/dlq/*`); per-intent tool allowlists on the orchestrator.

## See also

- [auth-jwt.md](./auth-jwt.md) — the AuthN layer that produces the user identity these checks consume.
- [audit-logging.md](./audit-logging.md) — log who attempted what, including denied attempts.
- `multi-tenancy.md` (PR-J, pending) — row-level security and tenant propagation patterns.
