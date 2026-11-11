# Operational Runbook

Commands are PowerShell (Docker Desktop / Windows); they work in bash too except where noted. Run from the project root.

## 1. Prerequisites
Docker Desktop (Compose v2; v2.24+ for the Vault overlay), a Gemini API key from https://aistudio.google.com/apikey, outbound HTTPS to `generativelanguage.googleapis.com`.

## 2. Installation and first start (default: file secrets)
```powershell
.\scripts\init-secrets.ps1            # prompts (hidden) for the Gemini key; generates customer/metrics tokens + Grafana password
docker compose config -q              # validate
docker compose up -d --build
docker compose ps                     # wait for all services "healthy"
curl http://localhost:8000/health
curl http://localhost:8000/ready      # must say "ready"
```
Linux/macOS: `./scripts/init-secrets.sh`. Grafana: http://localhost:3000, user `admin`, password in `secrets\grafana_admin_password.txt`.

First query:
```powershell
$t = (Get-Content secrets\customer_api_tokens.txt -Raw).Trim()
curl -X POST http://localhost:8000/query -H "Authorization: Bearer $t" -H "Content-Type: application/json" -d '{\"query\":\"Where is my order ORD1001?\"}'
```
(The order query needs no Gemini call, so it works even before the Gemini key is valid.)

## 3. Vault mode (local simulation)
```powershell
"VAULT_DEV_ROOT_TOKEN=$([guid]::NewGuid())" | Add-Content .env      # local dev only
$f = "-f","docker-compose.yml","-f","docker-compose.vault.yml"
docker compose @f up -d vault
docker compose @f exec vault sh /vault-init/bootstrap.sh     # hidden Gemini key prompt; prints customer token once
docker compose @f up -d --build
curl http://localhost:8000/ready                              # "vault":"ok"
```
`./secrets/` still needs `grafana_admin_password.txt` (run `init-secrets` first; it is harmless that it also creates unused file secrets). Dev Vault loses data on restart: re-run `bootstrap.sh` and `docker compose @f up -d`.

## 4. Startup / shutdown
```powershell
docker compose up -d            # start        | docker compose stop      # stop, keep data
docker compose restart app      # restart app  | docker compose down      # remove containers (volumes kept)
docker compose down -v          # DESTROYS Prometheus/Grafana data
```
Containers use `restart: unless-stopped` and come back after a Docker Desktop restart.

## 5. Monitoring
Grafana dashboard **Support Platform / Customer Support API**: availability, request rate, 5xx ratio, p50/p95/p99 latency, category mix, Gemini errors by reason, rejected credentials. Alerts (Prometheus -> `http://localhost:9090` is *not* published; use `docker compose exec prometheus wget -qO- http://localhost:9090/api/v1/alerts`): `SupportApiDown`, `HighServerErrorRate`, `HighLatencyP95`, `GeminiFailures`, `AuthFailureSpike`. No Alertmanager is configured - alerts are visible, not delivered; wire a notifier (Alertmanager/Grafana contact point) as a customer step.
Logs: `docker compose logs -f app` (JSON lines).

## 6. Troubleshooting
| Symptom | Likely cause | Action |
|---|---|---|
| `/ready` 503, `gemini_api_key_configured:false` | secrets file empty/missing or Vault unreachable | check `secrets\gemini_api_key.txt`; `docker compose logs app` |
| `/query` 502; log `reason=bad_request_or_invalid_key` | Gemini `400 API_KEY_INVALID`: key revoked, truncated, wrong key type | `python scripts/diagnose_gemini.py --live` (never prints the key). Create a new AI Studio key, `.\scripts\init-secrets.ps1 -ReplaceGeminiKey` - no restart needed |
| 502 `unauthorized` | key not permitted/API not enabled/restrictions | enable Generative Language API; check key restrictions |
| 502 `model_not_found` | wrong `GEMINI_MODEL` | list models via diagnose script; set `GEMINI_MODEL` in `.env` or shell, `docker compose up -d` |
| 502 `rate_limited` | quota | wait / raise quota / billing |
| 502 `timeout` / `upstream_error` | network or Google outage | check egress/proxy; retry |
| 401 on `/query` | wrong/rotated token | read current `secrets\customer_api_tokens.txt` |
| Prometheus target down | metrics token mismatch | `secrets\metrics_token.txt` must be readable by the Prometheus container (Linux: mode 644) |
| Grafana "No data" | Prometheus unhealthy / no traffic | `docker compose ps`; send a query |
| `up` fails: bind source path does not exist | missing `secrets/*.txt` | run init-secrets script |

## 7. Incident response
1. **Detect** (alert, dashboard, customer report). 2. **Contain:** suspected key leak => revoke (section 9) *before* investigating; suspected token leak => remove that token. `docker compose stop app` stops all service. 3. **Preserve:** `docker compose logs app > incident-$(date).log` (already redacted; contains no customer text). 4. **Eradicate/recover:** rotate affected secrets, redeploy. 5. **Review:** identify root cause, update runbook/tests. Check Google AI Studio/Cloud usage page for unexpected spend.

## 8. Backup and recovery
| Item | Backup | Recovery |
|---|---|---|
| `secrets/` (default mode) | Encrypted offline copy by admin (it is the only copy of the Gemini key; the key itself can be re-issued from Google) | restore folder, `up -d` |
| Vault dev data | **Not recoverable** (in-memory) - keep source secrets elsewhere; re-bootstrap | `bootstrap.sh` |
| Grafana data | `docker run --rm -v support-platform_grafana_data:/d -v ${PWD}:/b busybox tar czf /b/grafana.tgz -C /d .` | reverse with `tar xzf` into a fresh volume |
| Prometheus data | optional (metrics only); same tar approach | or accept loss |
| App | stateless - rebuild from source | `docker compose up -d --build` |

## 9. Secret rotation and revocation
**Gemini key (rotate):** create new key in AI Studio -> `.\scripts\init-secrets.ps1 -ReplaceGeminiKey` -> verify `/ready`, send a test query (the app rebuilds its client automatically when the file changes; no restart) -> delete the old key in AI Studio. Vault mode: re-run `bootstrap.sh` (or `vault kv patch secret/support-app gemini_api_key=...` as admin).
**Gemini key (revoke/compromise):** delete the key in Google AI Studio/Cloud *first*, then replace as above. `/query` returns 502 until replaced.
**Customer token (rotate with zero downtime):** add the new token to `customer_api_tokens.txt` as a second comma-separated value, give it to the client, then remove the old one after the client switched. Quick full rotation: `.\scripts\init-secrets.ps1 -RotateTokens`. **Revoke one client:** delete its token from the list (effective immediately, file is read per request).
**Metrics token:** `-RotateTokens`, then `docker compose restart prometheus app` to be certain both sides pick up the new value.
**Vault AppRole `secret_id` (revoke):** destroy the old one via the `secret-id-accessor/destroy` endpoint (see Vault AppRole docs; not exercised here) and issue a new one with `vault write -f auth/approle/role/support-app/secret-id`, then update `secrets/vault_secret_id`. Revoking the AppRole token cuts the app off within ~15 minutes at most (cache TTL 30 s, token TTL 15 min).
**Grafana password:** change in UI or replace `grafana_admin_password.txt` then recreate the container (only applies to first init of the Grafana DB; otherwise use `grafana cli admin reset-admin-password`).

## 10. Upgrade and rollback
```powershell
git pull; docker compose build --pull; docker tag multi-agent-customer-support:1.1.0 multi-agent-customer-support:previous
docker compose up -d
curl http://localhost:8000/ready          # verify, then send one test query
```
Rollback: `git checkout <previous-tag>; docker compose up -d --build` (secrets and metrics volumes are unaffected). Before upgrading third-party images (Prometheus/Grafana/Vault) back up volumes and read their release notes.
