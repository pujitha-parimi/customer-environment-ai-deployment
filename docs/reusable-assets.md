# Reusable Assets

| Asset | Location | Reuse for other customers | What to change |
|---|---|---|---|
| **Query classifier + router** | `service.py` | any "triage then specialist" assistant (HR, IT helpdesk, sales) | category list, prompts |
| **Specialist agent pattern** | `agents/*` (rules list + fenced untrusted input) | new domain agents | prompt rules, add tools |
| **Gemini access layer** | `llm_client.py` | any Gemini project: lazy SDK import, key-rotation aware client, safe error taxonomy | model/config only |
| **Input validation** | `tools/customer_tools.py`, Pydantic schemas in `api.py` | any text API | limits |
| **Demo tool pattern** | `tools/order_tools.py` | replace with real order/CRM API client behind the same function signature | data source |
| **API skeleton** | `api.py` (+`security.py`) | health/ready/query/metrics, bearer auth with rotation, request IDs, non-leaking error handlers, security headers | schemas, scopes |
| **Secrets provider** | `secrets_provider.py` | Vault AppRole -> file -> env chain, rotation without restart, stdlib only; swap Vault branch for AWS/Azure/GCP SDK | backend |
| **Log redaction** | `logging_config.py` | drop-in JSON logging that masks keys/tokens | add patterns |
| **Hardened Dockerfile** | `Dockerfile`, `.dockerignore` | any Python service: non-root, healthcheck, no secrets in image | file list |
| **Compose template** | `docker-compose.yml`, `docker-compose.vault.yml` | network segmentation (internal nets), loopback ports, read-only fs, cap_drop, limits, file secrets, Vault overlay | services |
| **Monitoring stack** | `deploy/prometheus/*`, `deploy/grafana/*` | RED dashboard (rate/errors/duration) + alert rules for any service exporting `http_requests_total` and `http_request_duration_seconds` | job targets, extra panels |
| **Vault policies** | `deploy/vault/*.hcl`, `bootstrap.sh` | app/operator/admin policy trio | paths |
| **Secret bootstrap scripts** | `scripts/init-secrets.*` | hidden-prompt + random token generation | names |
| **Config validator** | `scripts/validate_configs.py` | CI check for compose security posture and dashboard/metric drift | rules |
| **Gemini key diagnostic** | `scripts/diagnose_gemini.py` | first-line support tool for `API_KEY_INVALID`-type issues; never prints keys | - |
| **Test harness** | `tests/helpers.py` (`FakeGemini`), fake-Vault server in `tests/test_secrets_and_logging.py` | mock Gemini at the SDK boundary and Vault over HTTP without network | - |
| **FDE docs set** | `docs/` | architecture, IAM, security, runbook, KT, validation templates | customer specifics |

Reuse opportunities: package `llm_client` + `secrets_provider` + `logging_config` + `metrics` as an internal library; turn the compose files into a cookiecutter; add a Terraform/Helm variant of the same layout for cloud customers.
