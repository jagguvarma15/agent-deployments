---
tags: [deployment, kubernetes, production]
when_to_load: "recipe targets kubernetes"
---

# Stack pick: Kubernetes + Helm

**Choice:** Kubernetes 1.30+ via managed control plane (EKS / GKE / AKS); Helm 3.x for application packaging
**Used for:** Container orchestration in production; templated deployment artifacts; rollout automation; horizontal autoscaling

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Docker Compose | Single-host; no rollout / HA / autoscaling — fine for dev, never for prod |
| Nomad | Simpler scheduler; smaller ecosystem; good fit for non-microservice workloads |
| ECS / Cloud Run / Fargate | Cloud-locked; faster onboarding; fine for single-cloud teams that don't need K8s ecosystem |
| Self-managed Kubernetes | Don't unless you have a platform team. Managed (EKS / GKE / AKS) is the right default |
| K8s + raw manifests | Hard to template per-env; ad-hoc; only OK for one-off cluster utilities |
| K8s + Kustomize | Overlay-based; fine for simple cases; weaker for sharing charts across services |
| K8s + Helm | De facto standard; chart ecosystem; values.yaml per env |

For mise: managed Kubernetes + Helm. Skip raw manifests after the first prototype.

## Workload shape

A typical agent deployment is **1–2 Deployments + 1 Service + 1 HPA + 1 ConfigMap + 1 ExternalSecret per microservice**:

| Resource | Purpose |
|----------|---------|
| `Deployment` | Replicas of the app pod |
| `Service` | Stable virtual IP + cluster DNS |
| `Ingress` / `Gateway` | External traffic routing + TLS |
| `HorizontalPodAutoscaler` | Scale on CPU / custom metrics |
| `ConfigMap` | Non-secret config |
| `Secret` (via ESO) | Secrets synced from cloud SM / Vault — see [secrets-management.md](./secrets-management.md) |
| `ServiceAccount` | Workload identity for IRSA / GKE Workload Identity |
| `PodDisruptionBudget` | Caps voluntary disruptions during rolling updates / node drains |
| `NetworkPolicy` | Egress + ingress firewall rules at pod level |

For event-driven workloads (the rebooking consumer):

- A **separate `Deployment` for the consumer** (no `Service` needed — it pulls work, doesn't accept connections).
- A **KEDA `ScaledObject`** for queue-depth-based autoscaling (Redis Streams pending entries, Kafka consumer lag).

## Helm chart structure

```
charts/rebooking/
├── Chart.yaml              # name, version, appVersion
├── values.yaml             # default values (committed)
├── values-dev.yaml         # dev overrides
├── values-prod.yaml        # prod overrides
├── templates/
│   ├── _helpers.tpl        # named templates (labels, selectors)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── configmap.yaml
│   ├── externalsecret.yaml
│   ├── serviceaccount.yaml
│   ├── pdb.yaml
│   ├── networkpolicy.yaml
│   ├── scaledobject.yaml   # KEDA, if event-driven
│   └── tests/
│       └── connection-test.yaml
└── README.md
```

Keep per-env overrides minimal — only what actually differs between environments. Drift between dev and prod values is a long-tail source of "works in dev, broken in prod" incidents.

## Critical Deployment fields

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rebooking
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0                  # zero-downtime; default 25% can cause user-visible blips
  template:
    metadata:
      labels: { app: rebooking }
    spec:
      terminationGracePeriodSeconds: 60   # match graceful-shutdown drain (see below)
      serviceAccountName: rebooking
      containers:
        - name: app
          image: ghcr.io/example/rebooking:v1.0.0   # never `latest` in prod
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef: { name: rebooking-config }
            - secretRef:    { name: rebooking-secrets }
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          startupProbe:
            httpGet: { path: /health/startup, port: 8000 }
            failureThreshold: 30          # 30 × 2s = 60s window to come up
            periodSeconds: 2
          livenessProbe:
            httpGet: { path: /health/live, port: 8000 }
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet: { path: /health/ready, port: 8000 }
            periodSeconds: 5
            failureThreshold: 2
          lifecycle:
            preStop:
              exec:
                command: ["sh", "-c", "sleep 15"]   # let LB notice readiness fail before SIGTERM
          securityContext:
            runAsNonRoot: true
            runAsUser: 10000
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - { name: tmp, mountPath: /tmp }
      volumes:
        - name: tmp
          emptyDir: {}
```

Tie `terminationGracePeriodSeconds` to your app's drain timeout — see [health-graceful-shutdown.md](../cross-cutting/health-graceful-shutdown.md). A grace period shorter than the drain timeout = SIGKILL mid-drain = dropped in-flight requests.

## Autoscaling

### HPA for HTTP services

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rebooking
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rebooking
  minReplicas: 3
  maxReplicas: 30
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: { type: Utilization, averageUtilization: 70 }
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # avoid flapping; cool down 5 min before scaling down
```

For LLM-heavy services, CPU is a poor signal — most time is spent awaiting the model. Scale on request count or in-flight tokens via a custom metric (Prometheus adapter).

### KEDA for event-driven workloads

Standard HPA doesn't observe Redis Stream depth or Kafka lag. KEDA does:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: rebooking-consumer
spec:
  scaleTargetRef:
    name: rebooking-consumer
  minReplicaCount: 1
  maxReplicaCount: 20
  pollingInterval: 15
  cooldownPeriod: 120
  triggers:
    - type: redis-streams
      metadata:
        address: redis:6379
        stream: reservations.cancelled
        consumerGroup: rebooker
        pendingEntriesCount: "50"          # scale up when XPENDING > 50
```

Scale consumers up when backlog grows; scale down (to `minReplicaCount`, optionally 0) when idle. For Kafka, swap the trigger to `kafka` with `consumerGroup` + `lagThreshold`.

## ConfigMap + ExternalSecret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rebooking-config
data:
  APP_ENV:        production
  LOG_LEVEL:      INFO
  EVENT_STREAM:   reservations.cancelled
  CONSUMER_GROUP: rebooker
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: rebooking-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: rebooking-secrets                # this is the K8s Secret consumed by the Deployment
  data:
    - secretKey: ANTHROPIC_API_KEY
      remoteRef: { key: prod/rebooking/anthropic-api-key }
    - secretKey: JWT_SECRET
      remoteRef: { key: prod/rebooking/jwt-signing-key }
    - secretKey: DATABASE_URL
      remoteRef: { key: prod/rebooking/database-url }
```

The Deployment consumes both via `envFrom` — clean separation of secret/non-secret, both projected as env vars.

## NetworkPolicy

Default-deny + explicit allow rules. Limits blast radius of a compromised pod:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: rebooking-egress
spec:
  podSelector:
    matchLabels: { app: rebooking }
  policyTypes: [Egress]
  egress:
    - to:
        - podSelector: { matchLabels: { app: redis } }
      ports: [{ protocol: TCP, port: 6379 }]
    - to:
        - podSelector: { matchLabels: { app: postgres } }
      ports: [{ protocol: TCP, port: 5432 }]
    - to: []                                 # Anthropic API + other external HTTPS
      ports: [{ protocol: TCP, port: 443 }]
    - to:                                    # DNS
        - namespaceSelector: { matchLabels: { name: kube-system } }
          podSelector:       { matchLabels: { k8s-app: kube-dns } }
      ports:
        - { protocol: UDP, port: 53 }
        - { protocol: TCP, port: 53 }
```

For ingress: pair with a corresponding `Ingress` NetworkPolicy allowing only the ingress controller / mesh sidecar.

## PodDisruptionBudget

Prevents the cluster autoscaler / node drain from taking down more than N pods at once:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: rebooking
spec:
  minAvailable: 2
  selector:
    matchLabels: { app: rebooking }
```

Without a PDB, a single `kubectl drain` can take all replicas down.

## Helm CI patterns

```bash
helm lint charts/rebooking

# Server-side dry-run validates against the API server (catches CRD / admission issues)
helm template charts/rebooking -f charts/rebooking/values-prod.yaml \
  | kubectl apply --dry-run=server -f -

# Atomic + wait = rollback on failure, block until pods Ready
helm upgrade --install rebooking charts/rebooking \
  -f charts/rebooking/values-prod.yaml \
  --atomic --wait --timeout 5m
```

`--atomic --wait` is the rollout-safety pair: rollback on failure, block until pods become Ready. For larger services tune `--timeout`.

## Multi-environment values

Keep environment overrides minimal:

```yaml
# values.yaml (defaults)
replicaCount: 3
image:
  repository: ghcr.io/example/rebooking
resources:
  requests: { cpu: 100m, memory: 256Mi }
  limits:   { cpu: 1000m, memory: 1Gi }

# values-prod.yaml (only the deltas)
replicaCount: 10
resources:
  requests: { cpu: 500m, memory: 1Gi }
image:
  tag: v1.0.0                        # never `latest` in prod
ingress:
  host: rebooking.example.com
```

## Pitfalls

- **`maxUnavailable: 25%` default** — downtime during rollouts. Set to `0` for HTTP services.
- **No `PodDisruptionBudget`** — node drains kill the entire deployment in one go.
- **Missing `runAsNonRoot` / `readOnlyRootFilesystem`** — container compromise becomes node compromise.
- **Image tag `latest`** — can't reliably roll back; cluster pulls a different image than you tested.
- **No resource requests** — pods are unschedulable on busy nodes. No resource limits — noisy neighbours.
- **`readOnlyRootFilesystem: true` but the app writes to `/tmp`** — mount an `emptyDir` at `/tmp`.
- **Liveness probe == readiness probe** — slow downstream causes cascading pod kills instead of just removal from the LB.
- **`livenessProbe` checking external dependencies** — a Redis blip restarts every pod simultaneously.
- **Forgetting `--atomic --wait`** — failed rollouts leave a half-deployed mess; rollback by hand.
- **NetworkPolicy with no DNS allow** — pods can't resolve anything; debug for an hour before remembering.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — production deployment target (a separate Deployment for the consumer, KEDA-scaled on Redis Streams pending count).
- All recipes that need horizontal scaling at deployment time.

## Production considerations

- **Cluster-level add-ons** — cluster-autoscaler, image scanner (Trivy / Grype), policy engine (OPA Gatekeeper / Kyverno), cert-manager.
- **Service mesh** (Istio / Linkerd) — mTLS east-west + L7 observability, if running enough services to justify the operational overhead.
- **Backup** — Velero for cluster-level snapshots; per-app data backups via DB-specific tools (the cluster snapshot isn't a backup of your data).
- **DR posture** — multi-AZ minimum; multi-region for tier-1 services; document the cluster bootstrap procedure and test it.
- **Cost control** — node taints + per-team namespace quotas; sleep schedules on non-prod environments.

## See also

- `secrets-management.md` — the External Secrets Operator pattern referenced in the Deployment above.
- `cross-cutting/health-graceful-shutdown.md` — probe distinctions and SIGTERM drain that tie to `terminationGracePeriodSeconds`.
- `terraform.md` — provisioning the cluster itself, plus the VPC / IAM / managed services around it.
- `cross-cutting/observability.md` — Prometheus / OTel collectors run inside the same cluster.
