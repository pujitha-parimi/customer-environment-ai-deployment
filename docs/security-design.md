# Security Design

## Authentication
- **Customer API:** `Authorization: Bearer <token>`. Tokens are random 256-bit values (`scripts/init-secrets.*`), compared with `hmac.compare_digest` against *every* configured token (comma-separated list enables per-client tokens and rotation overlap). **Fails closed:** no tokens configured => every request is 401.
- **Metrics:** `/metrics` requires a *different* token (`METRICS_TOKEN`); a customer token cannot read metrics.
- **Unauthenticated endpoints:** `/health` (liveness) and `/ready` (booleans only: key configured, tokens configured, secret backend status; no values). `/docs` is public unless `ENABLE_DOCS=false` - **disable it in production**.
- Rejected credentials increment `auth_failures_total{scope}` and trigger the `AuthFailureSpike` alert.

## Authorization
Two scopes only: `query` (customer) and `metrics` (monitoring). The API exposes no administrative endpoints; administration is done on the host/Vault (see iam-design.md).

## Secrets management
| Mode | Mechanism | Strength | Limitation |
|---|---|---|---|
| **Default** | Docker file-based secrets: `./secrets/*.txt` mounted read-only at `/run/secrets/*` (tmpfs), referenced via `*_FILE` env paths | Never in image layers, env vars, compose file, or Git; re-read on every use => rotation without restart | Plain files on the host disk; protected only by host/folder permissions and disk encryption. **This is not enterprise secrets management.** |
| **Vault overlay** | HashiCorp Vault KV v2, AppRole login (15-min tokens), policy allows read of one path | Central store, per-identity policy, revocable `secret_id`, audit-capable | Compose runs Vault in **dev mode**: in-memory, auto-unsealed, no TLS, known root token - *local simulation only*; data is lost on restart (re-run `bootstrap.sh`). AppRole ids still sit in `./secrets` files. |
| Local development | `.env` (gitignored) | Convenience | Plaintext on disk. Dev only. |

Production Vault would need: raft/consul storage, TLS, real unseal (auto-unseal via cloud KMS/HSM), audit devices, response-wrapped `secret_id` delivery or Vault Agent. These are **not implemented or tested here**.

Rules enforced in code/config: no secrets in `Dockerfile`/compose/image (`scripts/validate_configs.py` checks), `.dockerignore` excludes `.env` and `secrets/`, `.gitignore` excludes `.env*` (except `.env.example`) and `secrets/`, Gemini key sent only in an HTTP header by the SDK.

## Network security
- Only `127.0.0.1:8000` (API) and `127.0.0.1:3000` (Grafana) are published; Prometheus and Vault are not published at all.
- `monitor_net` and `secrets_net` are `internal: true` (no internet, no host access).
- **No TLS inside this stack.** Terminate TLS at a reverse proxy/load balancer before exposing beyond localhost.
- Outbound: app -> `generativelanguage.googleapis.com:443` only in intent; Compose cannot enforce egress allow-lists - use host firewall/proxy for that.

## Data protection
- **Customer text is sent to Google** inside Gemini prompts. Customer must review Google's data-use terms for their API tier and must not route regulated data (PCI, PHI) through this system. Agent prompts forbid asking for passwords, CVVs, card numbers.
- Logs/metrics contain **no** customer text or answers - only request ID, route label, status, latency, category, query length. A redaction filter additionally masks `AQ.`/`AIza` keys, Bearer tokens, Vault tokens and `key=value` secrets, including in tracebacks.
- Validation errors return field names and messages only, never the submitted input.
- Responses carry `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.
- Order data is **demo data** (`tools/order_tools.py`), not real customer records.
- No database: nothing is persisted by the app. Prometheus/Grafana volumes hold only aggregate metrics and Grafana config.

## Threat mitigation
| Threat | Mitigation | Residual risk |
|---|---|---|
| API key theft from repo/image | Not in Git (history scanned), image, or env; `.dockerignore` | Host compromise exposes `secrets/` |
| Key leakage via logs/errors | Redaction filter; Gemini errors mapped to a reason code and raised `from None`; generic client messages; tested | New log statements must follow the pattern |
| Token guessing / brute force | 256-bit tokens, constant-time compare, failure metric + alert | **No rate limiting or lockout** - add at reverse proxy |
| Prompt injection | Customer text fenced in `<customer_query>` tags with "untrusted data" instruction; agents have no tools/side effects (read-only demo lookup) | LLM output may still be wrong; do not wire agents to refund/account actions without extra controls |
| Hallucinated policies/refunds | Prompts forbid inventing policy/status and claiming actions | Not guaranteed; human review for sensitive cases |
| Container breakout / privilege escalation | Non-root UID, `cap_drop: ALL`, `no-new-privileges`, read-only root, pids/CPU/memory limits | Shared kernel; Vault/Prometheus/Grafana images run with their upstream default users |
| DoS / cost exhaustion | 2000-char limit, 30 s Gemini timeout, container limits | No per-client quota; a valid token can drive Gemini spend - set Google quota/budget alerts |
| Supply chain | Minimal deps (openai-agents removed), version ranges, pinned image tags | Pin exact versions/digests and scan images (e.g. Trivy) - not done here |
| Metrics scraping by others | Separate token; Prometheus not published | - |
| Vault dev-mode misuse | Clearly labelled, internal network only | Never use as production Vault |
