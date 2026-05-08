# Hub Auth Setup — Production Runbook

> **Why**: Hub ships with BasicAuth available but DISABLED by default
> (so localhost development is friction-free). Anything beyond
> `127.0.0.1` — LAN, reverse proxy, port-forward — needs `HUB_PASSWORD`
> set BEFORE exposure.
>
> **Confirmation it's disabled**: at hub startup you'll see
> `⚠ BasicAuth disabled — set HUB_PASSWORD env var to require login`.
> If you don't see that line, BasicAuth is on.

## TL;DR — three steps

```
1. Pick a strong password (use a password manager)
2. Set HUB_PASSWORD env var the way your deployment manages env vars
   (NSSM service → AppEnvironmentExtra; bare process → shell export;
    Docker → -e HUB_PASSWORD=...)
3. Restart hub. Confirm startup log says "🔐 BasicAuth enabled (username: 'hub')"
```

`HUB_USERNAME` defaults to `hub` — override via env if you want.

---

## NSSM (Windows Service) — what this hub uses

Hub on this machine runs as a Windows service via NSSM. The
`logs/service-stderr-*.log` files (134+ at last count) are the NSSM
crash + restart history.

To set `HUB_PASSWORD`:

```powershell
# Run from an elevated (Administrator) PowerShell:
nssm set <ServiceName> AppEnvironmentExtra "HUB_PASSWORD=<strong-password>" "HUB_USERNAME=hub"

# Verify
nssm get <ServiceName> AppEnvironmentExtra

# Restart the service to pick up the new env
nssm restart <ServiceName>
```

To find `<ServiceName>` (if you don't remember it):

```powershell
Get-Service | Where-Object { $_.DisplayName -like "*F180*" -or $_.DisplayName -like "*Hub*" }
```

After restart, hit `http://localhost:8080/` — you should get a browser
auth dialog instead of the dashboard loading immediately.

---

## Bare process (no service wrapper)

```bash
# Linux / macOS / WSL:
export HUB_PASSWORD="your-strong-password"
python scripts/serve_prod.py --host 0.0.0.0 --port 8080

# Windows CMD:
set HUB_PASSWORD=your-strong-password
python scripts\serve_prod.py --host 0.0.0.0 --port 8080
```

For persistence, write `HUB_PASSWORD` to `.env` (gitignored) and load
via `python-dotenv` at startup, OR set as a system env var via
`setx` / `/etc/environment`.

---

## Docker / Compose

```yaml
# docker-compose.yml
services:
  hub:
    image: qa-hub-saucedemo:latest
    environment:
      HUB_PASSWORD: "${HUB_PASSWORD}"
      HUB_USERNAME: "hub"
    ports: ["8080:8080"]
```

```bash
# .env (don't commit)
HUB_PASSWORD=your-strong-password
```

```bash
docker compose up -d
docker compose logs hub | grep BasicAuth
# Expect: 🔐 BasicAuth enabled (username: 'hub')
```

---

## Verification checklist

After restart, before exposing beyond localhost:

- [ ] Startup log shows `🔐 BasicAuth enabled (username: 'hub')`
- [ ] `curl http://localhost:8080/api/projects` returns `401 Unauthorized` without `-u`
- [ ] `curl -u hub:<password> http://localhost:8080/api/projects` returns `200`
- [ ] Browser opens login dialog when visiting the dashboard
- [ ] Vue v2 SPA at `/v2/` also gates behind auth
- [ ] `/api/scaffold/sync/<pid>` POST without auth → 401 (sync subprocess is
      the most expensive endpoint; auth here is critical)

If all six pass, you can safely move to:

1. **Reverse proxy** (Caddy / nginx — see `frontend/PRODUCTION.md`)
2. **HTTPS** (Caddy auto-provisions Let's Encrypt; nginx via certbot)
3. **Bind to `0.0.0.0`** instead of `127.0.0.1`

---

## Other env vars Hub respects

| Env var | Default | Purpose |
|---|---|---|
| `HUB_PASSWORD` | (empty → auth disabled) | BasicAuth password |
| `HUB_USERNAME` | `hub` | BasicAuth username |
| `HUB_SMTP_PASS` | (config.json fallback) | SMTP password — prefer env over config |
| `HUB_RESEND_API_KEY` | (config.json fallback) | Resend API key — prefer env over config |

Setting `HUB_SMTP_PASS` / `HUB_RESEND_API_KEY` via env (instead of
inside `config.json`) is recommended even for localhost — keeps secrets
out of the JSON state file that's regularly diffed and edited.

---

## Recovering from "lost the password"

1. Stop the hub service (`nssm stop <ServiceName>` or kill the process)
2. Unset `HUB_PASSWORD` (`nssm set <ServiceName> AppEnvironmentExtra ""`
   for NSSM, or remove from .env)
3. Restart — hub starts with BasicAuth disabled, recover access
4. Set a new `HUB_PASSWORD` and restart again

---

## Rate limiting (next layer of protection)

Auth alone doesn't protect against a logged-in user spamming expensive
endpoints. Rate limiting is **NOT yet built into hub** — for LAN /
team exposure, run hub behind a reverse proxy that enforces request
limits per IP. Caddy example:

```caddyfile
hub.internal.example {
  reverse_proxy 127.0.0.1:8080

  # Throttle subprocess-spawning endpoints
  rate_limit {
    zone sync_throttle {
      key {remote_ip}
      events 5
      window 1m
    }
    match path /api/scaffold/sync/* /api/projects/add
    zone sync_throttle
  }
}
```

Documented for follow-up; not blocking single-operator localhost use.
