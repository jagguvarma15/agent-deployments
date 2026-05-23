# Cross-cutting: PII handling and GDPR alignment

**Concern:** Treat PII as a distinct data class with its own storage, access, and lifecycle rules. GDPR is the strict baseline; CCPA and state laws layer on top.
**Library:** `pgcrypto` / KMS envelope encryption + tokenization service (when shared) + regex/NER DLP screens
**Lives in:** Inline below — every recipe that touches customer data adopts at least the minimization + deletion patterns.

## What it provides

- A working definition of PII (direct, quasi, sensitive) so you know what's in scope.
- Storage patterns (separate PII table, column encryption, tokenization) with tradeoffs.
- A concrete right-to-erasure (GDPR Article 17) implementation.
- LLM-specific concerns: redaction before prompting, regurgitation in completions.
- Pitfalls that bite even careful teams (cache TTLs surviving deletion, PII in `trace_id`, backups never purged).

## What counts as PII

- **Direct identifiers** — name, email, phone, government ID, customer-assigned id when it's externally meaningful.
- **Quasi-identifiers** — birthday, ZIP, IP address, device fingerprint, browser UA. Individually weak; in combination they re-identify.
- **Sensitive categories** (GDPR Article 9) — health, religion, sexual orientation, biometrics, union membership. Stricter rules, higher fines.

For mise / restaurant-rebooking: customer name, contact info, party-size patterns, dining preferences, and reservation history are all PII. The restaurant's name + reservation times in aggregate are not — but tie them to a customer and they are.

## Data minimization

- **Don't store PII you don't need.** "We might want it later" is not a justification under GDPR.
- **Don't log PII.** Log identifiers (`customer_id`), resolve to PII only at the display layer.
- **Don't pass PII to the LLM unless necessary** for the task. When you do, document it and prefer redacted forms.
- **Don't include PII in error messages.** Stack traces sent to error tracking should not contain payloads.
- **Don't include PII in observability** — `trace_id`, span attributes, metric labels are all backed by stores you don't fully control.

If you wouldn't put it on a billboard, treat it as PII and apply the rules below.

## Storage patterns

### Separate PII table

PII lives in its own table referenced from non-PII tables. Tightest access control and easiest deletion.

```sql
CREATE TABLE customers (
    id          UUID PRIMARY KEY,
    pii_id      UUID REFERENCES customer_pii(id) ON DELETE SET NULL,
    tenant_id   UUID NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    -- non-PII attributes only
);

CREATE TABLE customer_pii (
    id              UUID PRIMARY KEY,
    name_encrypted  BYTEA NOT NULL,    -- envelope encryption, KMS-managed DEK
    email_encrypted BYTEA NOT NULL,
    phone_encrypted BYTEA,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Restrict access at the role level
REVOKE ALL    ON customer_pii FROM app_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON customer_pii TO app_pii_role;
```

Pros: tight access boundary; deletion is a single table; auditing reads is easy.
Cons: more joins; harder for analytics.

### Column-level encryption

PII encrypted in place using `pgcrypto` or application-layer envelope encryption. Simpler schema; the access boundary is looser (column GRANTs help but aren't as clean).

```sql
ALTER TABLE customers
    ADD COLUMN name_encrypted  BYTEA,
    ADD COLUMN email_encrypted BYTEA;
```

```python
from cryptography.fernet import Fernet

def encrypt_pii(value: str) -> bytes:
    return Fernet(get_dek_from_kms()).encrypt(value.encode())
```

### Tokenization

Replace PII with stable, non-reversible-without-vault tokens. The PII lives in a dedicated tokenization service. Analytics teams get tokens; only the customer-facing service can detokenize.

Best when PII flows across services / teams and you want a single point of access control. Overkill for single-service deployments.

## Access control

- **Per-column or per-table RBAC.** Who can read `email_encrypted`? Not "the app" — specific roles.
- **Audit every PII read.** Use [audit-logging.md](./audit-logging.md). Include `justification` for high-stakes reads (support agent looking up a customer).
- **Justify breakglass.** Admin override that bypasses RBAC must require a written justification and produce an audit row that immediately alerts security.

## Retention and deletion (Article 17 — right to erasure)

Erasure must be complete: the row in the OLTP store is the easy part. The full list:

```python
async def delete_customer(customer_id: str) -> None:
    # 1. Hard-delete PII rows
    await db.execute("DELETE FROM customer_pii WHERE id = $1",
                     await pii_id_for(customer_id))

    # 2. Anonymize references — keep the historical record (restaurants need it),
    #    but break the link back to the person
    await db.execute("UPDATE reservations SET customer_id = NULL WHERE customer_id = $1",
                     customer_id)

    # 3. Audit the deletion (the audit row itself is PII-free)
    await audit("customer.deleted", "customer", customer_id)

    # 4. Purge caches keyed on the customer or containing PII
    await cache.delete_pattern(f"customer:{customer_id}:*")
    await cache.delete_pattern(f"pii:{customer_id}:*")

    # 5. Schedule deletion from downstream systems
    await schedule_deletion(customer_id, targets=[
        "search_index",      # async; emit an event
        "analytics_warehouse",
        "data_lake",
        "backups",           # tombstone the customer in the backup catalog;
                             # backups themselves expire on their own schedule
        "third_party",       # e.g. email provider, SMS provider — call their delete APIs
    ])
```

**Document your deletion fan-out.** Every store that ever saw the data needs a deletion path or a documented expiration window.

### Soft delete vs hard delete

- **Soft delete (`deleted_at` column)** — easy to undo; bad for GDPR. The data is still present, the row is still indexed, backups still contain it.
- **Hard delete + anonymize** — correct shape for PII. Soft delete is fine for *non-PII* records.

If you need a "deletion grace period" for accidental clicks, implement it in the deletion job: write a `pending_deletion` row, hard-delete after N days. Not by leaving the data in the live table marked deleted.

## Right of access (Article 15)

A customer can request all data you hold on them. Implement an export endpoint that:

1. Authenticates the requester (high-confidence; this is exactly the data an attacker would want).
2. Compiles all PII + activity history into a single structured payload (JSON / CSV).
3. Audits the export request and the resulting download.
4. Optionally encrypts the export with the requester's provided key.

## Cross-border transfers

If data flows US ↔ EU:

- Pick a legal basis: adequacy decision, Standard Contractual Clauses (SCCs), Binding Corporate Rules (BCRs).
- Document it once, in a place that survives team turnover.
- Where feasible, avoid transfers entirely — regional deployments + region-pinned data stores beat any paperwork solution.

## LLM-specific concerns

### Don't send raw PII to the LLM unless required

Redact before prompting. The LLM provider's logs / training pipeline are out of your control even with the right contracts.

```python
import re

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}\b")
SSN_RE   = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

def redact_for_llm(text: str) -> str:
    text = EMAIL_RE.sub("<EMAIL>", text)
    text = PHONE_RE.sub("<PHONE>", text)
    text = SSN_RE.sub("<SSN>",   text)
    return text
```

For higher precision use an NER model (`presidio-analyzer`) or a structured-extraction pass before generation.

### LLM responses can regurgitate PII

The model may emit PII present in its context or, more rarely, in its training data. Screen completions before they reach the user or before they're stored:

```python
class CompletionGuard(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def no_pii(cls, v: str) -> str:
        if EMAIL_RE.search(v) or PHONE_RE.search(v) or SSN_RE.search(v):
            raise ValueError("completion contained PII; check redaction upstream")
        return v
```

### Provider terms

Document the provider's data-handling policy (Anthropic, OpenAI, etc.) in your data-flow diagram. Specifically: what's retained, for how long, whether inputs feed training. Re-verify on contract renewal.

## DLP-style checks on outbound

Outbound emails, SMS, webhook payloads, and third-party API calls should be scanned for accidental PII inclusion before send. Simple regex DLP catches the obvious mistakes; combine with NER for higher precision:

```python
async def send_email(to: str, subject: str, body: str) -> None:
    if dlp_screen_blocks(subject) or dlp_screen_blocks(body):
        raise OutboundBlocked("DLP screen flagged PII in outbound email")
    await provider.send(to=to, subject=subject, body=body)
```

Default to block-on-flag in production; default to log-only in development to tune the regexes.

## Tests

- **Roundtrip test** — encrypt → decrypt yields the original; encrypt is non-deterministic (different ciphertext on each call).
- **Deletion fan-out test** — call `delete_customer`; assert no PII rows remain in PII table; reservations have null `customer_id`; cache lookups miss; audit row present.
- **No PII in trace test** — span attributes / metric labels never include redactable patterns.
- **Redaction test** — `redact_for_llm` removes the canonical PII patterns; assert no false negatives on common formats.
- **DLP screen test** — outbound payloads containing PII are blocked in prod mode; logged in dev mode.

## Pitfalls

- **Logging the request body** — PII in app logs, surviving for weeks.
- **Caches with PII keys / values** — orphan PII surviving deletion. Always include cache purge in the deletion fan-out.
- **PII in `trace_id` / span names** — observability backend retains it for the trace retention window.
- **Soft-delete instead of hard-delete** — GDPR violation; the data is still there.
- **Backups never purged** — PII immortal in backups. Set a maximum backup retention and document it.
- **Third-party deletion ignored** — email / SMS provider still has the data. Use their delete APIs and audit the call.
- **Anonymization that isn't** — `customer_id = NULL` is anonymous; `customer_id = "deleted_user_42"` linked to past reservations isn't.
- **Sending PII to the LLM "just for one prompt"** — provider retention is out of your control.
- **Export endpoint without strong authn** — perfect target for an attacker.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — customer data flow through the rebooking orchestrator; notification redaction; deletion fan-out.

## See also

- [audit-logging.md](./audit-logging.md) — every PII access is audited.
- [authorization-rbac.md](./authorization-rbac.md) — PII access requires a specific permission.
- [security-hardening.md](./security-hardening.md) — encryption-at-rest and -in-transit choices.
