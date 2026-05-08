# Hub v2 — Production Deployment Guide

Vue v2 is now feature-complete enough to be the primary UI. Legacy `/`
remains available as a fallback. This guide covers deploying both side
by side and (later) sunsetting legacy.

## Build pipeline

Every push to master rebuilds the frontend in CI (`vue-build` job in
`.github/workflows/tests.yml`). On a server, run the same command:

```bash
cd frontend
npm ci                    # exact lockfile install — use in CI/prod
npm run build             # outputs ../static/dist/
```

`npm run build` runs `vue-tsc -b && vite build`, so a TypeScript error
fails the build (same as CI).

## Running in production

```bash
# Inside Hub root
python scripts/serve_prod.py --host 0.0.0.0 --port 8080
```

Hub serves:
- `/`           → legacy `templates/dashboard.html` (vanilla)
- `/v2/`        → built Vue SPA (`static/dist/index.html`)
- `/v2/<any>`   → same SPA — vue-router handles client-side routing
- `/static/dist/assets/*` → JS/CSS chunks via Flask static handler

## Reverse proxy

The Caddy + nginx examples in `scripts/Caddyfile.example` and
`scripts/nginx.conf.example` work unchanged for v2 — both routes
go through the same `127.0.0.1:8080` upstream.

## Security hardening (Sprint G — v2.9.0)

Hub ships with these security defaults baked in. No extra config needed
for **localhost** use; production exposure (LAN / internet) needs the
HTTPS step at the bottom.

### Built into the app (always on)

| Layer | Mechanism | Configurable via |
|---|---|---|
| **P2.2 Response headers** | `X-Content-Type-Options: nosniff` · `X-Frame-Options: DENY` · `Referrer-Policy: same-origin` · `Permissions-Policy` (camera/mic/geo off) · CSP with `default-src 'self'` and `frame-ancestors 'none'` | `@app.after_request` in `app.py` — edit if you need to allow embedding |
| **P2.3 Rate limit (writes)** | 60 POST/PUT/DELETE per minute per (IP, route). Returns 429 with a JSON error | hard-coded; see `_RATE_LIMITS` dict in `app.py` |
| **P2.3 Rate limit (auth)** | 10 failed authentications per minute per IP — fires only when `HUB_PASSWORD` env var is set | activates automatically once password configured |
| **P2.4 Body size cap** | Reject request bodies > 10 MB (returns 413). Covers config import + bulk paste comfortably | `HUB_MAX_BODY_MB` env var (integer MB) |

### P2.1 HTTPS — needed before LAN/internet exposure

Hub's built-in server is HTTP only on `127.0.0.1`. For HTTPS / public
exposure, terminate TLS at a reverse proxy:

**Caddy (recommended — automatic Let's Encrypt or self-signed)**

```bash
# 1. Install Caddy: https://caddyserver.com/docs/install
# 2. Copy Caddyfile + replace the placeholder domain
cp scripts/Caddyfile.example /etc/caddy/Caddyfile
# 3. Hub stays on localhost only:
python scripts/serve_prod.py --host 127.0.0.1 --port 8080
# 4. Caddy handles HTTPS + redirects HTTP → HTTPS:
sudo systemctl restart caddy
```

For LAN-only without DNS, uncomment the `hub.local` block at the bottom
of `Caddyfile.example` — `tls internal` issues a Caddy-CA cert that you
trust on each client once.

**nginx (existing infra)**

`scripts/nginx.conf.example` shows the equivalent setup — `proxy_pass
http://127.0.0.1:8080` with `proxy_buffering off` for the SSE endpoints.
Provide your own cert via `ssl_certificate` / `ssl_certificate_key`.

**Behind a reverse proxy?** Hub already honors `X-Forwarded-For` for
audit logs and rate limiting (`_client_ip()`), so the IP-based bucket
tracks real clients instead of `127.0.0.1`.

### Enable BasicAuth (multi-user / shared deployment)

```bash
# systemd
sudo systemctl edit f180-hub
# add: Environment="HUB_USERNAME=admin" "HUB_PASSWORD=<strong>"

# NSSM (Windows)
nssm set QAHubDemo AppEnvironmentExtra "HUB_USERNAME=admin" "HUB_PASSWORD=<strong>"
nssm restart QAHubDemo
```

Once `HUB_PASSWORD` is set, the auth-fail rate limit also activates
automatically.

## Bundle size watch

Current build (Phase 3 complete):
- JS: ~183 KB raw, ~64 KB gzipped
- CSS: ~24 KB raw, ~5 KB gzipped

CI's `vue-build` job verifies `static/dist/index.html` exists. To add a
size-budget check, append to `.github/workflows/tests.yml`:

```yaml
- name: Bundle size guard
  working-directory: frontend
  run: |
    JS_SIZE=$(stat -c%s ../static/dist/assets/index-*.js)
    if [ "$JS_SIZE" -gt 524288 ]; then
      echo "JS bundle exceeds 512 KB ($JS_SIZE bytes)"
      exit 1
    fi
```

## Dev workflow (HMR)

```bash
# Terminal 1 — backend
python app.py

# Terminal 2 — frontend dev server
cd frontend
npm run dev               # http://localhost:5173 with hot reload
```

Vite proxies `/api/*` to `http://localhost:8080`, so the dev server
talks to the real Flask backend. No double-running of Hub needed.

## Production deployment checklist

Before the first non-developer uses v2:

- [ ] `cd frontend && npm ci && npm run build` ran without warnings
- [ ] `static/dist/index.html` exists and references hashed JS/CSS
- [ ] Visit `/v2/` — sidebar renders, no console errors
- [ ] Walk every route once: dashboard, overview, pipeline, release,
      schedule, projects, bugs, activity, input, output, screenshots,
      syscheck, guide, settings (14 routes)
- [ ] Settings → Branding loads current config and saves
- [ ] Pipeline → Run a benign stage (e.g. status refresh) — SSE log streams
- [ ] Schedule → toggle one schedule on/off — state persists
- [ ] Bug Tracker → add → edit → delete cycle works
- [ ] e2e tests green: `pytest -m e2e`
- [ ] CI green for last commit (both pytest + vue-build jobs)

## Switching the default route to v2

When v2 is proven stable and you want `http://localhost:8080/` to land
on v2:

1. In `app.py`, change the `@app.route("/")` handler to:
   ```python
   from flask import redirect
   @app.route("/")
   def index():
       return redirect("/v2/", code=302)
   ```
2. Move `templates/dashboard.html` to `templates/legacy/dashboard.html`
   and add a `/legacy` route that serves it (so it stays accessible
   for one release cycle).
3. Update `ONBOARDING.md` and `CLAUDE.md` architecture diagram.
4. Announce the change in audit log:
   ```bash
   curl -X POST http://localhost:8080/api/run/log -d '...'  # or just commit message
   ```

## Sunsetting legacy

Only after 30 days of v2-only operation with no bugs filed against it:

- [ ] Delete `templates/dashboard.html`
- [ ] Delete `static/app.js`
- [ ] Delete `static/app.css`
- [ ] Remove the `/legacy` redirect route
- [ ] Update CLAUDE.md to remove all references to vanilla layer
- [ ] Move `frontend/` contents to repo root if desired (since there's
      no longer a "legacy" to coexist with — it's just "the frontend")

## Rolling back

If v2 has a critical bug in production:

1. **Quick mitigation**: comment out the `/v2/` route in `app.py`,
   restart Hub. Users automatically lose access to v2 and stay on
   legacy `/`. No data loss — both UIs share `config.json` and the
   localStorage `fp_project` key.
2. **Code-level rollback**: `git revert <commit-range>` of the v2
   commits, redeploy.
3. **Full rollback**: `rm -rf frontend/ static/dist/` and redeploy.
   No backend code changes were required for v2, so the legacy UI
   keeps working unchanged.

## Monitoring

`logs/hub.log` captures backend errors regardless of which UI made
the request. The Activity Feed (`/v2/activity` or `logs/audit.jsonl`
directly) shows mutations. For UI-specific errors, the browser
console is the source of truth — consider adding Sentry / GlitchTip
if v2 starts seeing real user traffic.

## Performance budgets (current)

| Metric | Target | Current |
|---|---|---|
| Initial JS (gzipped) | < 100 KB | ~64 KB ✓ |
| Initial CSS (gzipped) | < 20 KB | ~5 KB ✓ |
| Cold load (LAN) | < 1.5 s | ~0.8 s ✓ |
| Time to interactive | < 2 s | ~1.2 s ✓ |

If JS exceeds the target, lazy-load routes:

```typescript
// router/index.ts — replace static imports with dynamic
{ path: '/pipeline', component: () => import('@/views/PipelineView.vue') }
```
