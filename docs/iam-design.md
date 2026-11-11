# IAM Design (Least Privilege)

> **Status:** design plus a *local simulation*. Nothing here configures AWS IAM, Azure RBAC or GCP IAM. Docker Desktop has no native RBAC, so the operator/admin separation is enforced only where a tool supports it (Vault policies, Grafana roles, app token scopes) and otherwise by procedure.

## Identities and roles

| Identity | Type | Can | Cannot | Enforced by |
|---|---|---|---|---|
| **Application service identity** | Container user `10001`, Vault AppRole `support-app` | Read exactly one Vault path (`secret/data/support-app`); read its own mounted secrets; call Google over HTTPS | Write/list Vault, read other paths, write its filesystem (read-only root), gain privileges (`cap_drop: ALL`, `no-new-privileges`) | `Dockerfile`, `docker-compose.yml`, `deploy/vault/policy-app.hcl` |
| **Customer API client** | Bearer token(s) in `customer_api_tokens` | `POST /query` | Read `/metrics`, any admin function | `security.py`, `api.py` (scope `query`) |
| **Monitoring (Prometheus)** | Bearer token `metrics_token` | `GET /metrics` only | `POST /query` (customer token is a different secret) | scope `metrics`; Prometheus on internal network |
| **Grafana viewer** | Grafana user, role *Viewer* | View dashboards | Edit dashboards, see secrets | Grafana RBAC (created manually) |
| **Application operator** | Human; Vault policy `support-operator`; Grafana *Editor* | Restart containers, read logs/dashboards, confirm that a secret was rotated (metadata) | Read secret **values** | `policy-operator.hcl` (explicit deny on data); host access by procedure |
| **Administrator** | Human; Vault policy `support-admin`; Grafana *Admin* | Rotate/revoke secrets and AppRole credentials, change compose config, upgrade | - | `policy-admin.hcl`; host admin rights |

Policy files: `deploy/vault/policy-app.hcl`, `policy-operator.hcl`, `policy-admin.hcl` (written to Vault by `bootstrap.sh`; creating *human* Vault tokens/userpass for operator/admin is a manual customer step).

## Least-privilege decisions

- Separate credentials per purpose: customer token != metrics token != Grafana password != Gemini key. Compromise of one does not grant the others.
- Multiple customer tokens may be active simultaneously (comma-separated) so each client can have its own token and be revoked individually.
- Each container receives only the secrets it needs (Prometheus gets only `metrics_token`; Grafana only its password).
- AppRole tokens are short-lived (TTL 15 min, max 1 h); `secret_id` can be revoked without touching the Gemini key.
- Network boundaries: monitoring and Vault networks are `internal`; only the app can reach the internet.
- Gemini key should be restricted in Google Cloud/AI Studio to the Generative Language API (and IP range if static) - **manual customer step**.

## Local simulation vs. real cloud

| Concern | Local (this repo) | AWS | Azure | GCP |
|---|---|---|---|---|
| Workload identity | Container UID + Vault AppRole | ECS task role / EKS IRSA | Managed Identity | Service account + Workload Identity |
| Secret store | Vault KV v2 (dev) / Docker file secrets | Secrets Manager (+ KMS) | Key Vault | Secret Manager |
| Secret access policy | `policy-app.hcl` (read one path) | IAM policy: `secretsmanager:GetSecretValue` on one secret ARN | RBAC *Key Vault Secrets User* on one secret | `roles/secretmanager.secretAccessor` on one secret |
| Network boundary | Compose internal networks | VPC private subnets, security groups, VPC endpoints | VNet + NSGs, Private Endpoints | VPC, firewall rules, Private Service Connect |
| Human roles | Vault policies + Grafana roles | IAM Identity Center permission sets | Entra ID groups + RBAC | Cloud IAM groups |
| Metrics access | Metrics token + internal net | CloudWatch / AMP + IAM | Azure Monitor + RBAC | Cloud Monitoring + IAM |
| Audit | Container logs; Vault audit device (not enabled) | CloudTrail | Activity Log | Cloud Audit Logs |

Migrating to a cloud: replace `secrets_provider.py`'s Vault branch with the provider's SDK (the interface is one function, `get_secret(name)`), run the same image under the platform's workload identity, and keep the app/metrics/customer scopes unchanged.
