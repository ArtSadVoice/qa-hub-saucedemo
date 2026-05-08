#!/usr/bin/env bash
# Install F180 Hub as a systemd service (Linux) — P1.1 Sprint F.
#
# Usage:
#   sudo ./scripts/install-service.sh
#
# What it does:
#   1. Verifies systemd is the init system
#   2. Creates the service user (f180hub) if missing
#   3. Copies scripts/f180-hub.service → /etc/systemd/system/
#   4. systemctl daemon-reload + enable + start
#   5. Prints the status command + log paths
#
# Idempotent — re-running just refreshes the unit and restarts.

set -euo pipefail

HUB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$HUB_DIR/scripts/f180-hub.service"
UNIT_DST="/etc/systemd/system/f180-hub.service"
SERVICE_USER="f180hub"
LOG_DIR="/var/log/f180-hub"

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR: must run as root (try: sudo $0)"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "ERROR: systemctl not found — this script supports systemd only."
  echo "       For other init systems, run scripts/serve_prod.py via your"
  echo "       process manager directly (see PRODUCTION.md)."
  exit 1
fi

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "ERROR: $UNIT_SRC not found"
  exit 1
fi

# Step 1: service user
if ! id "$SERVICE_USER" &>/dev/null; then
  echo "→ Creating system user $SERVICE_USER"
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
else
  echo "✓ Service user $SERVICE_USER already exists"
fi

# Step 2: log dir owned by service user
mkdir -p "$LOG_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"

# Step 3: hub dir readable by service user (don't chown — keep your edits)
chgrp "$SERVICE_USER" "$HUB_DIR"
chmod g+rx "$HUB_DIR"

# Step 4: install unit
cp "$UNIT_SRC" "$UNIT_DST"

# Patch WorkingDirectory if hub is somewhere other than /opt/feedback180-hub
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$HUB_DIR|" "$UNIT_DST"

systemctl daemon-reload
systemctl enable f180-hub
systemctl restart f180-hub

echo
echo "✓ Installed as systemd service"
echo "  Status:   sudo systemctl status f180-hub"
echo "  Logs:     sudo journalctl -u f180-hub -f"
echo "  Stop:     sudo systemctl stop f180-hub"
echo "  Disable:  sudo systemctl disable f180-hub"
echo
echo "Hub should be reachable at http://127.0.0.1:8080 within ~5 seconds."
