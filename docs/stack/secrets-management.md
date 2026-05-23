# Stack pick: Secrets management

**Choice (dev):** `.env` files loaded via `python-dotenv` or Node's `--env-file`
**Choice (prod):** Cloud secret manager (AWS Secrets Manager / GCP Secret Manager / Azure Key Vault) when single-cloud; HashiCorp Vault when multi-cloud or on-prem
**Used for:** API keys (Anthropic, third-party platforms), JWT signing keys, DB passwords, mTLS certs, webhook signing secrets

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Plain env vars in deploy manifests | OK for dev; in prod the manifests get checked into git and viewed by too many people |
| `.env` files committed to git | Never. Use `.gitignore` + `.env.example` |
| Encrypted env files (SOPS, git-crypt) | Decent middle ground for small teams; harder to rotate, harder to audit access |
| Cloud secret manager (AWS / GCP / Azure) | Best when you're already single-cloud — IAM-integrated, audit-logged, native rotation |
| HashiCorp Vault | Cloud-agnostic; best for multi-cloud or on-prem; higher operational overhead (HA cluster, unseal, backup) |
| Doppler / 1Password Secrets | SaaS; quick onboarding; good for small-to-medium teams that don't want infra |
| Kubernetes `Secret` | NOT encrypted at rest by default; use External Secrets Operator (ESO) to sync from Vault / cloud SM |

For mise: cloud secret manager once a target cloud is chosen; Doppler while remaining provider-neutral.

## Local development setup

`.env` at the repo root, gitignored. `.env.example` committed with the required keys and dummy values.

```bash
# .env.example  (committed)
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=change-me
DATABASE_URL=postgresql://app:app@localhost:5432/app
REDIS_URL=redis://localhost:6379
RESY_API_KEY=
OPENTABLE_API_KEY=
```

```gitignore
# .gitignore
.env
.env.*
!.env.example
```

Loaded at boot — language-specific:

### Python (`python-dotenv`)

```python
from dotenv import load_dotenv
load_dotenv()  # before importing Settings
```

### Node 20.6+ (built-in)

```bash
node --env-file=.env src/index.ts
```

### Pydantic-settings boot-time validation

The single highest-ROI piece of secrets hygiene: refuse to start with default or empty secrets in production.

```python
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    anthropic_api_key: str
    jwt_secret: str
    resy_api_key: str | None = None  # optional in dev

    @model_validator(mode="after")
    def reject_defaults_in_prod(self) -> "Settings":
        if self.app_env == "production":
            if self.jwt_secret in {"", "change-me", "dev-secret"}:
                raise ValueError("JWT_SECRET cannot be a default value in production")
            if not self.anthropic_api_key.startswith("sk-ant-"):
                raise ValueError("ANTHROPIC_API_KEY missing or malformed")
        return self
```

### Zod boot-time validation (TS)

```typescript
import { z } from "zod";

const Settings = z.object({
  APP_ENV: z.enum(["development", "staging", "production"]).default("development"),
  ANTHROPIC_API_KEY: z.string().startsWith("sk-ant-"),
  JWT_SECRET: z.string().min(32),
}).refine(
  (s) => s.APP_ENV !== "production" || !["", "change-me"].includes(s.JWT_SECRET),
  { message: "JWT_SECRET cannot be a default value in production" },
);

export const settings = Settings.parse(process.env);
```

## Production patterns

### Pattern 1 — Cloud secret manager + External Secrets Operator (Kubernetes)

ESO reads from the cloud secret manager and projects values into a Kubernetes `Secret`. The application reads `env:` or mounted files — it never knows about the upstream manager.

```yaml
# external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: rebooking-secrets
  namespace: rebooking
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: rebooking-secrets
  data:
    - secretKey: ANTHROPIC_API_KEY
      remoteRef:
        key: prod/rebooking/anthropic-api-key
    - secretKey: RESY_API_KEY
      remoteRef:
        key: prod/rebooking/resy-api-key
    - secretKey: JWT_SECRET
      remoteRef:
        key: prod/rebooking/jwt-signing-key
```

Pros: app code identical across environments. Cons: requires Kubernetes + ESO + a cluster-wide secret store.

### Pattern 2 — Direct SDK access (VM, serverless, single binary)

```python
import boto3
from functools import cache

@cache
def get_secret(name: str) -> str:
    client = boto3.client("secretsmanager", region_name="us-east-1")
    return client.get_secret_value(SecretId=name)["SecretString"]

ANTHROPIC_API_KEY = get_secret("prod/rebooking/anthropic-api-key")
```

`functools.cache` keeps the lookup in-process — the manager is hit once per process, not per request. For long-running services, pair with a background refresh loop so rotated secrets get picked up without a restart.

### Pattern 3 — HashiCorp Vault (AppRole / Kubernetes auth)

```python
import hvac

client = hvac.Client(url="https://vault.internal:8200")
client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)

resp = client.secrets.kv.v2.read_secret_version(path="prod/rebooking/anthropic-api-key")
ANTHROPIC_API_KEY = resp["data"]["data"]["value"]
```

For Kubernetes workloads, prefer Kubernetes auth (`client.auth.kubernetes.login(role=...)`) — the service account token authenticates against Vault, no long-lived AppRole credentials to manage.

## Rotation

Every secret has a rotation cadence; document it once, automate where possible.

| Secret type | Recommended cadence | Mechanism |
|-------------|---------------------|-----------|
| Database password | 90 days | Vault dynamic credentials, OR AWS/GCP managed rotation |
| API key (third-party) | 180 days | Manual rotation; coordinate with vendor; pre-warm new key for a day |
| JWT signing key | 90 days | Key rolling (overlap window) |
| Service-to-service mTLS cert | 30 days | cert-manager (Kubernetes) or scheduled rotation Lambda |
| Webhook signing secret | 180 days | Vendor portal + double-signing window |

### Key rolling (JWT example)

The hardest rotation case — tokens already issued with the old key must keep verifying until they expire.

1. Generate the new key; load it into the signer service as `JWT_SIGNING_KEY_NEW`.
2. Configure verifiers to accept either `JWT_SIGNING_KEY_OLD` or `JWT_SIGNING_KEY_NEW` (JWKS endpoint with both `kid`s).
3. Cut the signer over to `JWT_SIGNING_KEY_NEW`. New tokens get the new `kid`; old tokens still verify against the old key.
4. After `max_token_ttl + buffer`, retire the old key from the JWKS endpoint and delete it.

## Secret hygiene rules

1. **Never log secrets.** Configure the logger to redact known secret patterns. Don't trust `repr()` on a Settings object — override or use `SecretStr`.
2. **Never commit secrets.** Pre-commit hooks: `gitleaks`, `git-secrets`, `detect-secrets`. CI: same scanners. If a secret is committed, rotate immediately — `git rebase` doesn't help once it's pushed.
3. **Boot-time validation.** Reject defaults / empty values in production (see snippet above).
4. **Least privilege on secret access.** IAM should grant `GetSecretValue` only for the specific secret ARNs a given service needs — never `*`.
5. **Audit secret access.** Cloud secret managers log every read; ship those logs to the same place as the application audit log. Review for anomalies (read from an unexpected role, off-hours bulk fetch).
6. **No secrets in URLs.** They end up in proxy logs, browser history, error trackers. Use headers or auth-flow tokens.
7. **No secrets in container images.** Build args leak into image history. Mount secrets at runtime.
8. **No secrets via debug endpoints.** Even in dev. Habits leak.
9. **Use envelope encryption for stored PII.** KMS holds the key-encryption key (KEK); the application generates a data-encryption key (DEK) per record / per dataset; the DEK is encrypted with the KEK and stored alongside the ciphertext.

### SecretStr — keep secrets out of error reporters

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: SecretStr

# repr(settings) -> Settings(jwt_secret=SecretStr('**********'))
# settings.jwt_secret.get_secret_value() -> the actual string
```

A stray `logger.error(settings)` won't leak the value into Sentry / Datadog.

## Where used in repo

- All recipes — every recipe needs `ANTHROPIC_API_KEY` at minimum.
- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `RESY_API_KEY` / `OPENTABLE_API_KEY` / `TOAST_API_KEY` for the reservation-platform adapters; `JWT_SECRET` for the admin HTTP layer; `DATABASE_URL` and `REDIS_URL`.

## Production considerations

- **High availability.** A secret-manager outage means the app can't restart. Cache fetched secrets in process memory; have a runbook for manual override (last-known-good secrets in a sealed envelope).
- **Cold-start latency.** SDK calls to secret managers add 50–200 ms each. Pre-fetch at boot inside the startup probe window, not on the request path.
- **Cost.** AWS Secrets Manager is $0.40 / secret / month + $0.05 per 10k API calls. Group related secrets (e.g., one JSON-shaped secret per service) rather than many singletons; cache aggressively. Vault is free but you pay for the cluster.
- **Disaster recovery.** Cloud secret managers handle backup; Vault you back up yourself (Raft snapshots). Document the restore procedure; test it on a cadence.
- **Compliance.** Cloud managers come with FedRAMP / SOC2 / ISO 27001 attestations; Vault you certify your own deployment.

## See also

- `security-hardening.md` — broader production discipline (TLS, headers, container posture).
- `audit-logging.md` — secret-access events are audit events.
- `auth-jwt.md` — JWT signing key is the canonical "must rotate" secret.
- [Pydantic settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — boot-time validation patterns.
