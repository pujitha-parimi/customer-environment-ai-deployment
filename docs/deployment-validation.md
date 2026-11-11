# Deployment Validation

Validation was performed in a build sandbox **without network access, Docker, or the FastAPI stack installed**. The table separates what was actually executed from what must be run on the customer's Docker host. Nothing marked "not executed" should be treated as passing.

## Executed in the build sandbox (Python 3.12)

| Check | Command | Result |
|---|---|---|
| All modules compile | `python -m compileall .` | OK |
| Unit tests (logic, agents, routing, order lookup, validation, secrets provider incl. fake Vault HTTP server, log redaction, LLM client error mapping, key rotation) | `python -m unittest discover -s tests -t . -v` | **43 executed, 43 passed**; 17 API tests **skipped** (FastAPI not installed) |
| CLI starts; order query answered with no key/network | `python main.py` | OK |
| CLI with Gemini unconfigured -> safe message, no traceback | `python main.py` | OK |
| Gemini error handling does not leak provider text/keys | `test_llm_client` | passed |
| Log redaction of `AQ.`, `AIza`, Bearer, Vault tokens | `test_secrets_and_logging` | passed |
| Compose/Prometheus/Grafana/Dockerfile static checks (57), incl. dashboard & alert metrics exist in `metrics.py`, loopback-only ports, internal networks, non-root, no secret ENV | `python scripts/validate_configs.py` | **57 passed, 0 failed** |
| YAML/JSON parse (compose, overlay, prometheus, alerts, Grafana datasource/dashboard) | via validator | OK |
| Shell syntax (`bootstrap.sh`, `init-secrets.sh`) and functional test of `init-secrets.sh` (create, no-overwrite, rotate) | `sh -n`, scripted run | OK |
| Git review: `.env` ignored, `.env.example` not ignored (was a bug), `secrets/` ignored, real key value absent from working tree (other than `.env`) and from all Git objects | scripted | OK |
| Gemini key shape diagnostic (offline) | `scripts/diagnose_gemini.py` | ran; key format `AQ.`, no whitespace/quotes/placeholder |

## NOT executed here - run on the customer/Docker host

| Check | Command | Expected |
|---|---|---|
| Install deps | `pip install -r requirements-dev.txt` | success |
| **API tests (17)** | `python -m unittest discover -s tests -t . -v` | 60 tests, 0 skipped, all pass. **These were written but never run; fix any failure before sign-off.** |
| FastAPI starts | `uvicorn api:app` | listens on :8000 |
| `/health`, `/ready`, `/query` (mocked), auth | covered by API tests | pass |
| Compose validation | `docker compose config -q` and `docker compose -f docker-compose.yml -f docker-compose.vault.yml config -q` | no output/errors |
| Image build | `docker compose build` | success |
| Stack health | `docker compose up -d; docker compose ps` | app, prometheus, grafana `healthy` |
| Non-root | `docker compose exec app id` | `uid=10001` |
| Prometheus config | `docker run --rm -v ${PWD}/deploy/prometheus:/c --entrypoint promtool prom/prometheus:v2.55.1 check config /c/prometheus.yml` (needs `/run/secrets/metrics_token` or run `check rules /c/alerts.yml`) | SUCCESS |
| Prometheus scrape works | Prometheus targets: `support-api` UP | UP |
| Grafana dashboard loads with data | http://localhost:3000 | panels populated after a few queries |
| Vault overlay end-to-end | runbook section 3 | `/ready` shows `"vault":"ok"` |
| PowerShell script `init-secrets.ps1` | run on Windows | creates 4 files |
| Image tags exist (`prom/prometheus:v2.55.1`, `grafana/grafana:11.3.0`, `hashicorp/vault:1.18`) | `docker pull` | success (tags chosen from knowledge, not verified online) |

## Requires external credentials
- **Live Gemini request.** Never verified. Your reported `400 API_KEY_INVALID` is unresolved: the configured key has the newer `AQ.` format (53 chars, no whitespace/quotes), so it is not a `.env` formatting problem. Run `python scripts/diagnose_gemini.py --live`. Probable causes: key revoked/regenerated or truncated when copied, or created for a different Google API than the Gemini Developer API. Create a fresh key in AI Studio and replace it via `init-secrets`. Also note the previous `test_gemini.py` hard-coded a model name (`gemini-3.5-flash-lite`) that may not exist for your key; the app now uses `GEMINI_MODEL`.
- Customer's Google project quota/billing/key restrictions.

## Requires manual customer configuration
TLS reverse proxy; Grafana users/roles; Alertmanager or Grafana contact points; Vault human identities; Google key restrictions and budget alerts; disk encryption/backup of `secrets/`; `ENABLE_DOCS=false` for production.

## Acceptance criteria
| # | Criterion | Status |
|---|---|---|
| 1 | Three agents, classification, routing, order lookup, validation | Implemented; unit-tested (executed, passed) |
| 2 | `/health`, `/ready`, `/query` with token auth, schemas, safe errors, Swagger | Implemented; **tests written, not yet executed** |
| 3 | Docker image, compose, non-root, health checks, restart, networks, limits | Implemented; static checks passed; **build/run not executed** |
| 4 | Secrets management (Vault optional + file secrets), rotation/revocation docs | Implemented; provider tested against fake Vault; real Vault **not executed** |
| 5 | IAM model | Designed and documented; local simulation only; no cloud IAM configured |
| 6 | Prometheus + Grafana + metrics + alerts | Implemented; static validation passed; **not run** |
| 7 | Tests run without real Gemini | Yes (all mocked) |
| 8 | No secrets in Git | Verified (working tree + history) |
| 9 | Live Gemini works | **Not verified** |

## Known limitations
Order data is demo data; billing/technical agents give guidance only and perform no actions; no rate limiting; no TLS; no alert delivery; Vault is dev mode; Compose cannot enforce egress allow-lists; images not vulnerability-scanned or digest-pinned; Prometheus/Grafana/Vault use upstream default users; single instance (no HA); no conversation history; customer text is processed by Google.
