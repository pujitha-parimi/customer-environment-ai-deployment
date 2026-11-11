# Multi-Agent Customer Support System

A customer-deployable support assistant: FastAPI service + Gemini-powered billing / technical / general agents, with Docker deployment, secrets management, monitoring and operations documentation.

> **Status honesty:** see [docs/deployment-validation.md](docs/deployment-validation.md) for exactly what has and has not been executed. Live Gemini access, Docker build/run and the FastAPI test suite must be verified on your machine.

## Features
- Query validation -> demo order lookup (no LLM call) -> Gemini classification -> specialist agent
- REST API: `GET /health`, `GET /ready`, `POST /query` (Bearer auth), `GET /metrics` (separate token), Swagger at `/docs`
- Structured JSON logs with secret redaction; no customer text in logs/metrics
- Docker Compose stack: app + Prometheus + Grafana (+ optional HashiCorp Vault), segmented networks, non-root, read-only, resource-limited
- Mocked-Gemini automated tests; static deployment validator

## Quick start (Docker Desktop, Windows)
```powershell
.\scripts\init-secrets.ps1          # hidden prompt for your Gemini key; generates tokens
docker compose up -d --build
curl http://localhost:8000/ready
```
Details, Vault mode, rotation, backup, troubleshooting: [docs/operational-runbook.md](docs/operational-runbook.md).

## Local development
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
copy .env.example .env              # then edit: real key + local tokens (never commit .env)
python -m unittest discover -s tests -t . -v      # no real Gemini calls
python scripts/diagnose_gemini.py --live          # checks your key safely (prints no secrets)
uvicorn api:app --reload                          # http://localhost:8000/docs
python main.py                                    # interactive CLI
```

## Example
```bash
curl -X POST http://localhost:8000/query -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"query":"Where is my order ORD1002?"}'
```
Demo orders: `ORD1001`, `ORD1002`, `ORD1003` (sample data, not real orders).

## Troubleshooting `400 API_KEY_INVALID`
Google rejected the key itself. Run `python scripts/diagnose_gemini.py --live`; create a new key at https://aistudio.google.com/apikey; replace it (`init-secrets.ps1 -ReplaceGeminiKey`). Ensure `GEMINI_MODEL` exists for your key. (Old helper scripts `check_*.py`/`list_gemini_models.py` were replaced by this diagnostic; the old live `test_gemini.py` is now the opt-in `scripts/verify_gemini_live.py`.)

## Documentation
| Doc | Content |
|---|---|
| [deployment-architecture](docs/deployment-architecture.md) | diagram, networks, data flow, ownership |
| [iam-design](docs/iam-design.md) | roles, least privilege, cloud equivalents (design only) |
| [security-design](docs/security-design.md) | auth, secrets, network, data protection, threats |
| [operational-runbook](docs/operational-runbook.md) | install, run, monitor, incidents, backup, rotation, upgrade |
| [knowledge-transfer](docs/knowledge-transfer.md) | architecture, API, config |
| [reusable-assets](docs/reusable-assets.md) | components for other customers |
| [deployment-validation](docs/deployment-validation.md) | verified vs. unverified, acceptance criteria, limitations |

## Project layout
```text
api.py security.py metrics.py        HTTP layer
service.py agents/ tools/            support logic
llm_client.py config.py secrets_provider.py logging_config.py
main.py                              CLI
tests/                               unittest suite (Gemini mocked)
scripts/                             secrets init, diagnostics, validators
deploy/                              prometheus, grafana, vault
Dockerfile docker-compose.yml docker-compose.vault.yml
```

## Limitations
Demo order data; billing/technical agents give guidance only and take no actions; no TLS or rate limiting in the stack; Vault overlay is dev-mode; see validation doc.

## License
Add your preferred license before distributing publicly.
