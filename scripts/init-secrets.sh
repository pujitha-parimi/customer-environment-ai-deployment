#!/usr/bin/env bash
# Creates ./secrets/*.txt for file-based Docker secrets (Linux/macOS/WSL/Git-Bash).
# Gemini key is read with hidden input; tokens/passwords are generated randomly.
# Existing files are NEVER overwritten unless --rotate-tokens is given (Gemini key is only replaced with --replace-gemini-key).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p secrets; umask 077
gen() { head -c 48 /dev/urandom | base64 | tr -d '=+/\n' | cut -c1-43; }
put() { printf %s "$2" > "secrets/$1"; chmod 644 "secrets/$1"; }   # 644: container users (app/prometheus/grafana) must read it; protect the DIRECTORY
rotate=false; replace=false
for a in "$@"; do [ "$a" = "--rotate-tokens" ] && rotate=true; [ "$a" = "--replace-gemini-key" ] && replace=true; done

if [ ! -s secrets/gemini_api_key.txt ] || $replace; then
  printf 'Paste Gemini API key (input hidden): '; read -rs key; printf '\n'
  [ -n "$key" ] || { echo "empty key - aborting" >&2; exit 1; }
  put gemini_api_key.txt "$(printf %s "$key" | tr -d '\r\n ')"; unset key
fi
for f in customer_api_tokens metrics_token grafana_admin_password; do
  if [ ! -s "secrets/$f.txt" ] || { $rotate && [ "$f" != grafana_admin_password ]; }; then put "$f.txt" "$(gen)"; echo "generated secrets/$f.txt"; fi
done
echo "Done. Customer API token is in secrets/customer_api_tokens.txt (give it to the client over a secure channel)."
