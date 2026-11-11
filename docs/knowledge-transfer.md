# Knowledge Transfer

## System architecture (one paragraph)
`api.py` (FastAPI) authenticates, validates, meters and logs; `service.py` decides what to do with a question (demo order lookup, or Gemini classification then a billing / technical / general agent); `llm_client.py` is the only code that talks to Gemini; `secrets_provider.py` finds secrets (Vault, files, env); Prometheus and Grafana observe the API. See `deployment-architecture.md` for the diagram.

## Repository map
| Path | What |
|---|---|
| `api.py`, `security.py`, `metrics.py` | HTTP layer, token check, Prometheus metrics |
| `service.py` | `classify_query`, `handle_order_query`, `route_query` |
| `agents/` | prompts for general, billing, technical agents |
| `tools/` | input validation, demo order data (`SAMPLE_ORDERS`) |
| `llm_client.py`, `config.py`, `secrets_provider.py`, `logging_config.py` | Gemini access, settings, secrets, JSON logs + redaction |
| `main.py` | interactive CLI |
| `tests/` | unit/API tests (all Gemini calls mocked) |
| `scripts/` | `init-secrets.*`, `diagnose_gemini.py`, `verify_gemini_live.py` (opt-in live test), `validate_configs.py` |
| `deploy/` | Prometheus, Grafana, Vault files |

## Customer operations (day-to-day)
Start/stop, rotate, back up and upgrade: `operational-runbook.md` sections 4, 8, 9, 10. Who may do what: `iam-design.md`.

## API usage
Base URL `http://localhost:8000`. Interactive docs: `/docs`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | none | liveness (`{"status":"healthy"}`) |
| `GET /ready` | none | config readiness; 200 ready / 503 not_ready |
| `POST /query` | `Bearer` customer token | ask a question |
| `GET /metrics` | `Bearer` metrics token | Prometheus format |

```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"I was charged twice for my subscription"}'
# 200 {"category":"billing","answer":"...","request_id":"3f1c..."}
```
| Status | Meaning |
|---|---|
| 200 | answered |
| 401 | missing/invalid token |
| 422 | invalid body (empty, >2000 chars, wrong type, unknown field) |
| 502 | Gemini failed (key invalid, quota, timeout, outage) |
| 503 | Gemini key not configured |
| 500 | unexpected error (generic message; see logs by `request_id`) |

Send `X-Request-ID` (8-64 chars `[A-Za-z0-9_-]`) to correlate; it is echoed back.

## Configuration
| Variable | Default | Notes |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | must exist for your key; check with `diagnose_gemini.py --live` |
| `GEMINI_TIMEOUT_SECONDS` | 30 | 1-120 |
| `LOG_LEVEL` | INFO | |
| `ENABLE_DOCS` | true | set false in production |
| `MAX_QUERY_LENGTH` | 2000 | cannot exceed 2000 (API schema limit) |
| `GEMINI_API_KEY`, `CUSTOMER_API_TOKENS`, `METRICS_TOKEN` | - | secrets; each also accepts `NAME_FILE` (path) and, with `VAULT_ADDR`, Vault |
| `VAULT_ADDR`, `VAULT_KV_MOUNT`, `VAULT_SECRET_PATH`, `VAULT_ROLE_ID_FILE`, `VAULT_SECRET_ID_FILE` | - / secret / support-app / /run/secrets/... | Vault mode |

## Troubleshooting and monitoring
See runbook sections 5-6. The "Gemini errors by reason" panel tells you immediately whether failures are key problems (`bad_request_or_invalid_key`, `unauthorized`), configuration (`model_not_found`), quota (`rate_limited`) or provider side (`timeout`, `upstream_error`).

## Known gaps to hand over explicitly
Real billing/order integrations, TLS, rate limiting, alert delivery, production Vault, conversation history - see `deployment-validation.md`.
