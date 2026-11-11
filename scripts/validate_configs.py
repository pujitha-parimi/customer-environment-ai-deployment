"""Static validation of deployment config (no Docker needed). Run: python scripts/validate_configs.py

This is NOT a substitute for `docker compose config` / `promtool check config`
(run those too - see docs/deployment-validation.md); it catches structural and
cross-file mistakes: dashboard/alert metrics that the app does not export,
published ports not bound to loopback, missing healthchecks, etc.
"""
import json, re, sys, pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
errors, notes = [], []


class L(yaml.SafeLoader):
    pass
for tag in ("!override", "!reset"):
    L.add_constructor(tag, lambda loader, node: loader.construct_sequence(node) if isinstance(node, yaml.SequenceNode) else None)


def load(p):
    return yaml.load((ROOT / p).read_text(), Loader=L)


def check(cond, msg):
    (notes if cond else errors).append(("ok   " if cond else "FAIL ") + msg)


compose = load("docker-compose.yml")
vault = load("docker-compose.vault.yml")
prom = load("deploy/prometheus/prometheus.yml")
alerts = load("deploy/prometheus/alerts.yml")
ds = load("deploy/grafana/provisioning/datasources/prometheus.yml")
dash = json.loads((ROOT / "deploy/grafana/dashboards/support-api.json").read_text())

svcs = compose["services"]
for name, s in svcs.items():
    check("healthcheck" in s, f"{name}: has healthcheck")
    check(s.get("restart") == "unless-stopped", f"{name}: restart policy")
    check("no-new-privileges:true" in s.get("security_opt", []), f"{name}: no-new-privileges")
    check(s.get("cap_drop") == ["ALL"], f"{name}: cap_drop ALL")
    check("limits" in s.get("deploy", {}).get("resources", {}), f"{name}: resource limits")
    for port in s.get("ports", []):
        check(str(port).startswith("127.0.0.1:"), f"{name}: port {port} bound to loopback only")
check("ports" not in svcs["prometheus"], "prometheus: no published ports")
check(compose["networks"]["monitor_net"].get("internal") is True, "monitor_net is internal")
check(svcs["app"].get("read_only") is True, "app: read-only root filesystem")
check("monitor_net" in svcs["prometheus"]["networks"] and "app_net" not in svcs["prometheus"]["networks"], "prometheus only on monitor_net")
env = svcs["app"]["environment"]
check(not any(re.search(r"KEY|TOKEN|PASSWORD", k) and not k.endswith("_FILE") for k in env), "app env holds no raw secret values (only *_FILE paths)")
for sec in compose["secrets"].values():
    check(sec["file"].startswith("./secrets/"), f"secret file under ./secrets/ ({sec['file']})")
check(vault["services"]["vault"]["networks"] == ["secrets_net"] and vault["networks"]["secrets_net"]["internal"], "vault only on internal secrets_net, not published")
check("ports" not in vault["services"]["vault"], "vault: no published ports")

# Dockerfile
df = (ROOT / "Dockerfile").read_text()
check(re.search(r"^USER 10001", df, re.M) is not None, "Dockerfile runs as non-root USER 10001")
check("HEALTHCHECK" in df, "Dockerfile has HEALTHCHECK")
check(not re.search(r"^(ENV|ARG).*(KEY|TOKEN|SECRET|PASSWORD)", df, re.M | re.I), "Dockerfile has no secret ENV/ARG")
di = (ROOT / ".dockerignore").read_text().split()
check(all(x in di for x in (".env", "secrets/", ".git")), ".dockerignore excludes .env, secrets/, .git")

# Prometheus
jobs = {j["job_name"]: j for j in prom["scrape_configs"]}
check("support-api" in jobs and jobs["support-api"]["static_configs"][0]["targets"] == ["app:8000"], "prometheus scrapes app:8000")
check(jobs["support-api"]["authorization"]["credentials_file"] == "/run/secrets/metrics_token", "prometheus uses bearer credentials_file")
check(prom["rule_files"] == ["/etc/prometheus/alerts.yml"], "rule file path matches compose mount")

# metric names used in dashboard/alerts must exist in metrics.py
src = (ROOT / "metrics.py").read_text()
defined = set(re.findall(r'(?:Counter|Gauge|Histogram)\(\s*"([a-z_]+)"', src))
defined |= {n + s for n in list(defined) for s in ("_bucket", "_sum", "_count")} | {"up"}
def used(expr):
    return set(re.findall(r"\b([a-z][a-z0-9_]*)(?=[{\[ (]|$)", expr)) & set(re.findall(r"\b(?:http|support|gemini|auth|up)[a-z_]*", expr))
exprs = [t["expr"] for p in dash["panels"] for t in p["targets"]]
exprs += [r["expr"] for g in alerts["groups"] for r in g["rules"]]
for e in exprs:
    for m in re.findall(r"\b((?:http|support|gemini|auth)_[a-z_]+|up)\b(?=[{\[ ]|$)", e):
        check(m in defined, f"metric '{m}' used in query exists in metrics.py")
        if m not in defined:
            break
ds_uid = ds["datasources"][0]["uid"]
check(all(p["datasource"]["uid"] == ds_uid for p in dash["panels"]), "dashboard datasource uid matches provisioned datasource")
check(len({p["id"] for p in dash["panels"]}) == len(dash["panels"]), "dashboard panel ids unique")
check(all(r.get("expr") and r.get("alert") for g in alerts["groups"] for r in g["rules"]), "every alert has name + expr")

print("\n".join(notes + errors))
print(f"\n{len(notes)} checks passed, {len(errors)} failed")
sys.exit(1 if errors else 0)
