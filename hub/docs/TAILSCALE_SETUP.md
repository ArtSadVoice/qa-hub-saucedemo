# Hub Remote Access via Tailscale — Operator Runbook

> **Why Tailscale**: Tailscale exposes the hub to authenticated devices
> over a private mesh VPN — no public DNS, no inbound firewall holes,
> no domain ownership required. Sister doc to `AUTH_SETUP.md`: that one
> covers BasicAuth (defense in depth); this one covers how the hub
> reaches teammates' devices in the first place.
>
> **Alternative considered**: Cloudflare Tunnel + Access. We tried it
> first and hit a cross-account routing limitation when the `qahub.com`
> DNS zone lived in a different Cloudflare account than the tunnel.
> See "Why we picked Tailscale here" at the bottom — that section also
> documents when CF Tunnel is the right call.

## TL;DR — three steps

```
1. Server side: install Tailscale on the hub machine, log in, note the
   tailnet IP (e.g. 100.114.52.59).
2. Server side: change the QAHubDemo NSSM AppParameters to bind 0.0.0.0
   so connections from tailnet peers can reach the listener (HUB_PASSWORD
   stays as the second auth layer — see AUTH_SETUP.md).
3. Each teammate: install Tailscale on their device, log into the SAME
   tailnet account, open http://<tailnet-ip>:8080/ in any browser →
   BasicAuth dialog → enter hub credentials → done.
```

`HUB_PASSWORD` MUST be set first (see `AUTH_SETUP.md`). Tailscale gates
who can REACH the hub; BasicAuth gates what they can DO once reached.
Either alone is incomplete.

---

## Server side (one time on the hub machine)

### 1. Install Tailscale

```powershell
# Run as Administrator
winget install tailscale.tailscale
```

After install, **close and reopen PowerShell** to pick up the new PATH.

### 2. Log in

```powershell
# Doesn't need admin
tailscale up
```

A browser opens — log in with the email that should "own" the tailnet
(it can invite teammates later). For QA Hub Demo use the company email
(`fb.cnx@qahub.com` or similar) so the tailnet survives any one
person's departure.

### 3. Verify and note the tailnet IP

```powershell
tailscale ip -4         # e.g. 100.114.52.59 — write this down
tailscale status        # lists every device in the tailnet
```

The IP is stable per device — won't change unless you remove the device
from the admin console.

### 4. Bind the hub listener to 0.0.0.0

By default `serve_prod.py` listens only on `127.0.0.1` (loopback) — even
with Tailscale running, peers cannot reach the hub from another device
because the inbound packet arrives on the tailnet interface, not the
loopback interface.

The hub runs as a Windows service via NSSM. Update its parameters:

```powershell
# Run as Administrator
nssm stop QAHubDemo
nssm set QAHubDemo AppParameters "C:\Automation\qa-hub-saucedemo\scripts\serve_prod.py --host 0.0.0.0"
nssm get QAHubDemo AppParameters       # verify the new value
nssm start QAHubDemo
```

Confirm the change took effect:

```powershell
netstat -ano | findstr ":8080"
# Expected: TCP    0.0.0.0:8080    0.0.0.0:0    LISTENING    <pid>
# (NOT: TCP   127.0.0.1:8080  ...)
```

### 5. Test from the same machine via the tailnet IP

```powershell
curl.exe -i http://100.114.52.59:8080/api/projects
# Expected: HTTP/1.1 401 UNAUTHORIZED + Www-Authenticate header
```

If you get 401 → tailnet routing works AND BasicAuth is gating. ✅

```powershell
curl.exe -u hub:<HUB_PASSWORD> http://100.114.52.59:8080/api/projects
# Expected: JSON array of registered projects
```

> ℹ The exposure-warning banner in `serve_prod.py` (added in PR #26) will
> NOT fire here, because `HUB_PASSWORD` is set as `AppEnvironmentExtra`
> in NSSM. The warning is for "non-loopback bind WITHOUT auth", not for
> non-loopback bind in general.

---

## Client side (each teammate, per device)

### Install

| Platform | Command |
|---|---|
| Windows | `winget install tailscale.tailscale` |
| macOS | `brew install --cask tailscale` |
| Linux | follow [tailscale.com/download/linux](https://tailscale.com/download/linux) |
| iOS | App Store → "Tailscale" |
| Android | Play Store → "Tailscale" |

### Join the tailnet

- Open Tailscale → **Sign in** → use the SAME identity provider as the
  tailnet owner (e.g. log into Google with the same workspace, or use
  Microsoft / GitHub depending on what the owner picked)
- Toggle Tailscale **ON**

### Use the hub

- Open any browser → `http://<tailnet-ip>:8080/`
- BasicAuth dialog appears → enter hub credentials
- Hub loads — same UI as if you were on the host machine

If the dialog never appears, the device probably isn't joined to the
tailnet yet — check `tailscale status` (CLI) or the menu bar app.

---

## Optional: MagicDNS for nicer URLs

By default you have to remember `100.114.52.59`. MagicDNS lets you
use the machine's hostname instead:

1. [login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns) → enable **MagicDNS**
2. Optionally set a global nameserver (e.g. `1.1.1.1` or `8.8.8.8`) so DNS resolution outside the tailnet still works
3. (Optional) Rename the hub machine for a friendlier URL:
   - Tailscale admin console → **Machines** → click the hub machine → Edit name → e.g. `f180-hub`
4. Now any tailnet peer can use: `http://f180-hub:8080/`

MagicDNS resolves only on devices that have Tailscale ON — falls back
gracefully if Tailscale is off.

---

## Verification checklist

After server-side setup, before sharing URLs with the team:

- [ ] `tailscale status` on the hub machine shows the device as online
- [ ] `netstat -ano | findstr ":8080"` shows `0.0.0.0:8080 LISTENING`
- [ ] `curl.exe -i http://<tailnet-ip>:8080/api/projects` returns `401`
      (NOT connection refused — refused means bind didn't change)
- [ ] `curl.exe -u hub:<pw> http://<tailnet-ip>:8080/api/projects` returns `200` with JSON
- [ ] On a SECOND device joined to the tailnet, browser at the same URL
      gets the BasicAuth dialog (NOT a connection error)
- [ ] Disable Tailscale on the second device → URL becomes unreachable
      (proves it really IS gated by tailnet membership, not just open
      to the LAN)

If all six pass: production-ready for team use.

---

## Adding / removing teammates

### Add a teammate

1. **Tailscale admin console** → **Settings → Users → Invite users**
2. Send invite to their work email
3. They follow the install + sign-in flow above
4. Their device appears in your **Machines** list — by default they can
   only reach machines you allow via ACL (default ACL allows all-to-all
   within the tailnet, which is fine for a small team)

### Remove a teammate

1. **Settings → Users** → click the user → **Remove**
2. Their devices are revoked from the tailnet immediately
3. (No need to rotate `HUB_PASSWORD` if Tailscale was their only access
    path — they can't reach the listener anymore. Rotate anyway if
    you suspect they could have copied the password elsewhere.)

### Audit who's reaching the hub

- **Tailscale admin console** → **Machines** → see who's online + when
  they last connected
- **Logs** tab shows all auth events
- Per-request audit lives in the hub's own logs (`hub.log` —
  rotation already configured per `app.py` `RotatingFileHandler`)

---

## Free tier limits (Personal plan)

- **100 devices** total in the tailnet
- **3 users** (each user can have multiple devices — phone + laptop = 1 user)
- Need more users → upgrade plan ($6/user/month for "Premium" or check
  current pricing on tailscale.com)

For QA Hub Demo-internal use, 3 users is tight; consider the **Custom**
plan or move to **Cloudflare Tunnel + Access** if the team needs to
grow beyond ~3-5 active people.

---

## Why we picked Tailscale here

Decision matrix as of 2026-05-05 setup:

| Option | Why we ruled it out / chose it |
|---|---|
| **Cloudflare Tunnel + Access** | Tried first. Blocked because `qahub.com` DNS zone lives in a Cloudflare account we don't control (Account A) — and tunnel routing requires the public-hostname binding to live in the same account as the tunnel itself. Workarounds (Account A owner sends install token, or invites us as a Member) require coordination we don't currently have. |
| **Buy own domain + CF Tunnel** | Viable ($10/yr) but adds infrastructure + ongoing renewal. Worth revisiting if external customers ever need access. |
| **WireGuard self-hosted** | Adds VPS cost + maintenance burden for a single-operator project. |
| **Port forward + DDNS** | Public exposure with no second auth layer; ruled out for security. |
| **Tailscale** ✅ | No DNS / domain dependency, no Cloudflare account coordination, no public exposure. Free tier covers solo + 2 teammates. Setup time 10 minutes total. |

**When to revisit CF Tunnel**: external customers (non-employees) need
access — Tailscale requires installing an agent which doesn't scale to
"send a customer a link." If that need arises, see git history for the
2026-05-05 attempt — most of the troubleshooting is captured in the
`docs/production-auth-runbook` PR thread + memory files.

---

## Recovery / cleanup

### Tailscale stops working
- `tailscale status` to diagnose — usually a reauth needed
- Reauth: `tailscale up --force-reauth` → browser opens for fresh login

### Reverting to localhost-only (e.g. for a security incident)
```powershell
# Run as Administrator
nssm stop QAHubDemo
nssm set QAHubDemo AppParameters "C:\Automation\qa-hub-saucedemo\scripts\serve_prod.py"
nssm start QAHubDemo
# Hub is now reachable ONLY on 127.0.0.1:8080 again — no remote access
```

### Uninstall Tailscale entirely
```powershell
# Run as Administrator
tailscale down
winget uninstall tailscale.tailscale
# Plus revert QAHubDemo AppParameters per "Reverting to localhost-only" above
```
