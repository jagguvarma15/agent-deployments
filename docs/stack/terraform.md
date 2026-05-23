# Stack pick: Terraform

**Choice:** OpenTofu (the Linux Foundation fork, MPL-licensed) OR HashiCorp Terraform 1.5+
**Used for:** Provisioning cloud infrastructure (VPCs, Kubernetes clusters, managed databases, IAM, DNS) reproducibly with a reviewable change record

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Click-ops in the cloud console | No reproducibility, no audit trail, no review path; drift accumulates |
| Cloud-native IaC (CloudFormation, ARM, Deployment Manager) | Vendor-locked; verbose; weaker module ecosystem |
| Pulumi | Code-first IaC (TS / Py / Go); good fit if the team is allergic to HCL; smaller ecosystem |
| Crossplane | Kubernetes-native IaC; powerful but heavy lift; good when K8s is already the control plane |
| Terraform / OpenTofu | De facto standard; HCL is readable; massive provider ecosystem |

For mise: OpenTofu (or Terraform where licensing constraints permit) with a clear module structure and a remote state backend with locking.

## Repository structure

```
infrastructure/
├── modules/
│   ├── vpc/
│   ├── kubernetes-cluster/
│   ├── postgres/
│   ├── redis/
│   ├── secrets/
│   └── monitoring/
├── envs/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   └── prod/
└── shared/
    └── providers.tf
```

Each environment is its own Terraform state. **Never share state across environments** — it's the single change that prevents "applied to prod by accident."

## State backend

Local state is fine for prototyping. Production **must** use a remote backend with locking.

### AWS S3 + DynamoDB

```hcl
terraform {
  required_version = ">= 1.5.0"
  backend "s3" {
    bucket         = "mise-tfstate-prod"
    key            = "rebooking/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "mise-tfstate-locks"
    encrypt        = true
  }
}
```

DynamoDB provides state-level locking — only one `terraform apply` per state can be in flight. S3 versioning on the bucket gives you a state-file history.

### Alternatives

- **Terraform Cloud / HCP Terraform** — managed backend, plan output review, RBAC. Quick to adopt; long-term cost depends on team size.
- **GCS** — for GCP-native deployments.
- **Azure Storage** — for Azure-native deployments.

For OpenTofu, all of the above work — the backend protocol is unchanged.

## Module structure example

```hcl
# modules/postgres/main.tf

variable "name"              { type = string }
variable "vpc_id"            { type = string }
variable "subnet_ids"        { type = list(string) }
variable "instance_class"    { type = string default = "db.t4g.medium" }
variable "engine_version"    { type = string default = "16.3" }
variable "allocated_storage" { type = number default = 50 }
variable "tags"              { type = map(string) default = {} }

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-subnet-group"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name   = "${var.name}-sg"
  vpc_id = var.vpc_id
  tags   = var.tags
}

resource "aws_db_instance" "this" {
  identifier              = var.name
  engine                  = "postgres"
  engine_version          = var.engine_version
  instance_class          = var.instance_class
  allocated_storage       = var.allocated_storage
  storage_encrypted       = true
  backup_retention_period = 30
  multi_az                = true
  deletion_protection     = true
  apply_immediately       = false
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = [aws_security_group.this.id]
  tags                    = var.tags

  lifecycle {
    prevent_destroy = true                  # tombstone: refuse to destroy without removing this line
  }
}

output "endpoint"          { value = aws_db_instance.this.endpoint }
output "security_group_id" { value = aws_security_group.this.id }
```

Env-level composition:

```hcl
# envs/prod/main.tf

module "vpc" {
  source = "../../modules/vpc"
  name   = "rebooking-prod"
  cidr   = "10.0.0.0/16"
  tags   = local.tags
}

module "postgres" {
  source            = "../../modules/postgres"
  name              = "rebooking-prod"
  instance_class    = "db.r6g.large"
  allocated_storage = 200
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnet_ids
  tags              = local.tags
}

locals {
  tags = {
    Environment = "prod"
    Service     = "rebooking"
    Owner       = "platform-team"
  }
}
```

## Plan / apply discipline

```bash
tofu fmt -recursive
tofu validate
tofu plan -out=plan.tfplan
# Review plan output carefully — every ~, every -
tofu apply plan.tfplan
```

Always:

- **`plan` before `apply`.** Always.
- **Save the plan to a file**; apply the same plan, not a re-planned one. Drift between plan-time and apply-time is one of the bugs you're paying Terraform to prevent.
- **Review every resource change** — especially `~` (modify) and `-` (destroy). `-/+` (replace) means downtime and data loss for stateful resources.
- **Never `apply -auto-approve` in prod.** CI can run plan automatically; apply needs a human.

## CI/CD pattern

```yaml
# .github/workflows/terraform.yml
name: terraform
on:
  pull_request:
    paths: ["infrastructure/**"]

jobs:
  plan:
    strategy:
      matrix:
        env: [dev, staging, prod]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: opentofu/setup-opentofu@v1

      - name: fmt check
        run: tofu fmt -check -recursive infrastructure/

      - name: init
        run: tofu init -backend-config=backend.tfvars
        working-directory: infrastructure/envs/${{ matrix.env }}

      - name: plan
        run: tofu plan -out=plan.tfplan -input=false
        working-directory: infrastructure/envs/${{ matrix.env }}

      - uses: actions/upload-artifact@v4
        with:
          name: plan-${{ matrix.env }}
          path: infrastructure/envs/${{ matrix.env }}/plan.tfplan

  apply:
    needs: plan
    if: github.ref == 'refs/heads/main'
    environment: prod          # GitHub environment with required reviewers
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: opentofu/setup-opentofu@v1
      - uses: actions/download-artifact@v4
        with: { name: plan-prod }
      - run: tofu apply -input=false plan.tfplan
        working-directory: infrastructure/envs/prod
```

The GitHub `environment` with required reviewers gates apply on human approval; the plan artifact ensures the applied plan is exactly the reviewed one.

## Drift detection

Run `tofu plan` on a schedule (e.g. nightly) and alert on a non-empty diff. Drift means someone changed infrastructure outside Terraform — investigate before applying.

```yaml
on:
  schedule:
    - cron: "0 7 * * *"
jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - run: |
          tofu plan -detailed-exitcode
          # exit 0 = no changes, 1 = error, 2 = changes detected
```

## State management hazards

- **Don't `rm` the state file** by hand. Use `tofu state rm <resource>` to remove a resource from state without destroying it.
- **Don't share state across envs.** Separate state per env prevents prod from being touched by a dev plan.
- **The state file is sensitive** — it can contain credentials, ARNs, and resource attributes in plaintext. Backend encryption is mandatory; access to the backend bucket should be tightly scoped.
- **Locking is mandatory in team settings** — concurrent applies corrupt state.
- **`terraform import`** is for adopting existing resources into state; pair every import with a matching resource block.
- **Backups** — enable S3 versioning on the state bucket; document and test the restore procedure.

## Providers worth knowing

| Provider | Typical use |
|----------|-------------|
| `hashicorp/aws` / `hashicorp/google` / `hashicorp/azurerm` | Core cloud resources |
| `hashicorp/kubernetes` | K8s manifests via Terraform — use sparingly; Helm is better for app deploys |
| `hashicorp/helm` | Install Helm charts via Terraform (good for cluster add-ons like cert-manager, ESO) |
| `cloudflare/cloudflare` | DNS, CDN, WAF |
| `hashicorp/vault` | Vault config |
| `datadog/datadog`, `grafana/grafana` | Monitoring resources |

## Cost guardrails

- Tag every resource with `Environment`, `Service`, `Owner` for cost allocation.
- Use `aws_budgets_budget` (or equivalent) to alert on spend thresholds.
- For non-prod: schedule shutdowns of idle resources (instance schedulers, scaled-to-zero KEDA).
- Detect orphan resources monthly — anything tagged with a `Service` that doesn't exist anymore.

## Pitfalls

- **Shared state across envs** — the prod environment accidentally destroyed by a dev plan.
- **`auto-approve` in CI** — no human review on changes; the worst class of automation.
- **No drift detection** — manual changes silently diverge from declared state.
- **Missing `prevent_destroy` lifecycle blocks on critical resources** — a fat-finger `tofu destroy` takes the database down.
- **Hardcoded secrets in `.tfvars`** — checked into git, leaked to anyone with read access.
- **Modules so abstract they can't be understood** — resist DRYing prematurely; three similar modules with small differences is often clearer than one mega-module with twelve toggles.
- **Provider version not pinned** — a provider upgrade in CI causes surprising plans.
- **State file in git** — it's a secret-leak source; backends, not git.

## Where used in repo

- This doc describes the recommended structure for the umbrella `mise/infrastructure/` directory. The scaffold-generated app code itself is out of scope for Terraform; the infra it runs on isn't.

## Production considerations

- **State backup** — enable S3 versioning on the state bucket; lifecycle rule to retain N versions.
- **Disaster recovery** — state restore procedure documented and tested; tested means actually ran it against a non-prod state.
- **Access control** — separate IAM roles for `plan` (read-only) and `apply` (write). Most engineers should never have `apply` permission on prod.
- **Policy enforcement** — OPA / Sentinel policies prevent dangerous changes at plan time (public S3 buckets, security groups open to `0.0.0.0/0`, unencrypted volumes).
- **Multi-region** — separate state per region; module reuse via source paths; document cross-region dependencies (e.g., route53 + cert).
- **Cost** — Terraform itself is free; OpenTofu always free; Terraform Cloud / HCP has per-user pricing.

## See also

- `kubernetes-helm.md` — the cluster Terraform provisions is the substrate Helm deploys into.
- `secrets-management.md` — Terraform should not store secrets in `.tfvars`; reference them from a secret manager.
- `cross-cutting/observability.md` — observability backends (Grafana, Datadog) are themselves Terraform-managed in production.
