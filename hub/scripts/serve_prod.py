"""Production entrypoint — runs Hub under waitress (a production WSGI server).

Why not `python app.py`?
    Flask's built-in server is dev-only: single-threaded friendliness, no
    graceful shutdown, no production hardening. waitress is pure-Python,
    Windows/Linux compatible, and handles concurrent requests properly.

Usage:
    python scripts/serve_prod.py                       # defaults: 127.0.0.1:8080
    python scripts/serve_prod.py --host 0.0.0.0        # listen on all interfaces
    python scripts/serve_prod.py --port 9000
    python scripts/serve_prod.py --threads 8

Run as a service (Windows, recommended):
    nssm install QAHubDemo "C:\\Python3xx\\python.exe" "scripts\\serve_prod.py"
    nssm set QAHubDemo AppDirectory "C:\\Automation\\qa-hub-saucedemo"
    nssm start QAHubDemo

Run as a service (Linux):
    See scripts/f180-hub.service (systemd unit file).
"""
import argparse
import os
import sys
from pathlib import Path

# Ensure the hub root is importable when run from anywhere
HUB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HUB_ROOT))

from waitress import serve
import app as hub_app


# Hosts that only loop back to the local machine — safe even without auth.
# Anything else (LAN IP, hostname, 0.0.0.0) is public-ish and must be
# protected by HUB_PASSWORD.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _exposure_warning(host: str) -> None:
    """If we're listening on a non-loopback host without HUB_PASSWORD,
    print a loud warning. Doesn't refuse to start — operator may be
    behind a reverse proxy with its own auth. But surfaces the risk
    in BIG letters so an accidental `--host 0.0.0.0` for testing
    doesn't quietly expose every API."""
    if host in _LOOPBACK_HOSTS:
        return
    if os.environ.get("HUB_PASSWORD"):
        return
    bar = "!" * 64
    print(bar)
    print(f"  ⚠  DANGER: binding to non-loopback host '{host}'")
    print( "  ⚠  but HUB_PASSWORD env var is NOT set — APIs are WIDE OPEN.")
    print( "  ⚠  Anyone reachable on this network can run pipelines, sync")
    print( "  ⚠  projects, modify config, exfiltrate test data, etc.")
    print( "  ⚠  Set HUB_PASSWORD before exposure: see docs/AUTH_SETUP.md")
    print( "  ⚠  (this warning prints but does NOT block startup —")
    print( "  ⚠   acceptable when behind a reverse proxy that auths)")
    print(bar)


def main() -> None:
    p = argparse.ArgumentParser(description="QA Hub Demo production server")
    p.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8080, help="port (default: 8080)")
    p.add_argument("--threads", type=int, default=4, help="worker threads (default: 4)")
    args = p.parse_args()

    # Run the safety check BEFORE the welcome banner so it isn't lost in
    # service-manager output that often only shows the last N lines.
    _exposure_warning(args.host)

    print("=" * 58)
    print("  QA Hub Demo — production server (waitress)")
    print(f"  Listening on http://{args.host}:{args.port}  · {args.threads} threads")
    print(f"  Root:   {hub_app.ROOT_DIR}")
    print(f"  Config: {hub_app.CONFIG_FILE}")
    print("  Ctrl+C to stop  (or use your service manager)")
    print("=" * 58)

    serve(
        hub_app.app,
        host=args.host,
        port=args.port,
        threads=args.threads,
        # ident removes the 'waitress' Server header for a bit less fingerprinting
        ident=None,
    )


if __name__ == "__main__":
    main()
