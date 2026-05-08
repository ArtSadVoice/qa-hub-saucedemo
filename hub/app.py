"""
app.py — QA Hub Demo: Central Multi-Project Dashboard
รัน 1 ครั้ง ใช้กับทุก project ใน C:\\Automation\\

Usage:
    python _hub/app.py
    # Browser เปิดที่ http://localhost:8080

Dependencies:
    pip install flask openpyxl
"""
import sys, io, os, re, json, shutil, threading, time, subprocess, atexit, signal, zipfile, logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Only redirect stdout when run as script (preserves pytest capture when imported for tests)
if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from flask import Flask, Response, jsonify, request, send_file, stream_with_context
from release_gate import compute_release_gate
from migrations import migrate_config, migrate_history, migrate_schedules
from validators import validate_config
from schemas import validate_body
from audit import audit
from notifications import notify as _notify_webhooks
from flakiness import analyse as _analyse_flakiness

# ── Hub paths ──────────────────────────────────────────────────────────────────
HUB_DIR     = Path(__file__).resolve().parent   # C:\Automation\_hub
ROOT_DIR    = HUB_DIR.parent                    # C:\Automation
CONFIG_FILE = HUB_DIR / "config.json"
PID_FILE    = HUB_DIR / ".server.pid"
LOG_DIR     = HUB_DIR / "logs"

# ── Logging: rotating file + console ───────────────────────────────────────────
# Every module can do `logging.getLogger(__name__)` or `logging.info(...)` and
# it lands here. File rotates at 10 MB, keeps 5 backups (= 50 MB ceiling).
LOG_DIR.mkdir(exist_ok=True)
_log_fmt = logging.Formatter("%(asctime)s  %(levelname)-5s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_file_handler = RotatingFileHandler(LOG_DIR / "hub.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
_file_handler.setFormatter(_log_fmt)
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_fmt)
_console_handler.setLevel(logging.WARNING)  # console shows warnings+errors; file captures everything at INFO+
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
logger = logging.getLogger("hub")

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Reload Jinja templates on disk change. Cheap on a single-process dev box,
# saves a hub restart whenever dashboard.html is edited. Set HUB_TEMPLATE_CACHE=1
# to disable in production-style deployments where the file never changes.
if os.environ.get("HUB_TEMPLATE_CACHE", "0") != "1":
    app.config["TEMPLATES_AUTO_RELOAD"] = True

# ── P2.4 — request size cap ────────────────────────────────────────────────
# Reject JSON / multipart bodies bigger than 10 MB so a misbehaving client
# can't exhaust memory by streaming an arbitrary payload. 10 MB comfortably
# covers our largest legit POST (config import + bulk-paste recipients).
# Flask responds with 413 automatically when the body exceeds this.
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("HUB_MAX_BODY_MB", "10")) * 1024 * 1024

# Module-load timestamp — used by /api/hub/health to compute uptime.
HUB_STARTED_AT = datetime.now()

# ── P2.3 — lightweight in-process rate limiter ─────────────────────────────
# Goals: prevent BasicAuth brute force + bound write-endpoint abuse without
# adding flask-limiter (a Redis-shaped dependency for our single-process
# deployment).
#
# Rules:
#   • POST/PUT/DELETE: 60 req/min per (ip, route).  Generous enough that
#     a real user clicking around won't hit it; tight enough that a script
#     hammering /api/bugs/add gets 429'd within seconds.
#   • Failed auth (any 401): 10/min per ip across all routes.  Slows
#     password guessing without locking out a typo'd user too aggressively.
# Buckets are per (ip, key) → list of timestamps in the trailing window.
# The window is rolled lazily on each check; no background thread.
_RATE_LOCK = threading.Lock()
_rate_buckets: dict = {}      # (ip, key) → list[float]
_RATE_LIMITS = {
    # key                     window_s, max_hits
    "write":                  (60.0,    60),
    "auth_fail":              (60.0,    10),
}


def _rate_check(ip: str, bucket_key: str) -> bool:
    """Return True if the request is within budget; False to reject with 429.
    Side-effect: appends now() to the bucket on a hit."""
    window, limit = _RATE_LIMITS[bucket_key]
    now = time.time()
    cutoff = now - window
    key = (ip or "-", bucket_key)
    with _RATE_LOCK:
        bucket = _rate_buckets.get(key, [])
        # Drop expired timestamps
        bucket = [t for t in bucket if t >= cutoff]
        if len(bucket) >= limit:
            _rate_buckets[key] = bucket
            return False
        bucket.append(now)
        _rate_buckets[key] = bucket
        return True

# ── Background worker plumbing ────────────────────────────────────────────
# Two daily workers, started at module load:
#   • config-backup   — copy config.json into config_backups/ once per day
#   • audit-archive   — call archive_old_entries() once per day
# Both stop on process exit via atexit; both check the stop event every
# minute so a Ctrl+C is responsive instead of hanging on a 24h sleep.
CONFIG_BACKUP_DIR    = HUB_DIR / "config_backups"
CONFIG_BACKUP_KEEP   = int(os.environ.get("HUB_CONFIG_BACKUP_KEEP_DAYS", "30"))
_bg_stop_event       = threading.Event()


def _config_backup_loop():
    """Daily auto-backup of config.json with rolling N-day retention."""
    CONFIG_BACKUP_DIR.mkdir(exist_ok=True)
    while not _bg_stop_event.is_set():
        try:
            if CONFIG_FILE.exists():
                today  = datetime.now().strftime("%Y%m%d")
                target = CONFIG_BACKUP_DIR / f"config_{today}.json"
                if not target.exists():            # one snapshot per day
                    shutil.copy2(CONFIG_FILE, target)
                    logger.info("config backup: %s", target.name)
                # Prune older than CONFIG_BACKUP_KEEP days
                cutoff = time.time() - CONFIG_BACKUP_KEEP * 86400
                for f in CONFIG_BACKUP_DIR.glob("config_*.json"):
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
        except Exception as e:
            logger.warning("config-backup loop error: %s", e)
        # 24h wait, but wake every minute to honor Ctrl+C / atexit
        for _ in range(24 * 60):
            if _bg_stop_event.wait(60):
                return


def _audit_archive_loop():
    """Daily call to archive_old_entries() — moves audit.jsonl entries older
    than HUB_AUDIT_RETENTION_DAYS into per-month archives."""
    while not _bg_stop_event.is_set():
        try:
            from audit import archive_old_entries
            result = archive_old_entries()
            if result.get("archived", 0) > 0:
                logger.info("audit retention: archived %d entries", result["archived"])
        except Exception as e:
            logger.warning("audit-archive loop error: %s", e)
        for _ in range(24 * 60):
            if _bg_stop_event.wait(60):
                return


def _start_background_workers():
    """Idempotent — safe to call from tests / repeated module reloads."""
    if getattr(_start_background_workers, "_started", False):
        return
    _start_background_workers._started = True
    for name, fn in [("config-backup",  _config_backup_loop),
                     ("audit-archive",  _audit_archive_loop),
                     ("metrics-flush",  _metrics_flush_loop)]:
        threading.Thread(target=fn, daemon=True, name=name).start()
    atexit.register(lambda: _bg_stop_event.set())


# ── Lightweight request metrics ────────────────────────────────────────────
# Per-route counters + sliding window of recent latencies (ms).
# Sprint D shipped the in-memory layer; Sprint H added a SQLite ring buffer
# (HUB_DIR/metrics.db) so historical p95 / error rate survive Hub restarts.
# In-memory hot path is unchanged (every request still updates the dict so
# /api/metrics can answer in microseconds); SQLite is best-effort, written
# from a background flush thread to keep the request hot path lock-free.
import sqlite3

_METRICS_LOCK = threading.Lock()
_METRICS_WINDOW = 200          # keep last N latencies per route for p95
_METRICS_MAX_ROUTES = 100      # cap unique routes tracked to bound memory
_metrics_count: dict = {}      # route → int (lifetime requests)
_metrics_errors: dict = {}     # route → int (lifetime 5xx)
_metrics_latency: dict = {}    # route → list[float ms] (last _METRICS_WINDOW)

# SQLite ring buffer — one row per minute per route, holds the rolling
# count + p95 + max so historical view doesn't need to reconstruct from
# raw samples. HUB_METRICS_KEEP_HOURS env var (default 168 = 1 week)
# bounds disk usage.
METRICS_DB         = HUB_DIR / "metrics.db"
METRICS_KEEP_HOURS = int(os.environ.get("HUB_METRICS_KEEP_HOURS", "168"))
_metrics_pending: list = []     # [(ts, route, count, errors, p95, max_ms)] queued for the flush thread


def _metrics_db_init():
    """Idempotent — creates the ring-buffer table on first call."""
    with sqlite3.connect(METRICS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS request_minutes (
                ts        INTEGER NOT NULL,    -- unix epoch (minute granularity)
                route     TEXT    NOT NULL,
                count     INTEGER NOT NULL,
                errors    INTEGER NOT NULL,
                p95_ms    REAL    NOT NULL,
                max_ms    REAL    NOT NULL,
                PRIMARY KEY (ts, route)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_minutes_ts ON request_minutes(ts)")


def _metrics_record(route: str, ms: float, status_code: int):
    if not route or route.startswith("/static/"):
        return
    with _METRICS_LOCK:
        if route not in _metrics_count and len(_metrics_count) >= _METRICS_MAX_ROUTES:
            return  # bound memory — drop after first 100 unique routes
        _metrics_count[route] = _metrics_count.get(route, 0) + 1
        if status_code >= 500:
            _metrics_errors[route] = _metrics_errors.get(route, 0) + 1
        buf = _metrics_latency.setdefault(route, [])
        buf.append(ms)
        if len(buf) > _METRICS_WINDOW:
            del buf[0]


def _metrics_flush_loop():
    """Once a minute, snapshot the current rolling window per route into the
    SQLite ring buffer. Counts written here are the WINDOW count + max ms +
    p95 of that minute's window — enough to chart historical trend without
    persisting every individual latency sample."""
    _metrics_db_init()
    while not _bg_stop_event.is_set():
        try:
            now_min = int(time.time() // 60) * 60
            rows = []
            with _METRICS_LOCK:
                for route, samples in _metrics_latency.items():
                    if not samples:
                        continue
                    sorted_s = sorted(samples)
                    p95_idx = max(0, min(len(sorted_s) - 1, int(round(0.95 * (len(sorted_s) - 1)))))
                    rows.append((
                        now_min, route,
                        _metrics_count.get(route, 0),
                        _metrics_errors.get(route, 0),
                        round(sorted_s[p95_idx], 2),
                        round(max(samples), 2),
                    ))
            if rows:
                with sqlite3.connect(METRICS_DB) as conn:
                    conn.executemany(
                        "INSERT OR REPLACE INTO request_minutes "
                        "(ts, route, count, errors, p95_ms, max_ms) VALUES (?, ?, ?, ?, ?, ?)",
                        rows,
                    )
                    # Prune older than retention window
                    cutoff = int(time.time()) - METRICS_KEEP_HOURS * 3600
                    conn.execute("DELETE FROM request_minutes WHERE ts < ?", (cutoff,))
        except Exception as e:
            logger.warning("metrics-flush loop error: %s", e)
        # 60s cadence; wake every 10s for a responsive shutdown
        for _ in range(6):
            if _bg_stop_event.wait(10):
                return


def _metrics_history(hours: int = 24) -> list:
    """Read back the last N hours from the ring buffer. Returns rows in
    chronological order keyed by minute."""
    if not METRICS_DB.exists():
        return []
    cutoff = int(time.time()) - hours * 3600
    with sqlite3.connect(METRICS_DB) as conn:
        cur = conn.execute(
            "SELECT ts, route, count, errors, p95_ms, max_ms FROM request_minutes "
            "WHERE ts >= ? ORDER BY ts ASC",
            (cutoff,),
        )
        return [
            {"ts": r[0], "route": r[1], "count": r[2], "errors": r[3], "p95_ms": r[4], "max_ms": r[5]}
            for r in cur.fetchall()
        ]


# Don't start the workers when running under pytest — tests shouldn't kick
# off real disk I/O or rotate files. Production paths (python app.py,
# scripts/serve_prod.py) hit the start path normally.
# Placed below _metrics_flush_loop so all worker functions referenced by
# _start_background_workers are defined at call time.
if "PYTEST_CURRENT_TEST" not in os.environ and "pytest" not in sys.modules:
    _start_background_workers()


# ── Optional BasicAuth gate (enabled only when HUB_PASSWORD env var is set) ──
# Dev flow (single user, no env var): auth off → identical to pre-auth behaviour.
# Prod flow: set HUB_PASSWORD (and optionally HUB_USERNAME, default "hub") to
# require Basic auth on every non-static request.
HUB_PASSWORD = os.environ.get("HUB_PASSWORD", "")
HUB_USERNAME = os.environ.get("HUB_USERNAME", "hub")


def _auth_ok() -> bool:
    if not HUB_PASSWORD:
        return True
    h = request.headers.get("Authorization", "")
    if not h.startswith("Basic "):
        return False
    import base64
    try:
        decoded = base64.b64decode(h[6:]).decode("utf-8", errors="ignore")
        user, _, pw = decoded.partition(":")
        return user == HUB_USERNAME and pw == HUB_PASSWORD
    except Exception:
        return False


@app.before_request
def _start_request_timer():
    request._t_start = time.perf_counter()


# ── P2.3 — write-endpoint rate limit ──────────────────────────────────────
# Runs after auth (which is also a before_request hook registered earlier
# in the file) so 401s don't count against the write quota — they have
# their own auth_fail bucket below.
@app.before_request
def _rate_limit_writes():
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return None
    # Static assets + favicon can never be POSTed; the route filter below
    # also skips system endpoints to avoid locking out a recovery flow.
    if request.path.startswith("/static/") or request.path == "/favicon.ico":
        return None
    if not _rate_check(_client_ip(), "write"):
        return jsonify({
            "error":  "rate limit exceeded",
            "detail": "too many write requests — 60/min per IP per route",
        }), 429
    return None


def _client_ip() -> str:
    """Best-effort client IP. Honors X-Forwarded-For when behind a reverse
    proxy (Sprint G P2.1 deployment guide), falls back to remote_addr."""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "-"


# ── P2.2 — security response headers ──────────────────────────────────────
@app.after_request
def _add_security_headers(response):
    # X-Content-Type-Options: stop browsers sniffing a misdeclared content type
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    # X-Frame-Options: deny — Hub never embeds itself in an iframe and
    # nobody else should either (clickjacking guard for /v2/ + legacy /).
    response.headers.setdefault("X-Frame-Options", "DENY")
    # Referrer-Policy: same-origin so external links don't leak our path
    response.headers.setdefault("Referrer-Policy", "same-origin")
    # Permissions-Policy: disable browser features Hub doesn't use, so a
    # future XSS can't reach for camera/mic/geolocation
    response.headers.setdefault("Permissions-Policy",
                                "camera=(), microphone=(), geolocation=(), interest-cohort=()")
    # CSP: lenient enough that the existing inline event handlers + style="..."
    # in templates keep working ('unsafe-inline' for now), but blocks loading
    # arbitrary external scripts. Tighten in a future sprint when templates
    # migrate to event listeners + class bindings.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: blob: https:; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return response


@app.after_request
def _record_request_metric(response):
    start = getattr(request, "_t_start", None)
    if start is not None:
        elapsed_ms = (time.perf_counter() - start) * 1000
        # url_rule is the registered template (e.g. "/api/bugs"); falls back to
        # path which may include dynamic segments
        rule = request.url_rule.rule if request.url_rule else request.path
        _metrics_record(rule, elapsed_ms, response.status_code)
    return response


@app.before_request
def _require_auth():
    # Static assets + favicon bypass auth so the browser's auth dialog doesn't
    # re-trigger for every asset fetch.
    p = request.path
    if p == "/favicon.ico" or p.startswith("/static/"):
        return None
    if _auth_ok():
        return None
    # P2.3 — auth-fail rate limit: cap brute-force attempts to 10/min/ip.
    # Only enforced when auth is actually configured — otherwise a fresh
    # install would 429 on every page load.
    if os.environ.get("HUB_PASSWORD"):
        if not _rate_check(_client_ip(), "auth_fail"):
            return jsonify({
                "error":  "too many failed authentication attempts",
                "detail": "10/min/ip cap — wait a minute and retry",
            }), 429
    return Response(
        "authentication required",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="QA Hub Demo"'},
    )


# ── API error shape: all /api/* paths return {"error": str, "detail"?: str} ──
# Non-/api paths keep Flask's default HTML error pages for browser users.
def _wants_json_error() -> bool:
    return request.path.startswith("/api/")


@app.errorhandler(404)
def _api_not_found(e):
    if _wants_json_error():
        return jsonify({"error": "not found", "detail": request.path}), 404
    return e  # default HTML response for non-API paths


@app.errorhandler(405)
def _api_method_not_allowed(e):
    if _wants_json_error():
        return jsonify({"error": "method not allowed", "detail": f"{request.method} {request.path}"}), 405
    return e


@app.errorhandler(500)
def _api_server_error(e):
    if _wants_json_error():
        # Full traceback to hub.log for debugging; structured shape to caller.
        logger.exception("500 on %s %s", request.method, request.path)
        return jsonify({"error": "internal server error", "detail": str(e)}), 500
    return e


# ── Atomic file writers (prevent partial reads / corruption on crash or concurrent access) ──
def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text atomically: tempfile in same dir, then os.replace (atomic on POSIX + Windows)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{threading.get_ident()}")
    try:
        tmp.write_text(content, encoding=encoding)
        os.replace(tmp, path)
    except Exception:
        try: tmp.unlink()
        except Exception: pass
        raise

def _atomic_write_json(path: Path, data, indent: int = 2) -> None:
    """Write JSON atomically (wraps _atomic_write_text)."""
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=indent))


# ── Email secrets: env var takes precedence over config.json value ──
def _email_secret(env_key: str, cfg_value: str = "") -> str:
    """Prefer env var; fall back to config.json value. Used for SMTP password and Resend API key.
    Set HUB_SMTP_PASS / HUB_RESEND_API_KEY to avoid storing secrets in _hub/config.json."""
    env_val = os.environ.get(env_key, "")
    return env_val if env_val else (cfg_value or "")


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return migrate_config(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return migrate_config({"projects": []})


def save_config(cfg: dict):
    _atomic_write_json(CONFIG_FILE, cfg)


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else (ROOT_DIR / raw).resolve()


def _parse_claude_meta(project_path: Path) -> dict:
    """Read Company and Category from CLAUDE.md (first 2000 chars only)."""
    claude_md = project_path / "CLAUDE.md"
    if not claude_md.exists():
        return {"company": "", "category": ""}
    try:
        head = claude_md.read_text(encoding="utf-8", errors="ignore")[:2000]
        company  = re.search(r'\*\*Company\*\*\s*:\s*(.+)',  head)
        category = re.search(r'\*\*Category\*\*\s*:\s*(.+)', head)
        return {
            "company":  company.group(1).strip()  if company  else "",
            "category": category.group(1).strip() if category else "",
        }
    except Exception:
        return {"company": "", "category": ""}


def get_project(pid: str) -> dict | None:
    for p in load_config()["projects"]:
        if p["id"] == pid:
            return {**p, "abs_path": _resolve_path(p["path"])}
    return None


def get_paths(pid: str) -> dict | None:
    proj = get_project(pid)
    if not proj:
        return None
    b = proj["abs_path"]
    return {
        "proj": proj, "base": b,
        "scripts":      b / "scripts",
        "input":        b / "input",
        "output":       b / "output",
        "screenshots":  b / "screenshots",
        "logs":         b / "logs",
        "tests":        b / "tests" / "e2e",
        "requirements": b / "requirements",
        "figma":        b / "figma",
    }


def _req_paths():
    """Extract ?p= and return (paths, err_tuple_or_None)."""
    pid = request.args.get("p", "").strip()
    if not pid:
        return None, (jsonify({"error": "missing ?p=project_id"}), 400)
    paths = get_paths(pid)
    if not paths:
        return None, (jsonify({"error": f"project not found: {pid}"}), 404)
    return paths, None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def latest_xlsx(d: Path):
    if not d.exists():
        return None
    files = sorted(
        [f for f in d.glob("*.xlsx") if not f.name.startswith("~$")],
        key=lambda f: f.stat().st_mtime, reverse=True,
    )
    return files[0] if files else None


def latest_docx(d: Path):
    if not d.exists():
        return None
    files = sorted(
        [f for f in d.glob("*.docx")
         if "_backup_" not in f.name and "_bak_" not in f.name],
        key=lambda f: f.stat().st_mtime, reverse=True,
    )
    return files[0] if files else None


# ── Stage-completion detectors (per project) ─────────────────────────────
# s7 (Generate Report): docx มีอยู่
# s8 (Inject Screenshots): docx ไม่มี placeholder "[แนบ Screenshot/Evidence" หลงเหลือ
#     → generate_report.py ใส่ placeholder; screenshot_injector.py แทนด้วยรูป
# s9 (Download): user เคยเรียก /api/output/download ของ docx ปัจจุบันแล้ว
#     → marker file: <project_logs>/.last_download.json

def docx_has_screenshot_placeholders(docx_path: Path) -> bool:
    """อ่าน word/document.xml ใน docx zip — True ถ้ายังเจอ placeholder ที่ injector ต้องแทน."""
    try:
        with zipfile.ZipFile(str(docx_path)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        return "[แนบ Screenshot/Evidence" in xml
    except Exception:
        return True  # อ่านไม่ออก ถือว่ายังไม่ inject


def is_inject_done(docx_path) -> bool:
    if not docx_path or not Path(docx_path).exists():
        return False
    return not docx_has_screenshot_placeholders(Path(docx_path))


def _download_marker(logs_dir: Path) -> Path:
    return logs_dir / ".last_download.json"


def is_download_done(logs_dir: Path, docx_path) -> bool:
    """True เฉพาะเมื่อ user เคย download ไฟล์ที่ชื่อเดียวกัน *และไฟล์ยังไม่ถูก regenerate ทับ*."""
    if not docx_path:
        return False
    p = Path(docx_path)
    if not p.exists():
        return False
    marker = _download_marker(logs_dir)
    if not marker.exists():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return False
    if data.get("file") != p.name:
        return False
    # หาก docx ถูก regenerate ทับหลัง download → mtime ปัจจุบัน > mtime ตอน mark → ถือว่ายังไม่ได้ download ตัวใหม่
    try:
        marker_mtime = float(data.get("docx_mtime", 0))
    except (TypeError, ValueError):
        return False
    try:
        current_mtime = p.stat().st_mtime
    except OSError:
        return False
    return current_mtime <= marker_mtime + 0.5  # 0.5s tolerance สำหรับ FS timestamp resolution


def mark_download(logs_dir: Path, docx_path) -> None:
    """เรียกตอน /api/output/download — บันทึกว่า user ดาวน์โหลด docx ปัจจุบันแล้ว (per project)."""
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        p = Path(docx_path)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        _download_marker(logs_dir).write_text(
            json.dumps({
                "file": p.name,
                "docx_mtime": mtime,
                "ts": datetime.now().isoformat(),
            }),
            encoding="utf-8",
        )
    except Exception:
        pass


def read_excel_data(input_dir: Path) -> dict:
    try:
        import openpyxl
    except ImportError:
        return {}
    xlsx = latest_xlsx(input_dir)
    if not xlsx:
        return {}
    try:
        wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    except Exception:
        return {}

    info = {}
    if "PROJECT_INFO" in wb.sheetnames:
        for row in wb["PROJECT_INFO"].iter_rows(values_only=True):
            col_b = row[1] if len(row) > 1 else None
            col_c = row[2] if len(row) > 2 else None
            if col_b and str(col_b).strip().startswith("*"):
                key = str(col_b).strip().lstrip("* ").strip()
                info[key] = str(col_c) if col_c is not None else ""

    ALL = ["pass", "fail", "not start", "in-progress", "block", "cancel"]
    ts_data, ts_order, cur = {}, [], None

    if "TCM" in wb.sheetnames:
        for row in wb["TCM"].iter_rows(values_only=True):
            if not any(c is not None for c in row):
                continue
            if row[0] == "TSID":
                continue
            if row[0] in ("STATUS LEGEND", "Pass"):
                break
            if row[0] and re.match(r"^TS_\d+$", str(row[0])):
                cur = str(row[0])
                if cur not in ts_data:
                    ts_data[cur] = {"desc": str(row[1] or ""), "counts": {s: 0 for s in ALL}}
                    ts_order.append(cur)
            if cur and row[2]:
                s = str(row[9] or "").strip().lower()
                if s in ts_data[cur]["counts"]:
                    ts_data[cur]["counts"][s] += 1
    wb.close()

    totals = {s: 0 for s in ALL}
    total_tc = 0
    for tsid in ts_order:
        for s in ALL:
            totals[s] += ts_data[tsid]["counts"][s]
            total_tc += ts_data[tsid]["counts"][s]

    return {
        "project": info, "ts_order": ts_order, "ts_data": ts_data,
        "totals": totals, "total_tc": total_tc,
        "accuracy": round(totals["pass"] / total_tc * 100) if total_tc else 0,
        "input_file": xlsx.name,
    }


def _stream(script: Path, cwd: Path, extra: list = None, timeout: int = None):
    cmd = [sys.executable, "-X", "utf8", str(script)] + (extra or [])
    def gen():
        yield f"data: {json.dumps({'line': f'▶ {script.name}...', 'type': 'info'})}\n\n"
        proc = None
        try:
            proc = subprocess.Popen(
                cmd, cwd=str(cwd),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            # Fix 3: watchdog thread — kill process if no output for `timeout` seconds
            if timeout:
                import threading
                _timer = [None]
                def _kill():
                    if proc.poll() is None:
                        proc.kill()
                        yield_queue.append(
                            f"data: {json.dumps({'line': f'ERROR: Process timed out after {timeout}s — killed', 'type': 'err', 'done': True, 'returncode': -9})}\n\n"
                        )
                yield_queue = []
                def _reset():
                    if _timer[0]: _timer[0].cancel()
                    _timer[0] = threading.Timer(timeout, _kill)
                    _timer[0].start()
                _reset()

            for ln in proc.stdout:
                if timeout: _reset()
                ln = ln.rstrip()
                if not ln:
                    continue
                t = "ok" if ln.startswith("✓") else ("err" if "ERROR" in ln.upper() else "info")
                yield f"data: {json.dumps({'line': ln, 'type': t})}\n\n"

            if timeout and _timer[0]: _timer[0].cancel()
            for extra_ev in (yield_queue if timeout else []):
                yield extra_ev
            proc.wait()
            rc = proc.returncode
            yield f"data: {json.dumps({'line': f'Done (exit {rc})', 'type': 'ok' if rc == 0 else 'err', 'done': True, 'returncode': rc})}\n\n"
        except Exception as e:
            if proc and proc.poll() is None:
                proc.kill()
            yield f"data: {json.dumps({'line': str(e), 'type': 'err', 'done': True, 'returncode': -1})}\n\n"
    return gen


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

def sse(gen_fn):
    return Response(stream_with_context(gen_fn()), mimetype="text/event-stream", headers=SSE_HEADERS)


# ══════════════════════════════════════════════════════════════════════════════
# API — PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/preflight/<pid>")
def api_preflight(pid: str):
    """Per-project pre-pipeline gate: scan input/ for Excel locks and
    structurally validate the project's docx template. Cheap (~50ms),
    intended to be polled before kicking off "Run Pipeline" so the
    user sees actionable issues before the pipeline crashes mid-run.
    See scaffold_audit.preflight_project for result shape."""
    proj = get_project(pid)
    if not proj:
        return jsonify({"error": "project not found"}), 404
    from scaffold_audit import preflight_project
    return jsonify(preflight_project(proj["abs_path"]))


@app.route("/api/scaffold/drift/<pid>")
def api_scaffold_drift(pid: str):
    """Hash-compare a project's infrastructure files (preflight, hooks,
    template ...) against the canonical scaffold for its type. Surfaces
    drift so an operator can tell which projects are due for a sync.
    See scaffold_audit.audit_project_drift for result shape."""
    proj = get_project(pid)
    if not proj:
        return jsonify({"error": "project not found"}), 404
    from pathlib import Path as _P
    from scaffold_audit import audit_project_drift
    scaffold_root = _P(__file__).parent / "scaffold"
    project_type = proj.get("type", "full-pipeline")
    return jsonify(audit_project_drift(
        proj["abs_path"], scaffold_root, project_type
    ))


@app.route("/api/projects/validate-path")
def api_projects_validate_path():
    """Cheap pre-submit check for ProjectAddModal — tells the operator
    whether the supplied path is sane for the chosen mode BEFORE they hit
    submit and wait for a 5s subprocess to fail.

    Query params:
      path  — required, the candidate path
      mode  — 'register' | 'scaffold' | 'clone' (default 'register')

    Returns:
      {
        ok: bool,            # safe to proceed
        exists: bool,        # folder exists on disk
        is_dir: bool,        # if exists, is it a directory
        not_empty: bool,     # if exists, has content (matters for scaffold/clone)
        within_root: bool,   # under C:/Automation/ (the convention)
        registered: bool,    # already in config.json
        message: str         # human-readable hint, '' when ok
      }
    """
    from pathlib import Path as _P
    raw = (request.args.get("path") or "").strip()
    mode = (request.args.get("mode") or "register").strip()

    out = {
        "ok": False, "exists": False, "is_dir": False, "not_empty": False,
        "within_root": False, "registered": False, "message": "",
    }
    if not raw:
        out["message"] = "Path is empty"
        return jsonify(out)

    # Reject obvious traversal — we don't need to be ironclad (subprocess
    # also validates) but no point letting "../" reach the backend.
    if ".." in _P(raw).parts:
        out["message"] = "Path may not contain '..'"
        return jsonify(out)

    p = _P(raw)
    try:
        p_abs = p.resolve()
    except Exception as e:
        out["message"] = f"Invalid path: {e}"
        return jsonify(out)

    # Convention: projects live under C:/Automation/
    root = _P(r"C:/Automation").resolve()
    try:
        out["within_root"] = str(p_abs).lower().startswith(str(root).lower())
    except Exception:
        out["within_root"] = False

    out["exists"] = p_abs.exists()
    if out["exists"]:
        out["is_dir"] = p_abs.is_dir()
        if out["is_dir"]:
            try:
                out["not_empty"] = any(p_abs.iterdir())
            except Exception:
                out["not_empty"] = True  # be conservative

    # Already-registered check (path collision, regardless of mode)
    for proj in load_config().get("projects", []):
        if _resolve_path(proj["path"]).resolve() == p_abs:
            out["registered"] = True
            break

    # Mode-specific verdict
    if mode == "register":
        if out["registered"]:
            out["message"] = f"Already registered as '{[p['id'] for p in load_config()['projects'] if _resolve_path(p['path']).resolve() == p_abs][0]}'"
        elif not out["exists"]:
            out["message"] = "Folder does not exist — can't register"
        elif not out["is_dir"]:
            out["message"] = "Path is a file, not a folder"
        else:
            out["ok"] = True
            out["message"] = "Folder exists — ready to register"
    else:  # scaffold or clone
        if out["registered"]:
            out["message"] = "Path is already registered as another project"
        elif out["exists"] and out["not_empty"]:
            out["message"] = (
                f"Folder already exists and is not empty — {mode} would overwrite. "
                "Delete the folder first or pick a different path."
            )
        elif out["exists"] and not out["not_empty"]:
            out["ok"] = True
            out["message"] = "Folder exists but is empty — safe to populate"
        else:
            out["ok"] = True
            out["message"] = "Path will be created"

    if not out["within_root"] and out["ok"]:
        out["message"] += " (warning: outside C:/Automation/ — non-standard)"

    return jsonify(out)


@app.route("/api/scaffold/sync/<pid>", methods=["POST"])
def api_scaffold_sync(pid: str):
    """Run sync_to_project.py against a registered project to bring its
    infrastructure files (preflight helpers, hooks, validated template)
    in line with the canonical scaffold for its type. Returns the script's
    stdout/stderr verbatim so the dashboard can show the per-file plan."""
    proj = get_project(pid)
    if not proj:
        return jsonify({"error": "project not found"}), 404
    body = request.json or {}
    include_pipeline = bool(body.get("include_pipeline_scripts"))
    include_template = bool(body.get("include_template"))

    from pathlib import Path as _P
    import subprocess as _sp
    project_type = proj.get("type", "full-pipeline")
    scaffold_root = _P(__file__).parent / "scaffold"
    script = scaffold_root / project_type / "scripts" / "sync_to_project.py"
    fallback_used = ""
    if not script.exists():
        # Fallback: full-pipeline ships the canonical sync_to_project.py.
        # The script's logic is project-type-agnostic — its source dir is
        # determined by `Path(__file__).resolve().parent.parent`, so running
        # the full-pipeline copy still pulls files from full-pipeline/. To
        # actually sync a manual-testing project against manual-testing
        # files, that flavor needs its own copy of the script
        # (scaffold/manual-testing/scripts/sync_to_project.py). Until/if
        # both flavors carry the script, fall back to full-pipeline so the
        # API returns SOMETHING actionable instead of a hard 2.
        fp_script = scaffold_root / "full-pipeline" / "scripts" / "sync_to_project.py"
        if fp_script.exists():
            script = fp_script
            fallback_used = (
                f"WARNING: scaffold/{project_type}/scripts/sync_to_project.py "
                f"missing — falling back to scaffold/full-pipeline/. Files copied "
                f"will come from full-pipeline/, NOT from {project_type}/. "
                f"Add sync_to_project.py to scaffold/{project_type}/scripts/ "
                f"to sync flavor-specific files.\n"
            )
        else:
            return jsonify({
                "ok": False, "stdout": "", "returncode": 2,
                "stderr": f"sync_to_project.py missing for type {project_type!r} "
                          f"and the full-pipeline fallback is also missing "
                          f"(expected at {script} or {fp_script})",
            })

    cmd = [sys.executable, "-X", "utf8", str(script),
           str(proj["abs_path"]), "--apply"]
    if include_pipeline:
        cmd.append("--include-pipeline-scripts")
    if include_template:
        cmd.append("--include-template")

    try:
        r = _sp.run(cmd, capture_output=True, text=True,
                    cwd=str(_P(__file__).parent), timeout=60)
        # Invalidate the drift cache for this project so the next dashboard
        # poll shows the post-sync state instead of the stale pre-sync entry.
        if r.returncode == 0:
            from scaffold_audit import invalidate_drift_cache as _inv
            _inv(proj["abs_path"])
        return jsonify({
            "ok": r.returncode == 0,
            "stdout": r.stdout,
            "stderr": (fallback_used + r.stderr) if fallback_used else r.stderr,
            "returncode": r.returncode,
        })
    except _sp.TimeoutExpired:
        return jsonify({
            "ok": False, "stdout": "",
            "stderr": (fallback_used or "") + "sync timed out (>60s)",
            "returncode": -1,
        })


@app.route("/api/scaffold/drift")
def api_scaffold_drift_all():
    """Drift summary across every registered project. Returns one entry
    per project — same payload as /api/scaffold/drift/<pid>."""
    from pathlib import Path as _P
    from scaffold_audit import audit_project_drift
    scaffold_root = _P(__file__).parent / "scaffold"
    out = []
    for p in load_config().get("projects", []):
        abs_path = _resolve_path(p["path"])
        if not abs_path.exists():
            out.append({
                "id": p["id"], "name": p.get("name", p["id"]),
                "project_path": str(abs_path),
                "project_exists": False,
                "ok": False, "summary": {}, "files": [],
            })
            continue
        audit = audit_project_drift(abs_path, scaffold_root,
                                    p.get("type", "full-pipeline"))
        out.append({
            "id": p["id"], "name": p.get("name", p["id"]),
            "project_exists": True,
            **audit,
        })
    return jsonify(out)


@app.route("/api/projects")
def api_projects():
    result = []
    for p in load_config()["projects"]:
        path = _resolve_path(p["path"])
        meta = _parse_claude_meta(path)
        result.append({
            **p,
            "exists":           path.exists(),
            "has_xlsx":         latest_xlsx(path / "input") is not None,
            "has_docx":         latest_docx(path / "output") is not None,
            "screenshot_count": _count_screenshots(p),
            "last_run":         _last_run_time(p),
            "company":          p.get("company")  or meta["company"],
            "category":         p.get("category") or meta["category"],
        })
    return jsonify(result)


@app.route("/api/projects/add", methods=["POST"])
def api_projects_add():
    data = request.json or {}
    for k in ["id", "name", "path"]:
        if not data.get(k):
            return jsonify({"error": f"missing field: {k}"}), 400

    # Validate ID — alphanumeric + hyphens only
    if not re.match(r'^[a-zA-Z0-9_-]+$', data["id"]):
        return jsonify({"error": "ID ต้องเป็นตัวอักษร ตัวเลข - หรือ _ เท่านั้น"}), 400

    # Validate path stays within ROOT_DIR — prevent path traversal
    try:
        _resolve_path(data["path"]).relative_to(ROOT_DIR)
    except ValueError:
        return jsonify({"error": "Path ต้องอยู่ภายใต้ root directory เท่านั้น"}), 400

    cfg = load_config()
    if any(p["id"] == data["id"] for p in cfg["projects"]):
        return jsonify({"error": f"id already exists: {data['id']}"}), 400

    proj_type      = data.get("type", "full-pipeline")
    base_url       = (data.get("base_url") or "").strip()
    figma_url      = (data.get("figma_url") or "").strip()
    has_playwright = data.get("has_playwright", True)
    git_url        = (data.get("git_url") or "").strip()
    init_mode      = data.get("init_mode", "none")  # "scaffold" | "git" | "none"
    created_dirs   = []
    used_scaffold  = False
    used_git       = False

    PLAYWRIGHT_FILES = {"playwright.config.ts", "package.json"}
    PLAYWRIGHT_DIRS  = {"tests"}
    SUBST_FILES = {"playwright.config.ts", "constants.ts", "CLAUDE.md", ".env.example", "SurveyPage.ts"}

    def _apply_placeholders(root: Path):
        placeholders = {
            "{{PROJECT_NAME}}": data["name"],
            "{{BASE_URL}}":     base_url or "https://your-app.example.com",
            "{{FIGMA_URL}}":    figma_url or "",
        }
        for f in root.rglob("*"):
            if f.is_file() and f.name in SUBST_FILES:
                try:
                    content = f.read_text(encoding="utf-8")
                    for k, v in placeholders.items():
                        content = content.replace(k, v)
                    f.write_text(content, encoding="utf-8")
                except Exception:
                    pass

    def _remove_playwright(root: Path):
        for fname in PLAYWRIGHT_FILES:
            fp = root / fname
            if fp.exists():
                fp.unlink()
        for dname in PLAYWRIGHT_DIRS:
            dp = root / dname
            if dp.exists():
                shutil.rmtree(dp)

    if init_mode in ("scaffold", "git"):
        abs_path = _resolve_path(data["path"])
        try:
            abs_path.relative_to(ROOT_DIR)
        except ValueError:
            return jsonify({"error": "Path ต้องอยู่ภายใต้ root directory เท่านั้น"}), 400
        if abs_path.exists():
            return jsonify({"error": f"Path already exists: {abs_path}"}), 400

        try:
            if init_mode == "git":
                if not git_url:
                    return jsonify({"error": "กรุณาระบุ Git URL"}), 400
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", git_url, str(abs_path)],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    err = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "clone failed"
                    return jsonify({"error": f"git clone ไม่สำเร็จ: {err}"}), 500
                # Remove .git → project เริ่มใหม่สะอาด
                git_dir = abs_path / ".git"
                if git_dir.exists():
                    shutil.rmtree(git_dir)
                if not has_playwright:
                    _remove_playwright(abs_path)
                _apply_placeholders(abs_path)
                used_git = True

            else:  # scaffold
                scaffold = HUB_DIR / "scaffold" / proj_type
                if scaffold.exists():
                    shutil.copytree(str(scaffold), str(abs_path))
                    if not has_playwright:
                        _remove_playwright(abs_path)
                    _apply_placeholders(abs_path)
                    used_scaffold = True
                    created_dirs = ["(scaffold copied)"]
                else:
                    # Fallback: empty folders
                    abs_path.mkdir(parents=True, exist_ok=False)
                    subs = (["input", "output", "scripts", "tests", "screenshots", "templates", "logs", "archive"]
                           if proj_type in ("full-pipeline", "manual-testing")
                           else ["surveys", "core", "test-results"])
                    for sub in subs:
                        (abs_path / sub).mkdir()
                        created_dirs.append(sub)

        except subprocess.TimeoutExpired:
            if abs_path.exists():
                shutil.rmtree(abs_path)
            return jsonify({"error": "git clone timeout (120s) — ลอง repo ที่เล็กกว่า หรือเช็ค URL"}), 500
        except Exception as e:
            if abs_path.exists() and not abs_path.iterdir().__next__() if abs_path.exists() else False:
                shutil.rmtree(abs_path)
            return jsonify({"error": f"สร้าง folder ไม่ได้: {e}"}), 500

    entry = {
        "id":    data["id"],
        "name":  data["name"],
        "path":  data["path"],
        "type":  proj_type,
        "color": data.get("color", "#2E75B6"),
    }
    if figma_url:
        entry["figma_url"] = figma_url
    if data.get("company"):
        entry["company"] = data["company"].strip()
    if data.get("category"):
        entry["category"] = data["category"].strip()
    cfg["projects"].append(entry)
    save_config(cfg)
    audit("project.add", id=entry["id"], name=entry["name"], path=entry["path"], type=entry.get("type"))

    # Seed universal Claude memory for the new project so principles + user
    # role apply no matter where Claude is invoked from. Failure-safe —
    # memory-seed errors must not fail the project-add call.
    try:
        from scripts.init_project_memory import init_for_path  # lazy import
        init_for_path(_resolve_path(entry["path"]), overwrite=False)
    except Exception as e:
        logger.warning("memory seed skipped for new project %s: %s", entry["id"], e)
    return jsonify({
        "ok": True,
        "used_scaffold": used_scaffold,
        "used_git": used_git,
        "has_playwright": has_playwright,
        "created_dirs": created_dirs,
    })


@app.route("/api/projects/update", methods=["POST"])
@validate_body(
    required=["id"],
    allowed=["name", "color", "type", "phase", "figma_url", "company", "category"],
)
def api_projects_update(body):
    pid = body["id"]
    cfg = load_config()
    for p in cfg["projects"]:
        if p["id"] == pid:
            if "name"  in body: p["name"]  = body["name"]
            if "color" in body: p["color"] = body["color"]
            if "type"  in body: p["type"]  = body["type"]
            if "phase" in body: p["phase"] = body["phase"]
            # figma_url, company, category: empty string = remove key from config so
            # /api/projects responses don't carry stale empty fields.
            for opt_field in ("figma_url", "company", "category"):
                if opt_field in body:
                    val = (body[opt_field] or "").strip()
                    if val:
                        p[opt_field] = val
                    else:
                        p.pop(opt_field, None)
            save_config(cfg)
            audit("project.update", id=pid, changes={k: v for k, v in body.items() if k != "id"})
            return jsonify({"ok": True})
    return jsonify({"error": f"project not found: {pid}"}), 404


@app.route("/api/projects/remove", methods=["POST"])
def api_projects_remove():
    pid = (request.json or {}).get("id", "")
    if not pid:
        return jsonify({"error": "missing id"}), 400
    cfg = load_config()
    before = len(cfg["projects"])
    cfg["projects"] = [p for p in cfg["projects"] if p["id"] != pid]
    save_config(cfg)
    if len(cfg["projects"]) < before:
        audit("project.remove", id=pid)
    return jsonify({"ok": True})


@app.route("/api/summary")
def api_summary():
    """Aggregate stats across all registered projects."""
    rows = []
    for p in load_config()["projects"]:
        path = _resolve_path(p["path"])
        xlsx = latest_xlsx(path / "input")
        docx = latest_docx(path / "output")
        row = {
            "id": p["id"], "name": p["name"],
            "type":  p.get("type",  "full-pipeline"),
            "phase": p.get("phase", "active"),
            "color": p.get("color", "#2E75B6"), "exists": path.exists(),
            "company":  p.get("company")  or _parse_claude_meta(path)["company"],
            "category": p.get("category") or _parse_claude_meta(path)["category"],
            "has_xlsx": xlsx is not None, "has_docx": docx is not None,
            "screenshot_count": _count_screenshots(p),
            "last_run": _last_run_time(p),
            "total_tc": 0, "pass": 0, "fail": 0, "accuracy": None,
        }
        proj_type = p.get("type", "full-pipeline")
        if xlsx and proj_type in ("full-pipeline", "manual-testing"):
            d = read_excel_data(path / "input")
            row["total_tc"] = d.get("total_tc", 0)
            row["pass"]     = d.get("totals", {}).get("pass", 0)
            row["fail"]     = d.get("totals", {}).get("fail", 0)
            row["accuracy"] = d.get("accuracy")
        elif proj_type == "playwright-only":
            # Use last valid run from history
            hist = [e for e in _load_history()
                    if e.get("project_id") == p["id"]
                    and e.get("step") == "tests"
                    and (e.get("pass", 0) + e.get("fail", 0)) > 0]
            if hist:
                last = hist[-1]
                total = last["pass"] + last["fail"]
                row["pass"]     = last["pass"]
                row["fail"]     = last["fail"]
                row["total_tc"] = total
                row["accuracy"] = round(last["pass"] / total * 100) if total else None
        rows.append(row)
    return jsonify(rows)


@app.route("/api/config/branding")
def api_config_branding():
    cfg = load_config()
    b   = cfg.get("branding", {})
    return jsonify({
        "app_name":    b.get("app_name",    "QA Hub Demo"),
        "subtitle":    b.get("subtitle",    "Multi-Project Dashboard"),
        "logo":        b.get("logo",        "🔬"),
        "logo_url":    b.get("logo_url",    ""),
        "primary_color": b.get("primary_color", ""),
        "footer":      b.get("footer",      ""),
        "company":     b.get("company",     ""),
        "favicon":     b.get("favicon",     ""),
    })


@app.route("/api/config/branding/save", methods=["POST"])
def api_config_branding_save():
    data = request.get_json(force=True)
    cfg  = load_config()
    cfg["branding"] = {
        "app_name":      data.get("app_name",    "").strip() or "QA Hub Demo",
        "subtitle":      data.get("subtitle",    "").strip() or "Multi-Project Dashboard",
        "logo":          data.get("logo",        "").strip() or "🔬",
        "logo_url":      data.get("logo_url",    "").strip(),
        "primary_color": data.get("primary_color","").strip(),
        "footer":        data.get("footer",      "").strip(),
        "company":       data.get("company",     "").strip(),
        "favicon":       data.get("favicon",     "").strip(),
    }
    save_config(cfg)
    audit("config.branding.save", app_name=cfg["branding"].get("app_name"))
    return jsonify({"ok": True})


@app.route("/api/config/email")
def api_config_email():
    cfg = load_config()
    e   = cfg.get("email", {})
    return jsonify({
        "provider":      e.get("provider", "smtp"),
        "smtp_host":     e.get("smtp_host", "smtp.gmail.com"),
        "smtp_port":     e.get("smtp_port", 587),
        "smtp_user":     e.get("smtp_user", ""),
        "smtp_pass":     e.get("smtp_pass", ""),
        "resend_api_key": e.get("resend_api_key", ""),
        "resend_from":   e.get("resend_from", ""),
        "sender_name":   e.get("sender_name", "F180 QA Hub"),
        "to":            e.get("to", []),
        "cc":            e.get("cc", []),
        "subject_template": e.get("subject_template",
                             "[{result}] UAT Report — {project} | {date} | Pass Rate {pass_rate}%"),
    })


@app.route("/api/config/email/save", methods=["POST"])
def api_config_email_save():
    data = request.get_json(force=True)
    cfg  = load_config()
    cfg["email"] = {
        "provider":      (data.get("provider") or "smtp").strip(),
        "smtp_host":     (data.get("smtp_host") or "").strip() or "smtp.gmail.com",
        "smtp_port":     int(data.get("smtp_port") or 587),
        "smtp_user":     (data.get("smtp_user") or "").strip(),
        "smtp_pass":     (data.get("smtp_pass") or "").strip(),
        "resend_api_key": (data.get("resend_api_key") or "").strip(),
        "resend_from":   (data.get("resend_from") or "").strip(),
        "sender_name":   (data.get("sender_name") or "").strip() or "F180 QA Hub",
        "to":            data.get("to", []),
        "cc":            data.get("cc", []),
        "subject_template": (data.get("subject_template") or "").strip() or
                            "[{result}] UAT Report — {project} | {date} | Pass Rate {pass_rate}%",
    }
    save_config(cfg)
    _sync_email_to_projects(cfg["email"])
    # Never audit-log the password fields themselves
    audit("config.email.save",
          provider=cfg["email"]["provider"],
          smtp_host=cfg["email"]["smtp_host"],
          recipients=len(cfg["email"].get("to", [])) + len(cfg["email"].get("cc", [])))
    return jsonify({"ok": True})


@app.route("/api/config/email/test", methods=["POST"])
def api_config_email_test():
    data = request.get_json(force=True)
    provider = (data.get("provider") or "smtp").strip()

    if provider == "resend":
        cfg_key = load_config().get("email", {}).get("resend_api_key", "")
        api_key = (data.get("resend_api_key") or "").strip() or _email_secret("HUB_RESEND_API_KEY", cfg_key)
        if not api_key:
            return jsonify({"ok": False, "error": "กรุณากรอก Resend API Key (หรือ set HUB_RESEND_API_KEY env var)"}), 400
        try:
            import resend as _resend
            _resend.api_key = api_key
            domains = _resend.Domains.list()
            count = len(domains.data) if hasattr(domains, 'data') else 0
            return jsonify({"ok": True, "detail": f"Resend API OK — {count} domain(s)"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:200]}), 400
    else:
        host = (data.get("smtp_host") or "").strip()
        port = int(data.get("smtp_port") or 587)
        user = (data.get("smtp_user") or "").strip()
        # Password: prefer form value, else fall back to env var HUB_SMTP_PASS, else stored config
        cfg_pwd = load_config().get("email", {}).get("smtp_pass", "")
        pwd  = (data.get("smtp_pass") or "").strip() or _email_secret("HUB_SMTP_PASS", cfg_pwd)
        if not host or not user or not pwd:
            return jsonify({"ok": False, "error": "กรุณากรอก SMTP Host, Username และ Password (หรือ set HUB_SMTP_PASS env var)"}), 400
        try:
            import smtplib as _smtp
            server = _smtp.SMTP(host, port, timeout=10)
            server.starttls()
            server.login(user, pwd)
            server.quit()
            return jsonify({"ok": True, "detail": f"{host}:{port} — login OK"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:200]}), 400


def _sync_email_to_projects(email_cfg: dict):
    """Sync Hub email config to all registered project distribution.json files.
    Secrets (smtp_pass / resend_api_key) resolved via _email_secret — env var > config."""
    provider = email_cfg.get("provider", "smtp")
    smtp_block = {
        "host": email_cfg.get("smtp_host", "smtp.gmail.com"),
        "port": email_cfg.get("smtp_port", 587),
        "user": email_cfg.get("smtp_user", ""),
        "password": _email_secret("HUB_SMTP_PASS", email_cfg.get("smtp_pass", "")),
    }
    to_list = email_cfg.get("to", [])
    cc_list = email_cfg.get("cc", [])
    sender  = email_cfg.get("sender_name", "F180 QA Hub")
    subj    = email_cfg.get("subject_template", "")

    for proj in load_config().get("projects", []):
        dist_path = _resolve_path(proj["path"]) / "docs" / "distribution.json"
        if not dist_path.exists():
            continue
        try:
            dist = json.loads(dist_path.read_text(encoding="utf-8"))
            dist["email_provider"] = provider
            dist["smtp"] = smtp_block
            if provider == "resend":
                dist["resend"] = {
                    "api_key": _email_secret("HUB_RESEND_API_KEY", email_cfg.get("resend_api_key", "")),
                    "from":    email_cfg.get("resend_from", ""),
                }
            if to_list:
                dist.setdefault("email", {})["to"] = to_list
            if cc_list:
                dist.setdefault("email", {})["cc"] = cc_list
            dist.setdefault("email", {})["sender_name"] = sender
            if subj:
                dist.setdefault("email", {})["subject_template"] = subj
            _atomic_write_json(dist_path, dist)
        except Exception:
            pass


@app.route("/api/config/export")
def api_config_export():
    return send_file(CONFIG_FILE, as_attachment=True, download_name="config.json",
                     mimetype="application/json")


@app.route("/api/config/import", methods=["POST"])
def api_config_import():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400
    try:
        cfg = json.loads(f.read().decode("utf-8"))
        if "projects" not in cfg or not isinstance(cfg["projects"], list):
            return jsonify({"error": "invalid config format"}), 400
        save_config(cfg)
        return jsonify({"ok": True, "count": len(cfg["projects"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/config/backup/list")
def api_config_backup_list():
    """List daily config snapshots written by the background worker."""
    if not CONFIG_BACKUP_DIR.exists():
        return jsonify({"backups": [], "keep_days": CONFIG_BACKUP_KEEP})
    files = sorted(CONFIG_BACKUP_DIR.glob("config_*.json"), reverse=True)
    return jsonify({
        "backups": [
            {
                "name":    f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            } for f in files
        ],
        "keep_days": CONFIG_BACKUP_KEEP,
    })


@app.route("/api/config/backup/restore", methods=["POST"])
def api_config_backup_restore():
    """Restore a specific daily snapshot by filename. Body: {"name": "config_20260428.json"}.
    Atomically swaps the live config — like /api/config/import but reading from
    the backup directory instead of an uploaded file."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or "/" in name or "\\" in name:
        return jsonify({"error": "invalid backup name"}), 400
    src = CONFIG_BACKUP_DIR / name
    if not src.exists() or not src.name.startswith("config_"):
        return jsonify({"error": "backup not found"}), 404
    try:
        cfg = json.loads(src.read_text(encoding="utf-8"))
        if "projects" not in cfg or not isinstance(cfg["projects"], list):
            return jsonify({"error": "backup file is malformed"}), 400
        save_config(cfg)
        audit("config.backup.restore", source=name, count=len(cfg["projects"]))
        return jsonify({"ok": True, "restored_from": name, "projects": len(cfg["projects"])})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/config/backup/run", methods=["POST"])
def api_config_backup_run():
    """Trigger an immediate backup snapshot — useful before a risky import.
    Idempotent: if today's snapshot already exists it'll be overwritten."""
    try:
        CONFIG_BACKUP_DIR.mkdir(exist_ok=True)
        today  = datetime.now().strftime("%Y%m%d")
        target = CONFIG_BACKUP_DIR / f"config_{today}.json"
        shutil.copy2(CONFIG_FILE, target)
        audit("config.backup.run", target=target.name)
        return jsonify({"ok": True, "name": target.name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


RUN_HISTORY_FILE         = HUB_DIR / "run_history.json"
RUN_HISTORY_ARCHIVE_DIR  = HUB_DIR / "run_history_archive"  # per-month JSONL archives (YYYYMM)
RUN_HISTORY_MAX          = 500  # entries kept in live file; older flushed to archive
_watch_procs: dict = {}       # project_id → subprocess.Popen
_active_test_procs: dict = {} # project_id → subprocess.Popen (running playwright)


def _pytest_python(base: Path) -> str:
    """Return path to project's venv python, falling back to system python.
    Used by pytest-only projects to invoke the right interpreter for `python -m pytest`."""
    venv_py = base / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    posix_py = base / ".venv" / "bin" / "python"
    if posix_py.exists():
        return str(posix_py)
    return shutil.which("python") or "python"


def _parse_pytest_junit(xml_path: Path) -> tuple[int, int]:
    """Parse pytest junit XML, return (passed, failed). (0, 0) on error."""
    try:
        import xml.etree.ElementTree as _ET
        tree = _ET.parse(xml_path)
        root = tree.getroot()
        suite = root.find("testsuite") if root.tag == "testsuites" else root
        total    = int(suite.attrib.get("tests", 0))
        failures = int(suite.attrib.get("failures", 0))
        errors   = int(suite.attrib.get("errors", 0))
        skipped  = int(suite.attrib.get("skipped", 0))
        failed   = failures + errors
        return total - failed - skipped, failed
    except Exception:
        return 0, 0


def _tcids_from_excel(paths: dict) -> list[str]:
    """Return ordered list of TCIDs from TCM sheet (col C / index 2)."""
    xlsx = latest_xlsx(paths["input"])
    if not xlsx:
        return []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
        tcids, cur = [], None
        if "TCM" in wb.sheetnames:
            for row in wb["TCM"].iter_rows(values_only=True):
                if not any(c is not None for c in row): continue
                if row[0] == "TSID": continue
                if row[0] in ("STATUS LEGEND", "Pass"): break
                if row[0] and re.match(r"^TS_\d+$", str(row[0])): cur = str(row[0])
                if cur and len(row) > 2 and row[2]: tcids.append(str(row[2]))
        wb.close()
        return tcids
    except Exception:
        return []

_hist_lock = threading.Lock()

def _load_history() -> list:
    if RUN_HISTORY_FILE.exists():
        try:
            return migrate_history(json.loads(RUN_HISTORY_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return []

def _archive_history_overflow(overflow: list) -> None:
    """Append overflow entries to per-month JSONL archive files (run_history_YYYYMM.jsonl).
    JSONL = one JSON object per line, append-only; safe because caller holds _hist_lock."""
    if not overflow:
        return
    try:
        RUN_HISTORY_ARCHIVE_DIR.mkdir(exist_ok=True)
        by_month: dict = {}
        for e in overflow:
            ts = str(e.get("ts", ""))
            ym = ts[:7].replace("-", "") if len(ts) >= 7 else datetime.now().strftime("%Y%m")
            by_month.setdefault(ym, []).append(e)
        for ym, items in by_month.items():
            archive_file = RUN_HISTORY_ARCHIVE_DIR / f"run_history_{ym}.jsonl"
            with archive_file.open("a", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception as e:
        # Archival failure must not block new run logging
        logger.warning("run_history archive failed: %s", e)


def _save_history(entries: list):
    # Keep max RUN_HISTORY_MAX entries live; flush overflow to dated JSONL archives.
    with _hist_lock:
        if len(entries) > RUN_HISTORY_MAX:
            _archive_history_overflow(entries[:-RUN_HISTORY_MAX])
        _atomic_write_json(RUN_HISTORY_FILE, entries[-RUN_HISTORY_MAX:])


@app.route("/api/run/log", methods=["POST"])
def api_run_log():
    """Record a completed run into run_history.json."""
    data = request.json or {}
    pid = (data.get("project_id") or "").strip()
    if not pid:
        return jsonify({"error": "project_id required"}), 400
    entry = {
        "project_id": pid,
        "step":       data.get("step", "tests"),
        "ts":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pass":       data.get("pass", 0),
        "fail":       data.get("fail", 0),
        "rc":         data.get("rc", 0),
        "tag":        data.get("tag", ""),
        "env":        data.get("env", "uat"),   # "uat" | "prod"
    }
    entries = _load_history()
    entries.append(entry)
    _save_history(entries)
    return jsonify({"ok": True, "ts": entry["ts"]})


@app.route("/api/run/history")
def api_run_history():
    pid = request.args.get("p", "")
    env = request.args.get("env", "").strip()
    entries = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
    if env:
        entries = [e for e in entries if (e.get("env") or "uat") == env]
    return jsonify(entries[-50:])


@app.route("/api/run/history/delete", methods=["POST"])
def api_run_history_delete():
    """Delete a specific run entry by project_id + ts."""
    data = request.json or {}
    pid  = data.get("project_id", "").strip()
    ts   = data.get("ts", "").strip()
    if not pid or not ts:
        return jsonify({"error": "project_id and ts required"}), 400
    all_entries = _load_history()
    before = len(all_entries)
    # Remove first matching entry (ts + project_id should be unique enough)
    removed = False
    new_entries = []
    for e in all_entries:
        if not removed and e.get("project_id") == pid and e.get("ts") == ts:
            removed = True
        else:
            new_entries.append(e)
    _save_history(new_entries)
    return jsonify({"ok": True, "removed": removed, "before": before, "after": len(new_entries)})


@app.route("/api/run/history/purge", methods=["POST"])
def api_run_history_purge():
    """Bulk-delete run entries for a project by mode.

    mode="ghost"  — remove entries where pass=0 AND fail=0 (no test output captured)
    mode="failed" — remove entries where rc != 0
    mode="all"    — remove ALL entries for this project
    """
    data = request.json or {}
    pid  = data.get("project_id", "").strip()
    mode = data.get("mode", "ghost")
    if not pid:
        return jsonify({"error": "project_id required"}), 400

    all_entries = _load_history()
    before = len([e for e in all_entries if e.get("project_id") == pid and e.get("step") == "tests"])

    def should_remove(e):
        if e.get("project_id") != pid or e.get("step") != "tests":
            return False
        if mode == "ghost":
            return e.get("pass", 0) == 0 and e.get("fail", 0) == 0
        if mode == "failed":
            return e.get("rc", 0) != 0
        if mode == "all":
            return True
        return False

    new_entries = [e for e in all_entries if not should_remove(e)]
    _save_history(new_entries)
    after = len([e for e in new_entries if e.get("project_id") == pid and e.get("step") == "tests"])
    return jsonify({"ok": True, "removed": before - after, "remaining": after})


@app.route("/api/run/trend")
def api_run_trend():
    pid = request.args.get("p", "").strip()
    env = request.args.get("env", "").strip()
    entries = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
    if env:
        entries = [e for e in entries if (e.get("env") or "uat") == env]
    result = []
    for e in entries[-20:]:
        total = e.get("pass", 0) + e.get("fail", 0)
        result.append({
            "ts":   e["ts"],
            "pass": e.get("pass", 0),
            "fail": e.get("fail", 0),
            "pct":  round(e["pass"] / total * 100) if total else 0,
            "tag":  e.get("tag", ""),
            "env":  e.get("env", "uat"),
            "rc":   e.get("rc", 0),
        })
    return jsonify(result)


_CMD_CATEGORIES = {
    "test":"🧪 Testing","test-tag":"🧪 Testing","test-headed":"🧪 Testing",
    "test-file":"🧪 Testing","watch":"🧪 Testing","debug-test":"🧪 Testing","schedule-run":"🧪 Testing",
    "explore":"📋 Analysis & Review","ba-agent":"📋 Analysis & Review","traceability":"📋 Analysis & Review",
    "summarize-input":"📋 Analysis & Review","write-req":"📋 Analysis & Review",
    "diff-req":"📋 Analysis & Review","open-issues":"📋 Analysis & Review","project":"📋 Analysis & Review",
    "bug-assign":"🐛 Bug Management",
    "report":"📄 Report & Release","inject":"📄 Report & Release",
    "report-send":"📄 Report & Release","approve-release":"📄 Report & Release",
    "pipeline":"🔧 Hub / Utility","status":"🔧 Hub / Utility","dashboard":"🔧 Hub / Utility",
    "start":"🔧 Hub / Utility","hub-status":"🔧 Hub / Utility","hub-diagnose":"🔧 Hub / Utility",
}

@app.route("/api/commands")
def api_commands():
    """Discover slash commands from all registered project .claude/commands/ folders."""
    seen, commands = set(), []
    for p in load_config()["projects"]:
        cmd_dir = _resolve_path(p["path"]) / ".claude" / "commands"
        if not cmd_dir.exists():
            continue
        for f in sorted(cmd_dir.glob("*.md")):
            if f.stem in seen:
                continue
            seen.add(f.stem)
            try:
                first_line = f.read_text(encoding="utf-8", errors="ignore").split("\n")[0].strip()
                commands.append({
                    "name": f"/{f.stem}",
                    "description": first_line,
                    "category": _CMD_CATEGORIES.get(f.stem, "🔧 Hub / Utility"),
                    "source": p["id"],
                })
            except Exception:
                pass
    # Sort by category then name
    commands.sort(key=lambda c: (c["category"], c["name"]))
    return jsonify(commands)


@app.route("/api/projects/discover")
def api_projects_discover():
    """Auto-discover project subdirs in ROOT_DIR."""
    found = []
    registered = {p["path"] for p in load_config()["projects"]}

    def _detect_type(folder: Path) -> str | None:
        """Return project type if folder looks like a project, else None."""
        has_pw      = (folder / "playwright.config.ts").exists()
        has_pytest  = (folder / "pytest.ini").exists() or (folder / "pyproject.toml").exists()
        has_scripts = (folder / "scripts").exists()
        has_tcm_tpl = (folder / "templates" / "Test_Case_Template.xlsx").exists()
        if has_pw and has_scripts:
            return "full-pipeline"
        if has_pw:
            return "playwright-only"
        if has_pytest and not has_pw:
            return "pytest-only"
        if has_scripts and has_tcm_tpl:
            return "manual-testing"
        return None

    for d in sorted(ROOT_DIR.iterdir()):
        if not d.is_dir() or d.resolve() == HUB_DIR or d.name.startswith("."):
            continue
        # Direct project
        ptype = _detect_type(d)
        if ptype:
            rel = str(d.relative_to(ROOT_DIR)).replace("\\", "/")
            if rel not in registered:
                found.append({"name": d.name, "path": rel, "type": ptype})
        # Parent folder with sub-projects
        else:
            for sub in sorted(d.iterdir()):
                if not sub.is_dir():
                    continue
                stype = _detect_type(sub)
                if stype:
                    rel = str(sub.relative_to(ROOT_DIR)).replace("\\", "/")
                    if rel not in registered:
                        found.append({
                            "name": f"{d.name} / {sub.name}",
                            "path": rel,
                            "type": stype,
                        })
    return jsonify(found)


# ══════════════════════════════════════════════════════════════════════════════
# API — PROJECT DATA  (all require ?p=)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/info")
def api_info():
    paths, err = _req_paths()
    if err: return err
    proj_type = paths["proj"].get("type", "full-pipeline")
    data = read_excel_data(paths["input"]) if proj_type in ("full-pipeline", "manual-testing") else {}
    # Contract guarantee — Dashboard StatsRow expects these keys regardless of
    # whether an Excel file exists yet (read_excel_data returns {} pre-Excel).
    # Pinned by tests/test_api_contracts.py::test_contract_api_info_full_pipeline.
    data.setdefault("total_tc", 0)
    data.setdefault("totals", {"pass": 0, "fail": 0, "not start": 0, "in-progress": 0, "block": 0, "cancel": 0})
    data.setdefault("accuracy", 0)
    docx = latest_docx(paths["output"])
    data["output"] = None
    if docx:
        st = docx.stat()
        data["output"] = {
            "name":     docx.name,
            "size_kb":  round(st.st_size / 1024),
            "modified": datetime.fromtimestamp(st.st_mtime).strftime("%d %b %Y %H:%M"),
        }
    data["chart_available"] = (paths["screenshots"] / "chart_summary.png").exists()
    data["project_meta"] = {k: v for k, v in paths["proj"].items() if k != "abs_path"}

    # Always expose a flat shot_count for the dashboard StatsRow, regardless of project type
    if proj_type == "playwright-only":
        tr = paths["base"] / "test-results"
        data["shot_count"] = len(list(tr.rglob("*.png"))) if tr.exists() else 0
    elif proj_type == "pytest-only":
        sd = paths["base"] / "screenshots"
        tr = paths["base"] / "test-results"
        data["shot_count"] = (len(list(sd.rglob("*.png"))) if sd.exists() else 0) + \
                             (len(list(tr.rglob("*.png"))) if tr.exists() else 0)
    else:
        sd = paths["screenshots"]
        data["shot_count"] = len(list(sd.glob("TS_*.png"))) if sd.exists() else 0

    # tests-only types (playwright-only, pytest-only): inject run history summary for dashboard
    if proj_type in ("playwright-only", "pytest-only"):
        pid = request.args.get("p", "").strip()
        env = request.args.get("env", "").strip()
        hist = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
        if env:
            hist = [e for e in hist if (e.get("env") or "uat") == env]
        if proj_type == "playwright-only":
            shot_dir = paths["base"] / "test-results"
            report_path = paths["base"] / "playwright-report" / "index.html"
        else:  # pytest-only
            shot_dir = paths["base"] / "screenshots"
            report_path = paths["base"] / "test-report.html"
        shot_count = len(list(shot_dir.rglob("*.png"))) if shot_dir.exists() else 0
        data["pw_history"]    = hist[-10:]
        data["pw_shot_count"] = shot_count
        data["pw_report_ok"]  = report_path.exists()
        data["pw_report_ts"]  = datetime.fromtimestamp(
            report_path.stat().st_mtime
        ).strftime("%d %b %Y %H:%M") if data["pw_report_ok"] else None
        if hist:
            last = hist[-1]
            total = last["pass"] + last["fail"]
            data["pw_last"] = {
                "pass":     last["pass"],
                "fail":     last["fail"],
                "total":    total,
                "pct":      round(last["pass"] / total * 100) if total else 0,
                "tag":      last.get("tag", ""),
                "ts":       last["ts"],
                "rc":       last.get("rc", 0),
            }

    return jsonify(data)


@app.route("/api/info/export-excel")
def api_info_export_excel():
    paths, err = _req_paths()
    if err: return err
    proj_type = paths["proj"].get("type", "full-pipeline")
    proj_meta = paths["proj"]

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    HDR_FILL  = PatternFill("solid", fgColor="1F4E79")
    SUB_FILL  = PatternFill("solid", fgColor="2E75B6")
    TOT_FILL  = PatternFill("solid", fgColor="E8F0FE")
    PASS_FILL = PatternFill("solid", fgColor="E8F5E9")
    FAIL_FILL = PatternFill("solid", fgColor="FFEBEE")
    EVEN_FILL = PatternFill("solid", fgColor="F8F9FA")
    WHITE     = PatternFill("solid", fgColor="FFFFFF")
    thin = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"), bottom=Side(style="thin", color="CCCCCC"),
    )

    wb = openpyxl.Workbook()
    ws = wb.active

    safe_name = re.sub(r"[^\w\-]", "_", proj_meta.get("name", proj_meta.get("id", "project")))

    if proj_type == "playwright-only":
        # ── playwright-only: export run history ────────────────────────
        ws.title = "Run History"
        pid = request.args.get("p", "").strip()
        env = request.args.get("env", "").strip()
        hist = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
        if env:
            hist = [e for e in hist if (e.get("env") or "uat") == env]
        hist = [e for e in hist if e.get("pass", 0) > 0 or e.get("fail", 0) > 0]  # skip ghost

        ws.merge_cells("A1:H1")
        t = ws["A1"]
        t.value = f"Test Run History — {proj_meta.get('name', proj_meta.get('id',''))}"
        t.font  = Font(bold=True, size=14, color="FFFFFF")
        t.fill  = HDR_FILL
        t.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        ws.merge_cells("A2:H2")
        ws["A2"].value = f"Project: {proj_meta.get('id','')}   |   Exported: {datetime.now().strftime('%d %b %Y %H:%M')}   |   Runs: {len(hist)}"
        ws["A2"].font  = Font(size=10, color="FFFFFF")
        ws["A2"].fill  = SUB_FILL
        ws["A2"].alignment = Alignment(horizontal="left", indent=1)
        ws.row_dimensions[2].height = 18

        COLS   = ["Timestamp", "Env", "Scope", "Pass", "Fail", "Total", "Pass Rate", "Result"]
        WIDTHS = [20, 8, 12, 8, 8, 8, 11, 10]
        for i, (h, w) in enumerate(zip(COLS, WIDTHS), 1):
            c = ws.cell(row=3, column=i, value=h)
            c.font = Font(bold=True, color="FFFFFF", size=10)
            c.fill = PatternFill("solid", fgColor="2F5597")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = thin
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[3].height = 20
        ws.freeze_panes = "A4"

        for row_i, e in enumerate(reversed(hist), 1):
            row = row_i + 3
            total = e.get("pass", 0) + e.get("fail", 0)
            pct   = round(e["pass"] / total * 100) if total else 0
            env_v = (e.get("env") or "uat").upper()
            tag_v = e.get("tag") or "all"
            ok    = e.get("rc", 0) == 0
            fill  = EVEN_FILL if row_i % 2 == 0 else WHITE
            vals  = [e.get("ts",""), env_v, f"@{tag_v}" if not tag_v.startswith("@") else tag_v,
                     e.get("pass",0), e.get("fail",0), total, f"{pct}%", "Done ✓" if ok else "Error ✗"]
            for col_i, val in enumerate(vals, 1):
                cell = ws.cell(row=row, column=col_i, value=val)
                cell.border = thin
                cell.alignment = Alignment(horizontal="center" if col_i != 1 else "left", vertical="center")
                cell.font = Font(size=10)
                if col_i == 4 and e.get("pass", 0):
                    cell.fill = PASS_FILL; cell.font = Font(color="1B5E20", bold=True, size=10)
                elif col_i == 5 and e.get("fail", 0):
                    cell.fill = FAIL_FILL; cell.font = Font(color="B71C1C", bold=True, size=10)
                else:
                    cell.fill = fill
            ws.row_dimensions[row].height = 17

        filename = f"Run_History_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    else:
        # ── full-pipeline / manual-testing: export scenario summary ────
        ws.title = "Scenario Summary"
        data = read_excel_data(paths["input"])
        if not data.get("ts_order"):
            return jsonify({"error": "ไม่พบข้อมูล TCM — กรุณา Upload Excel ก่อน"}), 404

        proj_info = data.get("project", {})
        ts_order  = data["ts_order"]
        ts_data   = data["ts_data"]
        totals    = data["totals"]
        total_tc  = data["total_tc"]

        ws.merge_cells("A1:I1")
        t = ws["A1"]
        t.value = f"Test Scenario Summary — {proj_meta.get('name', proj_meta.get('id',''))}"
        t.font  = Font(bold=True, size=14, color="FFFFFF")
        t.fill  = HDR_FILL
        t.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        ws.merge_cells("A2:I2")
        sub = ws["A2"]
        meta_parts = []
        for f in ["Project Code", "Project Name", "Sprint / Version", "Customer"]:
            v = proj_info.get(f)
            if v: meta_parts.append(f"{f}: {v}")
        sub.value = "   |   ".join(meta_parts) if meta_parts else f"Project: {proj_meta.get('id','')}"
        sub.font  = Font(size=10, color="FFFFFF")
        sub.fill  = SUB_FILL
        sub.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[2].height = 18

        ws.merge_cells("A3:I3")
        ws["A3"].value = f"Exported: {datetime.now().strftime('%d %b %Y %H:%M')}   |   Total TCs: {total_tc}   |   Pass Rate: {data.get('accuracy', 0)}%"
        ws["A3"].font  = Font(size=9, italic=True, color="555555")
        ws["A3"].alignment = Alignment(horizontal="right", indent=1)
        ws.row_dimensions[3].height = 15

        COLS   = ["TSID", "Description", "Total", "Pass", "Fail", "In-Progress", "Block", "Not Start", "Cancel"]
        WIDTHS = [12, 55, 8, 8, 8, 11, 8, 10, 8]
        for i, (h, w) in enumerate(zip(COLS, WIDTHS), 1):
            c = ws.cell(row=4, column=i, value=h)
            c.font = Font(bold=True, color="FFFFFF", size=10)
            c.fill = PatternFill("solid", fgColor="2F5597")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = thin
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[4].height = 22
        ws.freeze_panes = "A5"

        STATUS_KEYS = ["pass", "fail", "in-progress", "block", "not start", "cancel"]
        for row_i, tsid in enumerate(ts_order, 1):
            ts  = ts_data[tsid]
            c   = ts["counts"]
            tot = sum(c.values())
            row = row_i + 4
            fill = EVEN_FILL if row_i % 2 == 0 else WHITE
            vals = [tsid, ts["desc"], tot, c.get("pass",0), c.get("fail",0),
                    c.get("in-progress",0), c.get("block",0), c.get("not start",0), c.get("cancel",0)]
            for col_i, val in enumerate(vals, 1):
                cell = ws.cell(row=row, column=col_i, value=val)
                cell.border = thin
                cell.alignment = Alignment(vertical="center", wrap_text=(col_i == 2),
                                           horizontal="left" if col_i <= 2 else "center")
                cell.font = Font(size=10, bold=(col_i == 1))
                if col_i == 4 and val:   cell.fill = PASS_FILL; cell.font = Font(color="1B5E20", bold=True, size=10)
                elif col_i == 5 and val: cell.fill = FAIL_FILL; cell.font = Font(color="B71C1C", bold=True, size=10)
                else:                    cell.fill = fill
            ws.row_dimensions[row].height = 18

        tot_row = len(ts_order) + 5
        ws.cell(tot_row, 1, "TOTAL").font = Font(bold=True, size=10)
        ws.cell(tot_row, 1).fill = TOT_FILL; ws.cell(tot_row, 1).border = thin
        ws.cell(tot_row, 2, "").fill = TOT_FILL; ws.cell(tot_row, 2).border = thin
        ws.cell(tot_row, 3, total_tc).font = Font(bold=True, size=10)
        ws.cell(tot_row, 3).fill = TOT_FILL; ws.cell(tot_row, 3).border = thin
        ws.cell(tot_row, 3).alignment = Alignment(horizontal="center")
        for col_i, key in enumerate(STATUS_KEYS, 4):
            v = totals.get(key, 0)
            cell = ws.cell(tot_row, col_i, v)
            cell.font = Font(bold=True, size=10, color=("1B5E20" if key=="pass" else "B71C1C" if key=="fail" else "000000"))
            cell.fill = TOT_FILL; cell.border = thin
            cell.alignment = Alignment(horizontal="center")
        ws.row_dimensions[tot_row].height = 20

        filename = f"Scenario_Summary_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/api/chart")
def api_chart():
    paths, err = _req_paths()
    if err: return err
    if paths["proj"].get("type") == "playwright-only":
        return jsonify({"error": "not available for playwright-only projects"}), 404
    chart = paths["screenshots"] / "chart_summary.png"
    if not chart.exists():
        return jsonify({"error": "chart not found"}), 404
    return send_file(chart, mimetype="image/png")


def _collect_screenshots(paths: dict) -> list[dict]:
    """Return list of screenshot dicts, handling both project types."""
    proj_type = paths["proj"].get("type", "full-pipeline")

    if proj_type in ("full-pipeline", "manual-testing"):
        d = paths["screenshots"]
        if not d.exists():
            return []
        files = sorted(d.glob("TS_*.png"), key=lambda f: f.name)
        return [{
            "filepath": f.name,           # relative to screenshots/
            "name":     f.name,
            "tcid":     f.stem,
            "size_kb":  round(f.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d %b %Y %H:%M"),
        } for f in files]

    if proj_type == "pytest-only":
        # pytest-only — scan screenshots/ + test-results/ for any .png
        result = []
        for sub in ("screenshots", "test-results"):
            d = paths["base"] / sub
            if not d.exists():
                continue
            for f in sorted(d.rglob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True):
                rel = str(f.relative_to(paths["base"])).replace("\\", "/")
                result.append({
                    "filepath": rel,
                    "name":     f.name,
                    "tcid":     rel,
                    "size_kb":  round(f.stat().st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d %b %Y %H:%M"),
                })
        return result

    # playwright-only — scan test-results/**/*.png
    tr = paths["base"] / "test-results"
    if not tr.exists():
        return []
    all_pngs = sorted(tr.rglob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in all_pngs:
        rel = f.relative_to(paths["base"])          # test-results/xxx/shot.png
        rel_str = str(rel).replace("\\", "/")
        # Use parent folder + filename as display label
        parts = rel_str.split("/")
        label = parts[-1].replace(".png", "")
        if len(parts) >= 3:                          # test-results/<suite>/<file>
            label = f"{parts[-2][:30]}…/{parts[-1]}" if len(parts[-2]) > 30 else f"{parts[-2]}/{parts[-1]}"
        result.append({
            "filepath": rel_str,
            "name":     f.name,
            "tcid":     label,
            "size_kb":  round(f.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d %b %Y %H:%M"),
        })
    return result


def _count_screenshots(p_entry: dict) -> int:
    """Type-aware screenshot count (used by /api/projects and /api/summary)."""
    path = _resolve_path(p_entry["path"])
    proj_type = p_entry.get("type")
    if proj_type == "playwright-only":
        tr = path / "test-results"
        return len(list(tr.rglob("*.png"))) if tr.exists() else 0
    if proj_type == "pytest-only":
        sd = path / "screenshots"
        tr = path / "test-results"
        return ((len(list(sd.rglob("*.png"))) if sd.exists() else 0) +
                (len(list(tr.rglob("*.png"))) if tr.exists() else 0))
    d = path / "screenshots"
    return len(list(d.glob("TS_*.png"))) if d.exists() else 0


def _last_run_time(p_entry: dict) -> str | None:
    """Return mtime of the most recently modified screenshot as a formatted string."""
    path = _resolve_path(p_entry["path"])
    proj_type = p_entry.get("type")
    if proj_type == "playwright-only":
        candidates = list((path / "test-results").rglob("*.png")) if (path / "test-results").exists() else []
    elif proj_type == "pytest-only":
        candidates = []
        for sub in ("screenshots", "test-results"):
            d = path / sub
            if d.exists():
                candidates.extend(d.rglob("*.png"))
    else:
        candidates = list((path / "screenshots").glob("TS_*.png")) if (path / "screenshots").exists() else []
    if not candidates:
        return None
    latest = max(candidates, key=lambda f: f.stat().st_mtime)
    return datetime.fromtimestamp(latest.stat().st_mtime).strftime("%d %b %Y %H:%M")


@app.route("/api/screenshots/list")
def api_screenshots_list():
    paths, err = _req_paths()
    if err: return err
    return jsonify(_collect_screenshots(paths))


@app.route("/api/screenshots/<path:filepath>")
def api_screenshot_file(filepath):
    """Serve screenshot — filepath may include subdirectories (playwright-only)."""
    paths, err = _req_paths()
    if err: return err
    proj_type = paths["proj"].get("type", "full-pipeline")

    if proj_type in ("full-pipeline", "manual-testing"):
        f = paths["screenshots"] / filepath
    else:
        f = paths["base"] / filepath      # filepath = "test-results/xxx/shot.png"

    f = f.resolve()
    # Safety: must be inside base dir
    try:
        f.relative_to(paths["base"])
    except ValueError:
        return jsonify({"error": "forbidden"}), 403

    if not f.exists() or f.suffix.lower() != ".png":
        return jsonify({"error": "not found"}), 404
    return send_file(f, mimetype="image/png")


@app.route("/api/screenshots/download")
def api_screenshots_download():
    """Bundle all screenshots into an in-memory ZIP and serve for download."""
    paths, err = _req_paths()
    if err: return err
    files = _collect_screenshots(paths)
    if not files:
        return jsonify({"error": "no screenshots"}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            abs_path = paths["base"] / f["filepath"]
            if abs_path.exists():
                zf.write(abs_path, f["filepath"].split("/")[-1])
    buf.seek(0)
    zip_name = f"{paths['proj']['id']}_screenshots.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=zip_name)


@app.route("/api/input/list")
def api_input_list():
    paths, err = _req_paths()
    if err: return err
    d = paths["input"]
    if not d.exists():
        return jsonify([])
    files = []
    for f in sorted(d.iterdir()):
        if f.is_file() and not f.name.startswith("~$"):
            st = f.stat()
            files.append({
                "name":     f.name,
                "size_kb":  round(st.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%d %b %Y %H:%M"),
                "ext":      f.suffix.lower(),
            })
    return jsonify(files)


@app.route("/api/input/download")
def api_input_download():
    paths, err = _req_paths()
    if err: return err
    xlsx = latest_xlsx(paths["input"])
    if not xlsx:
        return jsonify({"error": "no input file"}), 404
    return send_file(xlsx, as_attachment=True, download_name=xlsx.name)


@app.route("/api/output/list")
def api_output_list():
    paths, err = _req_paths()
    if err: return err
    d = paths["output"]
    if not d.exists():
        return jsonify([])
    files = []
    for f in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and not f.name.startswith("~$"):
            st = f.stat()
            files.append({
                "name":     f.name,
                "size_kb":  round(st.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%d %b %Y %H:%M"),
                "ext":      f.suffix.lower(),
            })
    return jsonify(files)


@app.route("/api/output/download")
def api_output_download():
    paths, err = _req_paths()
    if err: return err
    proj_type = paths["proj"].get("type", "full-pipeline")

    # pytest-only: serve test-report.html as the project's "output"
    if proj_type == "pytest-only":
        report = paths["base"] / "test-report.html"
        if not report.exists():
            return jsonify({"error": "no test-report.html — run tests first"}), 404
        as_attach = request.args.get("inline", "").strip() not in ("1", "true", "yes")
        return send_file(report, as_attachment=as_attach, download_name=report.name)

    # If a specific filename is requested via ?f=, serve that file (used by file list).
    # Otherwise fall back to latest .docx (used by quick-download buttons).
    requested = request.args.get("f", "").strip()
    if requested:
        target = (paths["output"] / requested).resolve()
        try:
            target.relative_to(paths["output"].resolve())
        except ValueError:
            return jsonify({"error": "forbidden"}), 403
        if not target.exists() or not target.is_file():
            return jsonify({"error": "not found"}), 404
        if target.suffix.lower() == ".docx":
            mark_download(paths["logs"], target)
        return send_file(target, as_attachment=True, download_name=target.name)
    docx = latest_docx(paths["output"])
    if not docx:
        return jsonify({"error": "no output file"}), 404
    mark_download(paths["logs"], docx)
    return send_file(docx, as_attachment=True, download_name=docx.name)


_PATH_KINDS = {"input", "output", "screenshots", "requirements", "figma"}


@app.route("/api/path/<kind>")
def api_path(kind: str):
    if kind not in _PATH_KINDS:
        return jsonify({"error": f"unknown kind: {kind}"}), 400
    paths, err = _req_paths()
    if err: return err
    folder = paths[kind]
    if kind != "input":
        folder.mkdir(parents=True, exist_ok=True)
    return jsonify({"path": str(folder)})


@app.route("/api/status")
def api_status():
    paths, err = _req_paths()
    if err: return err
    proj_type = paths["proj"].get("type", "full-pipeline")

    # pytest-only: only s5/s7/s8/s9 are meaningful — derived from junit + HTML report
    if proj_type == "pytest-only":
        pid = request.args.get("p", "").strip()
        hist = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
        valid = [e for e in hist if (e.get("pass", 0) + e.get("fail", 0)) > 0]
        last_test = valid[-1] if valid else None
        report = paths["base"] / "test-report.html"
        report_ts = (datetime.fromtimestamp(report.stat().st_mtime).strftime("%d %b %Y %H:%M")
                     if report.exists() else None)
        empty = {"ok": False, "file": None}
        return jsonify({
            "s1": empty, "s2": empty, "s3": empty, "s4": empty, "s6": empty,
            "s5": {"ok": last_test is not None,
                   "file": f"pass={last_test['pass']} fail={last_test['fail']}" if last_test else None},
            "s7": {"ok": report.exists(),
                   "file": "test-report.html" if report.exists() else None,
                   "ts":   report_ts},
            "s8": {"ok": report.exists(),
                   "file": "test-report.html" if report.exists() else None},
            "s9": {"ok": report.exists(),
                   "file": "test-report.html" if report.exists() else None},
            "ba_outputs":  [],
            "has_api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        })

    req_files   = sorted(paths["requirements"].glob("*.md"),          key=lambda f: f.stat().st_mtime, reverse=True) if paths["requirements"].exists() else []
    figma_files = sorted(paths["figma"].glob("*.png"),                key=lambda f: f.stat().st_mtime, reverse=True) if paths["figma"].exists()        else []
    ba_outputs  = sorted(paths["logs"].glob("ba_output_*.json"),      key=lambda f: f.stat().st_mtime, reverse=True) if paths["logs"].exists()         else []
    spec_files  = sorted(paths["tests"].glob("TS_*.spec.ts"))         if paths["tests"].exists()        else []
    screenshots = sorted(paths["screenshots"].glob("TS_*.png"))       if paths["screenshots"].exists()  else []
    xlsx = latest_xlsx(paths["input"])
    docx = latest_docx(paths["output"])
    # Spec staleness: any spec older than the Excel input?
    xlsx_mtime = xlsx.stat().st_mtime if xlsx else 0
    spec_stale = bool(xlsx_mtime and spec_files and any(
        f.stat().st_mtime < xlsx_mtime for f in spec_files
    ))
    return jsonify({
        "s1": {"ok": bool(req_files or figma_files), "files": [f.name for f in req_files] + [f.name for f in figma_files]},
        "s2": {"ok": bool(xlsx), "file": xlsx.name if xlsx else None, "ba_outputs": [f.name for f in ba_outputs]},
        "s3": {"ok": bool(xlsx), "file": xlsx.name if xlsx else None},
        "s4": {"ok": bool(spec_files), "count": len(spec_files), "files": [f.name for f in spec_files], "stale": spec_stale},
        "s5": {"ok": bool(screenshots), "count": len(screenshots)},
        "s6": {"ok": bool(xlsx), "file": xlsx.name if xlsx else None},
        "s7": {"ok": bool(docx), "file": docx.name if docx else None},
        "s8": {"ok": is_inject_done(docx), "file": docx.name if docx else None},
        "s9": {"ok": is_download_done(paths["logs"], docx), "file": docx.name if docx else None},
        "ba_outputs":   [f.name for f in ba_outputs],
        "has_api_key":  bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.route("/api/validate/excel")
def api_validate_excel():
    """Check Excel TCM completion: how many TCIDs have Status filled vs Not Start."""
    paths, err = _req_paths()
    if err: return err
    xlsx = latest_xlsx(paths["input"])
    if not xlsx:
        return jsonify({"error": "no input file"}), 404
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
        ALL = ["pass", "fail", "not start", "in-progress", "block", "cancel"]
        counts = {s: 0 for s in ALL}
        tcids, cur = [], None
        if "TCM" in wb.sheetnames:
            for row in wb["TCM"].iter_rows(values_only=True):
                if not any(c is not None for c in row): continue
                if row[0] == "TSID": continue
                if row[0] in ("STATUS LEGEND", "Pass"): break
                if row[0] and re.match(r"^TS_\d+$", str(row[0])): cur = str(row[0])
                if cur and len(row) > 2 and row[2]:
                    tcids.append(str(row[2]))
                    raw = str(row[9] or "").strip().lower() if len(row) > 9 else ""
                    s = raw if raw in ALL else "not start"
                    counts[s] += 1
        wb.close()
        total = len(tcids)
        not_started = counts["not start"]
        # Screenshot coverage
        shots = {f.stem for f in paths["screenshots"].glob("TS_*.png")} if paths["screenshots"].exists() else set()
        missing_shots = [t for t in tcids if t not in shots]
        return jsonify({
            "total": total, "filled": total - not_started,
            "not_started": not_started, "counts": counts,
            "missing_shots": missing_shots, "shot_coverage": len(tcids) - len(missing_shots),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# API — RELEASE GATE  (backend computation; mirrors frontend loadRelease logic)
# ══════════════════════════════════════════════════════════════════════════════

def _excel_tc_stats(paths: dict) -> dict:
    """Return {total, not_started, pass, pass_pct, shot_coverage_pct, shot_coverage_n} or empty dict."""
    xlsx = latest_xlsx(paths["input"])
    if not xlsx:
        return {}
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
        ALL = ["pass", "fail", "not start", "in-progress", "block", "cancel"]
        counts = {s: 0 for s in ALL}
        tcids, cur = [], None
        if "TCM" in wb.sheetnames:
            for row in wb["TCM"].iter_rows(values_only=True):
                if not any(c is not None for c in row): continue
                if row[0] == "TSID": continue
                if row[0] in ("STATUS LEGEND", "Pass"): break
                if row[0] and re.match(r"^TS_\d+$", str(row[0])): cur = str(row[0])
                if cur and len(row) > 2 and row[2]:
                    tcids.append(str(row[2]))
                    raw = str(row[9] or "").strip().lower() if len(row) > 9 else ""
                    s = raw if raw in ALL else "not start"
                    counts[s] += 1
        wb.close()
        total = len(tcids)
        shots = {f.stem for f in paths["screenshots"].glob("TS_*.png")} if paths["screenshots"].exists() else set()
        covered = sum(1 for t in tcids if t in shots)
        return {
            "total":              total,
            "not_started":        counts["not start"],
            "pass":               counts["pass"],
            "pass_pct":           round(counts["pass"] / total * 100) if total else None,
            "shot_coverage_n":    covered,
            "shot_coverage_pct":  round(covered / total * 100) if total else None,
        }
    except Exception:
        return {}


@app.route("/api/release-gate")
def api_release_gate():
    """GET /api/release-gate?p=<id> — returns JSON Release Gate result for CI integration.
    Response verdict: 'GO' | 'NOGO' | 'NOT_READY' | 'SKIP_PLANNING' | 'SKIP_PAUSED'.
    Use 'go' boolean for simple pass/fail gating."""
    pid = request.args.get("p", "").strip()
    if not pid:
        return jsonify({"error": "missing ?p=project_id"}), 400
    result = compute_release_gate(pid)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════════════
# API — RUN PIPELINE  (SSE, all require ?p=)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/run/generate")
def api_run_generate():
    paths, err = _req_paths()
    if err: return err
    return sse(_stream(paths["scripts"] / "run.py", paths["base"]))


@app.route("/api/run/inject")
def api_run_inject():
    paths, err = _req_paths()
    if err: return err
    def gen():
        # P2: Screenshot diff pre-check
        tcids = _tcids_from_excel(paths)
        if tcids:
            shots = {f.stem for f in paths["screenshots"].glob("TS_*.png")} if paths["screenshots"].exists() else set()
            missing = [t for t in tcids if t not in shots]
            extra   = [s for s in shots if s not in set(tcids)]
            matched = len(tcids) - len(missing)
            yield f"data: {json.dumps({'line': f'📸 Screenshot check: {matched}/{len(tcids)} matched', 'type': 'info'})}\n\n"
            if missing:
                preview = ' '.join(missing[:6]) + ('...' if len(missing) > 6 else '')
                yield f"data: {json.dumps({'line': f'⚠️  Missing ({len(missing)}): {preview}', 'type': 'warn'})}\n\n"
            if extra:
                yield f"data: {json.dumps({'line': f'ℹ️  Extra screenshots not in TCM: {len(extra)}', 'type': 'info'})}\n\n"
        yield from _stream(paths["scripts"] / "screenshot_injector.py", paths["base"])()
    return sse(gen)


@app.route("/api/run/add-charts")
def api_run_add_charts():
    paths, err = _req_paths()
    if err: return err
    return sse(_stream(paths["scripts"] / "add_excel_charts.py", paths["base"]))


@app.route("/api/run/tests")
def api_run_tests():
    paths, err = _req_paths()
    if err: return err
    proj_type = paths["proj"].get("type")
    if proj_type == "manual-testing":
        def _mt():
            yield f"data: {json.dumps({'line': '❌ manual-testing project ไม่รองรับ Playwright — ใช้ TCM Excel แทน', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(_mt)

    if proj_type == "pytest-only":
        tag      = request.args.get("tag",  "").strip()
        env      = request.args.get("env",  "").strip()
        pid_key  = request.args.get("p",    "").strip()
        base     = paths["base"]
        pid      = paths["proj"]["id"]
        def gen_pytest():
            label = f"▶ Running pytest{f' (-m {tag})' if tag else ''}..."
            if env:
                label += f" [TEST_ENV={env}]"
            yield f"data: {json.dumps({'line': label, 'type': 'info'})}\n\n"
            try:
                py = _pytest_python(base)
                junit_path = base / ".pytest_junit.xml"
                report_path = base / "test-report.html"
                cmd = [py, "-m", "pytest",
                       f"--junitxml={junit_path}",
                       f"--html={report_path}",
                       "--self-contained-html"]
                if tag:
                    cmd += ["-m", tag]
                run_env = {**os.environ}
                if env:
                    run_env["TEST_ENV"] = env
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(base),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env=run_env,
                )
                if pid_key:
                    _active_test_procs[pid_key] = proc
                for ln in proc.stdout:
                    ln = ln.rstrip()
                    if not ln:
                        continue
                    low = ln.lower()
                    t = ("err" if "failed" in low or " error" in low or "errors" in low
                         else "ok" if " passed" in low or "passed in" in low
                         else "info")
                    yield f"data: {json.dumps({'line': ln, 'type': t})}\n\n"
                _active_test_procs.pop(pid_key, None)
                try:
                    proc.wait(timeout=1800)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    yield f"data: {json.dumps({'line': 'ERROR: pytest timed out after 30 minutes — killed', 'type': 'err', 'done': True, 'returncode': -9})}\n\n"
                    return
                rc = proc.returncode
                if junit_path.exists():
                    passed, failed = _parse_pytest_junit(junit_path)
                    entry = {
                        "project_id": pid,
                        "step":       "tests",
                        "ts":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "pass":       passed,
                        "fail":       failed,
                        "rc":         rc,
                        "tag":        tag,
                        "env":        env or "uat",
                    }
                    entries = _load_history()
                    entries.append(entry)
                    _save_history(entries)
                    yield f"data: {json.dumps({'line': f'📊 Logged to history: pass={passed} fail={failed}', 'type': 'info'})}\n\n"
                done_type = "ok" if rc == 0 else ("warn" if rc == -15 else "err")
                msg = "Tests cancelled." if rc == -15 else f"Tests done (exit {rc})"
                yield f"data: {json.dumps({'line': msg, 'type': done_type, 'done': True, 'returncode': rc})}\n\n"
            except Exception as e:
                _active_test_procs.pop(pid_key, None)
                yield f"data: {json.dumps({'line': str(e), 'type': 'err', 'done': True, 'returncode': -1})}\n\n"
        return sse(gen_pytest)

    tag      = request.args.get("tag",  "").strip()
    env      = request.args.get("env",  "").strip()
    pid_key  = request.args.get("p",    "").strip()
    grep_pat = request.args.get("grep", "").strip()   # re-run specific tests
    headed   = request.args.get("headed", "").strip() in ("1", "true", "yes")
    def gen():
        label = f"▶ Running Playwright tests{f' (@{tag})' if tag else ''}..."
        if grep_pat:
            label = f"🔁 Re-running {grep_pat.count('|') + 1} failed test(s)..."
        if headed:
            label = "🐞 Debug mode (--headed --debug) — browser will open"
        if env:
            label += f" [TEST_ENV={env}]"
        yield f"data: {json.dumps({'line': label, 'type': 'info'})}\n\n"
        try:
            npx = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
            cmd = [npx, "playwright", "test", "--reporter=list"]
            if headed:
                cmd += ["--headed", "--debug", "--workers=1"]
            if grep_pat:
                cmd += ["--grep", grep_pat]
            elif tag:
                cmd += ["--grep", f"@{tag}"]
            run_env = {**os.environ}
            if env:
                run_env["TEST_ENV"] = env
            proc = subprocess.Popen(
                cmd,
                cwd=str(paths["base"]),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env=run_env,
            )
            if pid_key:
                _active_test_procs[pid_key] = proc
            for ln in proc.stdout:
                ln = ln.rstrip()
                if not ln:
                    continue
                t = ("warn" if "flaky" in ln.lower()
                     else "ok" if ("passed" in ln or "✓" in ln)
                     else "err" if ("failed" in ln or "✗" in ln)
                     else "info")
                yield f"data: {json.dumps({'line': ln, 'type': t})}\n\n"
            _active_test_procs.pop(pid_key, None)
            try:
                proc.wait(timeout=1800)   # 30 min hard cap — ป้องกัน playwright ค้างตลอดกาล
            except subprocess.TimeoutExpired:
                proc.kill()
                yield f"data: {json.dumps({'line': 'ERROR: Test run timed out after 30 minutes — killed', 'type': 'err', 'done': True, 'returncode': -9})}\n\n"
                return
            rc = proc.returncode
            done_type = "ok" if rc == 0 else ("warn" if rc == -15 else "err")
            msg = "Tests cancelled." if rc == -15 else f"Tests done (exit {rc})"
            yield f"data: {json.dumps({'line': msg, 'type': done_type, 'done': True, 'returncode': rc})}\n\n"
        except Exception as e:
            _active_test_procs.pop(pid_key, None)
            yield f"data: {json.dumps({'line': str(e), 'type': 'err', 'done': True, 'returncode': -1})}\n\n"
    return sse(gen)


@app.route("/api/run/cancel", methods=["POST"])
def api_run_cancel():
    pid_key = request.args.get("p", "").strip()
    proc = _active_test_procs.pop(pid_key, None)
    if proc and proc.poll() is None:
        proc.kill()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "reason": "no active run"})


@app.route("/api/run/debug")
def api_run_debug():
    """Stream /debug-test <spec> via claude CLI."""
    paths, err = _req_paths()
    if err: return err
    spec = request.args.get("spec", "").strip()
    if not spec:
        def _no():
            yield f"data: {json.dumps({'line': 'Error: spec parameter required', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(_no)
    claude_bin = shutil.which("claude") or "claude"
    def gen():
        yield f"data: {json.dumps({'line': f'🔍 Debugging {spec} via /debug-test...', 'type': 'info'})}\n\n"
        try:
            proc = subprocess.Popen(
                [claude_bin, "--dangerously-skip-permissions", "-p", f"/debug-test {spec}"],
                cwd=str(paths["base"]),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
            )
            for ln in proc.stdout:
                ln = ln.rstrip()
                if not ln:
                    continue
                t = "err" if "ERROR" in ln.upper() or "fail" in ln.lower() else "info"
                yield f"data: {json.dumps({'line': ln, 'type': t})}\n\n"
            proc.wait()
            rc = proc.returncode
            yield f"data: {json.dumps({'line': f'Debug done (exit {rc})', 'type': 'ok' if rc == 0 else 'err', 'done': True, 'returncode': rc})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'line': str(e), 'type': 'err', 'done': True, 'returncode': -1})}\n\n"
    return sse(gen)


@app.route("/api/run/send-report")
def api_run_send_report():
    paths, err = _req_paths()
    if err: return err
    channel = request.args.get("channel", "both")
    script  = paths["scripts"] / "send_report.py"
    if not script.exists():
        def _missing():
            yield f"data: {json.dumps({'line': '❌ send_report.py ไม่พบ — รัน /sync-agents ก่อน', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(_missing)
    return sse(_stream(script, paths["base"], ["--channel", channel]))


@app.route("/api/run/all")
def api_run_all():
    paths, err = _req_paths()
    if err: return err
    def gen():
        for script in [paths["scripts"] / "run.py", paths["scripts"] / "screenshot_injector.py"]:
            yield f"data: {json.dumps({'line': '', 'type': 'info'})}\n\n"
            yield from _stream(script, paths["base"])()
    return sse(gen)


@app.route("/api/run/watch", methods=["POST"])
def api_run_watch():
    """Toggle watch.py background process for a project."""
    paths, err = _req_paths()
    if err: return err
    pid_key = request.args.get("p", "")
    action  = (request.json or {}).get("action", "toggle")
    proc = _watch_procs.get(pid_key)
    running = proc is not None and proc.poll() is None

    if action == "stop" or (action == "toggle" and running):
        if proc:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
        _watch_procs.pop(pid_key, None)
        return jsonify({"running": False})
    else:
        watch_script = paths["scripts"] / "watch.py"
        if not watch_script.exists():
            return jsonify({"error": "watch.py not found in scripts/"}), 404
        new_proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", str(watch_script)],
            cwd=str(paths["base"]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _watch_procs[pid_key] = new_proc
        return jsonify({"running": True, "pid": new_proc.pid})


@app.route("/api/run/watch/status")
def api_run_watch_status():
    pid_key = request.args.get("p", "")
    proc = _watch_procs.get(pid_key)
    running = proc is not None and proc.poll() is None
    if proc and not running:
        _watch_procs.pop(pid_key, None)
    return jsonify({"running": running})


@app.route("/api/run/ba")
def api_run_ba():
    paths, err = _req_paths()
    if err: return err
    req_files   = sorted(paths["requirements"].glob("*.md"),  key=lambda f: f.stat().st_mtime, reverse=True) if paths["requirements"].exists() else []
    figma_files = sorted(paths["figma"].glob("*.png"),        key=lambda f: f.stat().st_mtime, reverse=True) if paths["figma"].exists()        else []
    if not req_files and not figma_files:
        def gen():
            yield f"data: {json.dumps({'line': 'Error: ไม่พบไฟล์ใน requirements/ หรือ figma/', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(gen)
    args = []
    if req_files:   args += ["--input-dir",   str(paths["requirements"])]  # combine all .md (survey_map + requirement etc.)
    if figma_files: args += ["--figma-image", str(figma_files[0])]
    args += ["--skip-playwright", "--no-interactive"]  # Fix 1+3: prevent input() hang
    return sse(_stream(paths["scripts"] / "orchestrator.py", paths["base"], args, timeout=900))


@app.route("/api/run/spec")
def api_run_spec():
    paths, err = _req_paths()
    if err: return err
    ba_files = sorted(paths["logs"].glob("ba_output_*.json"), key=lambda f: f.stat().st_mtime, reverse=True) if paths["logs"].exists() else []
    if not ba_files:
        def gen():
            yield f"data: {json.dumps({'line': 'Error: ไม่พบ ba_output_*.json ใน logs/', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(gen)
    return sse(_stream(paths["scripts"] / "orchestrator.py", paths["base"],
                       ["--skip-ba", str(ba_files[0]), "--no-interactive"], timeout=900))


@app.route("/api/run/explore")
def api_run_explore():
    paths, err = _req_paths()
    if err: return err
    script = paths["scripts"] / "explore_survey.py"
    if not script.exists():
        def gen():
            yield f"data: {json.dumps({'line': 'Error: explore_survey.py not found in scripts/ — sync project files from Hub scaffold first', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(gen)
    url = request.args.get("url", "").strip()
    args = [url] if url else []
    return sse(_stream(script, paths["base"], args, timeout=1800))


@app.route("/api/run/review-excel")
def api_run_review_excel():
    paths, err = _req_paths()
    if err: return err
    script = paths["scripts"] / "review_excel.py"
    if not script.exists():
        def gen():
            yield f"data: {json.dumps({'line': 'Error: review_excel.py not found in scripts/', 'type': 'err', 'done': True, 'returncode': 1})}\n\n"
        return sse(gen)
    return sse(_stream(script, paths["base"]))


# ══════════════════════════════════════════════════════════════════════════════
# BUG REPORTS
# ══════════════════════════════════════════════════════════════════════════════

BUGS_DIR = HUB_DIR / "bugs"


def _bugs_file(pid: str) -> Path:
    BUGS_DIR.mkdir(exist_ok=True)
    return BUGS_DIR / f"{pid}.json"


def load_bugs(pid: str) -> list:
    f = _bugs_file(pid)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


_bugs_lock = threading.Lock()


def save_bugs(pid: str, bugs: list):
    with _bugs_lock:
        _atomic_write_json(_bugs_file(pid), bugs)


def _next_bug_id(pid: str, bugs: list) -> str:
    prefix = re.sub(r"[^A-Z0-9]", "", pid.upper())[:6] or "BUG"
    nums = [int(m.group()) for b in bugs
            for m in [re.search(r"\d+$", b.get("id", ""))] if m]
    seq = max(nums, default=0) + 1
    return f"BUG-{prefix}-{seq:03d}"


@app.route("/api/bugs")
def api_bugs_list():
    pid = request.args.get("p", "").strip()
    if not pid:
        return jsonify({"error": "missing ?p="}), 400
    return jsonify(load_bugs(pid))


@app.route("/api/bugs/add", methods=["POST"])
def api_bugs_add():
    data = request.get_json(force=True)
    pid  = data.get("project_id", "").strip()
    if not pid:
        return jsonify({"error": "missing project_id"}), 400
    bugs = load_bugs(pid)
    # status defaults to Open but caller may pre-set Fixed/Closed for bulk import
    initial_status = data.get("status", "Open")
    if initial_status not in ("Open", "Fixed", "Closed"):
        initial_status = "Open"
    bug  = {
        "id":           _next_bug_id(pid, bugs),
        "project_id":   pid,
        "title":        data.get("title", "").strip(),
        "severity":     data.get("severity", "Medium"),
        "environment":  data.get("environment", "").strip(),
        "steps":        data.get("steps", []),
        "expected":     data.get("expected", "").strip(),
        "actual":       data.get("actual", "").strip(),
        "evidence":     data.get("evidence", []),
        "related_task": data.get("related_task", "").strip(),
        "related_spec": data.get("related_spec", "").strip(),
        "description":  data.get("description", "").strip(),
        "assignee":     data.get("assignee", "").strip(),
        "status":       initial_status,
        "created_at":   datetime.now().isoformat(timespec="seconds"),
    }
    bugs.append(bug)
    save_bugs(pid, bugs)
    return jsonify({"ok": True, "bug": bug})


_BUG_UPDATE_FIELDS = [
    "title", "severity", "environment", "steps",
    "expected", "actual", "evidence",
    "related_task", "related_spec", "status",
    "description", "assignee",
]


@app.route("/api/bugs/update", methods=["POST"])
@validate_body(
    required=["project_id", "id"],
    # notify_assignee is a legacy side-effect flag from BugAssignModal — accepted
    # for backwards compatibility but currently not acted on server-side.
    allowed=[*_BUG_UPDATE_FIELDS, "notify_assignee"],
)
def api_bugs_update(body):
    pid    = body["project_id"].strip()
    bug_id = body["id"].strip()
    bugs = load_bugs(pid)
    for b in bugs:
        if b["id"] == bug_id:
            for field in _BUG_UPDATE_FIELDS:
                if field in body:
                    b[field] = body[field]
            b["updated_at"] = datetime.now().isoformat(timespec="seconds")
            save_bugs(pid, bugs)
            return jsonify({"ok": True, "bug": b})
    return jsonify({"error": "bug not found"}), 404


@app.route("/api/bugs/delete", methods=["POST"])
def api_bugs_delete():
    data   = request.get_json(force=True)
    pid    = data.get("project_id", "").strip()
    bug_id = data.get("id", "").strip()
    if not pid or not bug_id:
        return jsonify({"error": "missing project_id or id"}), 400
    bugs = load_bugs(pid)
    filtered = [b for b in bugs if b["id"] != bug_id]
    if len(filtered) == len(bugs):
        return jsonify({"error": "bug not found"}), 404
    save_bugs(pid, filtered)
    return jsonify({"ok": True})


@app.route("/api/bugs/export")
def api_bugs_export():
    pid = request.args.get("p", "").strip()
    if not pid:
        return jsonify({"error": "missing ?p="}), 400
    proj = get_project(pid)
    if not proj:
        return jsonify({"error": "project not found"}), 404
    bugs = load_bugs(pid)

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from collections import Counter

    SEV_COLORS    = {"Critical": "C62828", "High": "E65100",
                     "Medium": "F57F17",   "Low":  "2E7D32"}
    STATUS_COLORS = {"Open": "B71C1C", "In Progress": "E65100",
                     "Resolved": "2E7D32", "Closed": "37474F"}

    wb = Workbook()
    ws = wb.active
    ws.title = "Bug Report"

    headers = ["Bug ID", "Title", "Severity", "Status", "Environment",
               "Steps to Reproduce", "Expected Behavior", "Actual Behavior",
               "Evidence", "Related Task", "Spec / Link", "Created At"]

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font      = Font(bold=True, color="FFFFFF", size=11)
        cell.fill      = PatternFill("solid", fgColor="1F3864")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = Border(bottom=Side(style="medium", color="FFFFFF"))
    ws.row_dimensions[1].height = 28

    for row_num, bug in enumerate(bugs, 2):
        steps_text   = "\n".join(f"{i+1}. {s}" for i, s in enumerate(bug.get("steps", [])))
        evidence_text = "; ".join(bug.get("evidence", []))
        row_data = [
            bug.get("id", ""),         bug.get("title", ""),
            bug.get("severity", ""),   bug.get("status", ""),
            bug.get("environment", ""), steps_text,
            bug.get("expected", ""),   bug.get("actual", ""),
            evidence_text,             bug.get("related_task", ""),
            bug.get("related_spec", ""), bug.get("created_at", ""),
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if col == 3:
                color = SEV_COLORS.get(bug.get("severity", ""), "757575")
                cell.font      = Font(bold=True, color="FFFFFF")
                cell.fill      = PatternFill("solid", fgColor=color)
                cell.alignment = Alignment(horizontal="center", vertical="top")
            elif col == 4:
                color = STATUS_COLORS.get(bug.get("status", ""), "757575")
                cell.font      = Font(bold=True, color="FFFFFF")
                cell.fill      = PatternFill("solid", fgColor=color)
                cell.alignment = Alignment(horizontal="center", vertical="top")
            elif row_num % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F7FAFF")
        ws.row_dimensions[row_num].height = max(30, 15 * max(1, steps_text.count("\n") + 1))

    for i, w in enumerate([14, 35, 12, 13, 18, 40, 30, 30, 28, 14, 22, 18], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Summary sheet ──────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Summary")
    ws2["A1"] = f"Bug Report — {proj['name']}"
    ws2["A1"].font = Font(bold=True, size=14, color="1F3864")
    ws2["A2"] = f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Total: {len(bugs)}"
    ws2["A2"].font = Font(italic=True, color="888888")

    by_sev    = Counter(b.get("severity", "—") for b in bugs)
    by_status = Counter(b.get("status",   "—") for b in bugs)

    ws2["A4"] = "By Severity";  ws2["A4"].font = Font(bold=True)
    for i, (k, v) in enumerate(by_sev.most_common(), 5):
        ws2[f"A{i}"] = k; ws2[f"B{i}"] = v

    base = 5 + len(by_sev) + 2
    ws2[f"A{base}"] = "By Status"; ws2[f"A{base}"].font = Font(bold=True)
    for i, (k, v) in enumerate(by_status.most_common(), base + 1):
        ws2[f"A{i}"] = k; ws2[f"B{i}"] = v

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"bugs_{pid}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ══════════════════════════════════════════════════════════════════════════════
# API — EMAIL TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

EMAIL_TPL_DIR = HUB_DIR / "email_templates"

def _mock_data(scenario="pass"):
    """Generate mock template variables for preview."""
    is_pass = scenario == "pass"
    return {
        "project_name": "MOCK Demo Project",
        "date": datetime.now().strftime("%d %B %Y"),
        "pass_rate": 100 if is_pass else 67,
        "pass_count": 10 if is_pass else 8,
        "fail_count": 0 if is_pass else 3,
        "not_start_count": 0 if is_pass else 1,
        "total": 10 if is_pass else 12,
        "result_icon": "&#10004;" if is_pass else "&#10060;",
        "result_label": "PASSED" if is_pass else "FAILED",
        "banner_bg": "#E8F5E9" if is_pass else "#FFEBEE",
        "banner_color": "#1B5E20" if is_pass else "#B71C1C",
        "rate_bg": "#E8F5E9" if is_pass else "#FFF3E0",
        "rate_color": "#2E7D32" if is_pass else "#E65100",
        "greeting": "Dear Team,",
        "intro_text": f"UAT Test Report for <b>MOCK Demo Project</b> — {datetime.now().strftime('%d %B %Y')}",
        "suite_title": "Test Suite Summary",
        "suites": [
            {"id": "TS_01", "desc": "Login & Auth", "total": 4, "pass": 4 if is_pass else 3, "fail": 0 if is_pass else 1, "not_start": 0, "rate": 100 if is_pass else 75},
            {"id": "TS_02", "desc": "Survey Flow", "total": 3, "pass": 3 if is_pass else 2, "fail": 0 if is_pass else 1, "not_start": 0, "rate": 100 if is_pass else 67},
            {"id": "TS_03", "desc": "Report Export", "total": 3, "pass": 3 if is_pass else 2, "fail": 0 if is_pass else 1, "not_start": 0 if is_pass else 1, "rate": 100 if is_pass else 67},
        ],
        "failed_tcs": [] if is_pass else [
            {"id": "TC-007", "name": "Mask SSN with special characters", "tsid": "TS_02"},
            {"id": "TC-008", "name": "Partial mask on numeric fields", "tsid": "TS_02"},
            {"id": "TC-011", "name": "Masked fields hidden in export", "tsid": "TS_03"},
        ],
        "failed_tcs_title": "Failed Test Cases (3)",
        "open_bugs": [] if is_pass else [
            {"id": "BUG-001", "title": "SSN masking fails on special chars", "severity": "High"},
            {"id": "BUG-002", "title": "Export shows masked fields", "severity": "Medium"},
        ],
        "bugs_title": "Open Bugs (2)",
        "runs": [
            {"ts": "2026-04-20 08:00", "tag": "smoke", "env": "UAT", "pass": 10, "fail": 0 if is_pass else 2, "rate": 100 if is_pass else 83, "dot": "&#128994;" if is_pass else "&#128308;"},
            {"ts": "2026-04-20 10:00", "tag": "e2e", "env": "UAT", "pass": 18, "fail": 0 if is_pass else 6, "rate": 100 if is_pass else 75, "dot": "&#128994;" if is_pass else "&#128308;"},
            {"ts": "2026-04-20 13:30", "tag": "regression", "env": "UAT", "pass": 19 if is_pass else 11, "fail": 1 if is_pass else 8, "rate": 95 if is_pass else 58, "dot": "&#128994;" if is_pass else "&#128308;"},
        ],
        "trend_title": "Run History (Latest)",
        "attachment_note": "Attached: Project_TestResult_20260420.docx",
        "footer_text": f"Sent by <b>F180 QA Hub</b> &middot; {datetime.now().strftime('%d %b %Y %H:%M')}",
        "footer_contact": "Contact QA Lead for questions",
    }


@app.route("/api/email-template")
def api_email_template_get():
    name = request.args.get("name", "manual")
    if name not in ("manual", "playwright"):
        return jsonify({"error": "invalid template name"}), 400
    tpl_path = EMAIL_TPL_DIR / f"{name}.html"
    if not tpl_path.exists():
        return jsonify({"error": "template not found"}), 404
    return jsonify({"name": name, "html": tpl_path.read_text(encoding="utf-8")})


@app.route("/api/email-template/save", methods=["POST"])
def api_email_template_save():
    data = request.get_json(force=True)
    name = data.get("name", "")
    html = data.get("html", "")
    if name not in ("manual", "playwright"):
        return jsonify({"error": "invalid template name"}), 400
    tpl_path = EMAIL_TPL_DIR / f"{name}.html"
    tpl_path.write_text(html, encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/email-template/preview")
def api_email_template_preview():
    name     = request.args.get("name", "manual")
    scenario = request.args.get("scenario", "pass")
    if name not in ("manual", "playwright"):
        return jsonify({"error": "invalid template name"}), 400
    tpl_path = EMAIL_TPL_DIR / f"{name}.html"
    if not tpl_path.exists():
        return jsonify({"error": "template not found"}), 404
    from jinja2 import Template
    tpl  = Template(tpl_path.read_text(encoding="utf-8"))
    html = tpl.render(**_mock_data(scenario))
    return Response(html, mimetype="text/html")


@app.route("/api/email-template/reset", methods=["POST"])
def api_email_template_reset():
    """Reset template to git version (if available) or return error."""
    data = request.get_json(force=True)
    name = data.get("name", "")
    if name not in ("manual", "playwright"):
        return jsonify({"error": "invalid template name"}), 400
    tpl_path = EMAIL_TPL_DIR / f"{name}.html"
    try:
        result = subprocess.run(
            ["git", "checkout", "HEAD", "--", f"email_templates/{name}.html"],
            cwd=str(HUB_DIR), capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return jsonify({"ok": True, "html": tpl_path.read_text(encoding="utf-8")})
        return jsonify({"error": "git checkout failed"}), 500
    except Exception:
        return jsonify({"error": "cannot reset — no git history"}), 500


# ══════════════════════════════════════════════════════════════════════════════
# API — SYSTEM CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/system-check")
def api_system_check():
    """Run system health checks as SSE stream."""
    def gen():
        results = []

        def _emit(name, ok, detail=""):
            status = "ok" if ok else "fail"
            results.append(ok)
            obj = {"check": name, "status": status, "detail": detail}
            yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        # 1. Python dependencies
        missing = []
        for mod in ["flask", "openpyxl", "docx", "pandas", "lxml", "watchdog", "dotenv"]:
            try:
                __import__(mod)
            except ImportError:
                missing.append(mod)
        if missing:
            yield from _emit("Python Dependencies", False, f"missing: {', '.join(missing)}")
        else:
            yield from _emit("Python Dependencies", True, "flask, openpyxl, python-docx, pandas, lxml, watchdog")

        # 2. Node.js / npx
        try:
            npx = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
            r = subprocess.run([npx, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                yield from _emit("Node.js / npx", True, f"npx {r.stdout.strip()}")
            else:
                yield from _emit("Node.js / npx", False, "npx found but returned error")
        except Exception as e:
            yield from _emit("Node.js / npx", False, str(e))

        # 3. Hub API health
        try:
            cfg = load_config()
            proj_count = len(cfg.get("projects", []))
            yield from _emit("Hub Config", True, f"{proj_count} projects registered")
        except Exception as e:
            yield from _emit("Hub Config", False, str(e))

        # 4. Generate mock TCM Excel
        mock_manual = ROOT_DIR / "_mock-manual"
        mock_full   = ROOT_DIR / "_mock-full"
        has_mock_manual = mock_manual.exists() and (mock_manual / "tests" / "mockup" / "data" / "create_mock_tcm.py").exists()
        has_mock_full   = mock_full.exists()   and (mock_full   / "tests" / "mockup" / "data" / "create_mock_tcm.py").exists()

        if not has_mock_manual and not has_mock_full:
            yield from _emit("Mock Projects", False, "_mock-manual/ and _mock-full/ not found")
        else:
            found = []
            if has_mock_manual: found.append("_mock-manual")
            if has_mock_full:   found.append("_mock-full")
            yield from _emit("Mock Projects", True, ", ".join(found))

        # 5. Generate TCM Excel (mock-manual)
        if has_mock_manual:
            try:
                r = subprocess.run(
                    [sys.executable, "-X", "utf8",
                     str(mock_manual / "tests" / "mockup" / "data" / "create_mock_tcm.py"),
                     "--scenario", "manual-pass"],
                    cwd=str(mock_manual), capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    yield from _emit("Generate TCM Excel", True, "manual-pass: 10 TCs created")
                else:
                    yield from _emit("Generate TCM Excel", False, r.stderr.strip()[-120:] if r.stderr else "unknown error")
            except Exception as e:
                yield from _emit("Generate TCM Excel", False, str(e))

        # 6. Generate Word Report (mock-manual)
        if has_mock_manual and (mock_manual / "scripts" / "generate_report.py").exists():
            # Inject ba_output first
            ba_src = mock_manual / "tests" / "mockup" / "data" / "ba_output_manual_pass.json"
            if ba_src.exists():
                ba_dst = mock_manual / "logs" / "ba_output_syscheck.json"
                shutil.copy2(str(ba_src), str(ba_dst))
            try:
                r = subprocess.run(
                    [sys.executable, "-X", "utf8",
                     str(mock_manual / "scripts" / "generate_report.py")],
                    cwd=str(mock_manual), capture_output=True, text=True, timeout=60)
                if r.returncode == 0:
                    docx_files = list((mock_manual / "output").glob("*.docx"))
                    size = f"{docx_files[0].stat().st_size // 1024}KB" if docx_files else "?"
                    yield from _emit("Generate Word Report", True, f"output created ({size})")
                else:
                    yield from _emit("Generate Word Report", False, r.stderr.strip()[-120:] if r.stderr else "unknown error")
            except Exception as e:
                yield from _emit("Generate Word Report", False, str(e))

        # 7. SMTP connection test (dry-run — connect only, don't send)
        smtp_ok = False
        if has_mock_manual:
            dist_file = mock_manual / "docs" / "distribution.json"
            if dist_file.exists():
                try:
                    dist = json.loads(dist_file.read_text(encoding="utf-8"))
                    smtp_cfg = dist.get("smtp", {})
                    host = smtp_cfg.get("host", "")
                    port = int(smtp_cfg.get("port", 587))
                    user = smtp_cfg.get("user", "")
                    pwd  = smtp_cfg.get("password", "")
                    if host and user and pwd:
                        import smtplib as _smtp
                        server = _smtp.SMTP(host, port, timeout=10)
                        server.starttls()
                        server.login(user, pwd)
                        server.quit()
                        smtp_ok = True
                        yield from _emit("SMTP Connection", True, f"{host}:{port} — login OK")
                    else:
                        yield from _emit("SMTP Connection", False, "smtp config incomplete in distribution.json")
                except Exception as e:
                    yield from _emit("SMTP Connection", False, str(e)[:100])
        if not smtp_ok and not has_mock_manual:
            yield from _emit("SMTP Connection", False, "no mock project to test with")

        # 8. run_history.json writable
        hist_path = HUB_DIR / "run_history.json"
        try:
            existing = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []
            yield from _emit("Run History", True, f"{len(existing)} entries, writable")
        except Exception as e:
            yield from _emit("Run History", False, str(e))

        # Summary
        passed = sum(1 for r in results if r)
        total  = len(results)
        yield f"data: {json.dumps({'done': True, 'passed': passed, 'total': total})}\n\n"

    return sse(gen)


# ══════════════════════════════════════════════════════════════════════════════
# API — TOOLS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/tools/retrofit-tcm", methods=["POST"])
def api_retrofit_tcm():
    """Generate TCM Excel from Playwright spec files for playwright-only projects."""
    paths, err = _req_paths()
    if err: return err
    if paths["proj"].get("type") != "playwright-only":
        return jsonify({"error": "only for playwright-only projects"}), 400

    base = paths["base"]
    # Find all spec files
    specs = sorted(base.rglob("*.spec.ts"))
    if not specs:
        return jsonify({"error": "ไม่พบ .spec.ts files"}), 404

    # Parse describe titles: "STAFFXX | TC-YY — Description @tags"
    import re as _re
    desc_re = _re.compile(r'test\.describe\s*\(\s*["\']([^"\']+)["\']')
    tag_re  = _re.compile(r'(@\w+)')
    tc_re   = _re.compile(r'(TC-[\w]+(?:\s*&\s*TC-[\w]+)*)')

    # Group by STAFF ID
    from collections import OrderedDict
    groups = OrderedDict()   # staff_id → [(tcid, desc, tags), ...]

    for spec in specs:
        try:
            src = spec.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in desc_re.finditer(src):
            title = m.group(1).strip()
            # Parse "STAFF31 | TC-01 — Page Load @smoke"
            parts = title.split("|", 1)
            if len(parts) < 2:
                continue
            staff_id = parts[0].strip()               # e.g. STAFF31
            rest     = parts[1].strip()               # e.g. TC-01 — Page Load @smoke
            tc_m     = tc_re.search(rest)
            tcid_raw = tc_m.group(1) if tc_m else "TC-??"
            # Remove TCID and tags from description
            desc_clean = tc_re.sub("", rest)
            desc_clean = tag_re.sub("", desc_clean)
            desc_clean = desc_clean.lstrip(" —–-").strip()
            tags       = " ".join(tag_re.findall(rest))
            if staff_id not in groups:
                groups[staff_id] = []
            # Handle "TC-02 & TC-06" → split into multiple rows
            for tcid in _re.split(r'\s*&\s*', tcid_raw):
                tcid = tcid.strip()
                groups[staff_id].append((tcid, desc_clean, tags))

    if not groups:
        return jsonify({"error": "parse ไม่ได้ — ตรวจ format test.describe"}), 400

    # Build Excel
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return jsonify({"error": "openpyxl not installed"}), 500

    wb = openpyxl.Workbook()

    # ── PROJECT_INFO sheet ───────────────────────────────────────────
    pi = wb.active
    pi.title = "PROJECT_INFO"
    proj_name = paths["proj"].get("name", base.name)
    pi.append(["", "* Project Name", proj_name])
    pi.append(["", "* Project Type", "playwright-only"])
    pi.append(["", "* Generated By", "QA Hub Demo — Retrofit TCM"])
    pi.append(["", "* Generated Date", datetime.now().strftime("%Y-%m-%d %H:%M")])

    # ── TCM sheet ────────────────────────────────────────────────────
    tcm = wb.create_sheet("TCM")
    header_fill = PatternFill("solid", fgColor="1F3864")
    header_font = Font(bold=True, color="FFFFFF")
    headers = ["TSID", "TS Description", "TCID", "TC Description", "Tags",
               "Col F", "Col G", "Col H", "Col I", "Status"]
    for ci, h in enumerate(headers, 1):
        cell = tcm.cell(row=1, column=ci, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    row = 2
    ts_num = 0
    for staff_id, tests in groups.items():
        # Extract number from STAFF31 → 031
        num_m = _re.search(r'\d+', staff_id)
        ts_num = int(num_m.group()) if num_m else ts_num + 1
        tsid = f"TS_{ts_num:03d}"
        # TSID header row
        ts_cell = tcm.cell(row=row, column=1, value=tsid)
        ts_cell.font = Font(bold=True)
        tcm.cell(row=row, column=2, value=f"{staff_id} Survey")
        row += 1
        for tcid, desc, tags in tests:
            tcm.cell(row=row, column=3, value=tcid)
            tcm.cell(row=row, column=4, value=desc)
            tcm.cell(row=row, column=5, value=tags)
            tcm.cell(row=row, column=10, value="not start")
            row += 1

    # Column widths
    for col, w in zip("ABCDEFGHIJ", [12,24,12,40,24,8,8,8,8,14]):
        tcm.column_dimensions[col].width = w

    # Save
    input_dir = base / "input"
    input_dir.mkdir(exist_ok=True)
    out_file = input_dir / f"TCM_{base.name}.xlsx"
    wb.save(out_file)

    tc_count = sum(len(v) for v in groups.values())
    return jsonify({
        "ok": True,
        "file": out_file.name,
        "ts_count": len(groups),
        "tc_count": tc_count,
        "path": str(out_file),
    })


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE RUNNER
# ══════════════════════════════════════════════════════════════════════════════

SCHEDULE_FILE     = HUB_DIR / "schedules.json"
SCHEDULE_LOG_FILE = HUB_DIR / "schedule.log"
SCHED_LOCK_DIR    = HUB_DIR / ".sched_locks"   # atomic per-fire lock files (cross-process dedup)
_sched_lock         = threading.Lock()
_sched_notifications: list = []        # in-memory queue, cleared after client reads
_last_sched_fire: dict     = {}        # sched_id → "YYYY-MM-DD HH:MM" last fired


def _claim_fire(sid: str, minute_key: str) -> bool:
    """Atomically claim that we (this process/thread) will fire <sid> at <minute_key>.

    Uses os.O_CREAT | os.O_EXCL — atomic on Windows + Linux. Returns True if we
    own the fire; False if another process/thread already claimed it. Falls open
    (returns True) on filesystem errors so a transient FS issue doesn't silently
    kill the scheduler.
    """
    try:
        SCHED_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return True
    safe = minute_key.replace(":", "").replace(" ", "_").replace("-", "")
    lock_file = SCHED_LOCK_DIR / f"{sid}_{safe}.lock"
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, datetime.now().isoformat().encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return True


def _cleanup_old_sched_locks(max_age_seconds: int = 86400) -> None:
    """Remove fire-lock files older than 1 day. Called once at scheduler start."""
    try:
        if not SCHED_LOCK_DIR.exists():
            return
        cutoff = time.time() - max_age_seconds
        for f in SCHED_LOCK_DIR.glob("*.lock"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _slog(msg: str):
    """Append a timestamped line to schedule.log (max 500 lines)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        existing = SCHEDULE_LOG_FILE.read_text(encoding="utf-8") if SCHEDULE_LOG_FILE.exists() else ""
        lines = existing.splitlines(keepends=True)
        lines.append(line)
        _atomic_write_text(SCHEDULE_LOG_FILE, "".join(lines[-500:]))
    except Exception:
        pass


def load_schedules() -> list:
    if SCHEDULE_FILE.exists():
        try:
            return migrate_schedules(json.loads(SCHEDULE_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return []


def save_schedules(schedules: list):
    with _sched_lock:
        _atomic_write_json(SCHEDULE_FILE, schedules)


def _next_sched_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


def _cron_matches(sched: dict, now: datetime) -> bool:
    stype = sched.get("schedule_type", "daily")
    if stype == "daily":
        try:
            h, m = map(int, sched.get("time", "00:00").split(":"))
            return now.hour == h and now.minute == m
        except Exception:
            return False
    elif stype == "weekly":
        try:
            h, m = map(int, sched.get("time", "00:00").split(":"))
            return now.weekday() == sched.get("weekday", 0) and now.hour == h and now.minute == m
        except Exception:
            return False
    elif stype == "cron":
        expr = sched.get("cron", "0 8 * * *").split()
        if len(expr) < 5:
            return False
        def _m(field, val):
            return field == "*" or int(field) == val
        try:
            return _m(expr[0], now.minute) and _m(expr[1], now.hour) and \
                   _m(expr[2], now.day) and _m(expr[3], now.month) and \
                   _m(expr[4], now.weekday())
        except Exception:
            return False
    return False


def _push_notification(pid: str, action: str, tag: str, status: str, env: str = "uat"):
    cfg  = load_config()
    pmap = {p["id"]: p["name"] for p in cfg["projects"]}
    _sched_notifications.append({
        "ts":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_name": pmap.get(pid, pid),
        "action":       action,
        "tag":          tag,
        "env":          env,
        "status":       status,
    })
    if len(_sched_notifications) > 20:
        _sched_notifications.pop(0)


def _run_scheduled(sched: dict):
    pid    = sched.get("project_id", "")
    action = sched.get("action", "tests")
    tag    = sched.get("tag", "all")
    env    = sched.get("env", "uat")

    _slog(f"START  id={sched['id']} project={pid} action={action} tag={tag} env={env}")

    paths = get_paths(pid)
    if not paths:
        _slog(f"ERROR  id={sched['id']} project not found: {pid}")
        _push_notification(pid, action, tag, "error: project not found")
        return

    base    = paths["base"]
    scripts = paths["scripts"]
    status  = "ok"

    try:
        if action == "tests":
            proj_type = paths["proj"].get("type", "full-pipeline")
            if proj_type == "pytest-only":
                py = _pytest_python(base)
                junit_path = base / ".pytest_junit.xml"
                report_path = base / "test-report.html"
                cmd = [py, "-m", "pytest",
                       f"--junitxml={junit_path}",
                       f"--html={report_path}",
                       "--self-contained-html"]
                if tag and tag != "all":
                    cmd += ["-m", tag.lstrip("@")]
                run_env = {**os.environ}
                if env and env != "uat":
                    run_env["TEST_ENV"] = env
                _slog(f"RUN    {' '.join(cmd)}  cwd={base}  TEST_ENV={env}")
                result = subprocess.run(
                    cmd, cwd=str(base), text=True,
                    encoding="utf-8", errors="replace", timeout=1800,
                    shell=False, env=run_env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                pass_, fail = _parse_pytest_junit(junit_path) if junit_path.exists() else (0, 0)
                _slog(f"RESULT rc={result.returncode} pass={pass_} fail={fail}")
                entry = {
                    "project_id": pid, "step": "tests",
                    "ts":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "pass": pass_, "fail": fail,
                    "rc":   result.returncode,
                    "tag":  tag.lstrip("@") if tag and tag != "all" else "",
                    "env":  env or "uat",
                    "source": "schedule",
                }
                hist = _load_history()
                hist.append(entry)
                _save_history(hist)
                status = "ok" if result.returncode == 0 else f"error(rc={result.returncode})"
            elif proj_type in ("full-pipeline", "playwright-only"):
                npx = shutil.which("npx") or r"C:\Program Files\nodejs\npx.cmd"
                cmd = [npx, "playwright", "test", "--reporter=list"]
                if tag and tag != "all":
                    # Tag is stored without leading "@" (matches Pipeline runner convention).
                    # Tolerate legacy entries that still include the @ prefix.
                    norm_tag = tag.lstrip("@")
                    cmd.append(f"--grep=@{norm_tag}")
                run_env = {**os.environ}
                if env and env != "uat":
                    run_env["TEST_ENV"] = env
                _slog(f"RUN    {' '.join(cmd)}  cwd={base}  TEST_ENV={env}")
                result = subprocess.run(
                    cmd, cwd=str(base), text=True,
                    encoding="utf-8", errors="replace", timeout=600,
                    shell=False, env=run_env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                )
                output = result.stdout or ""
                pass_ = fail = flaky = 0
                for line in output.splitlines():
                    mm = re.search(r"(\d+)\s+passed", line)
                    if mm: pass_ = int(mm.group(1))
                    mm = re.search(r"(\d+)\s+failed", line)
                    if mm: fail = int(mm.group(1))
                    mm = re.search(r"(\d+)\s+flaky", line)
                    if mm: flaky = int(mm.group(1))
                _slog(f"RESULT rc={result.returncode} pass={pass_} fail={fail} flaky={flaky}")
                entry = {
                    "project_id": pid, "step": "tests",
                    "ts":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "pass": pass_, "fail": fail, "flaky": flaky,
                    "rc":   result.returncode,
                    "tag":  tag.lstrip("@") if tag and tag != "all" else "",
                    "source": "schedule",
                }
                hist = _load_history()
                hist.append(entry)
                _save_history(hist)   # _save_history already holds _hist_lock internally
                status = "ok" if result.returncode == 0 else f"error(rc={result.returncode})"
            else:
                status = "skipped"
                _slog(f"SKIP   manual-testing project, nothing to run")

        elif action == "generate":
            script = scripts / "generate_tcm.py"
            if script.exists():
                r = subprocess.run([sys.executable, "-X", "utf8", str(script)],
                                   cwd=str(base), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=300)
                status = "ok" if r.returncode == 0 else f"error(rc={r.returncode})"
            else:
                status = "error: generate_tcm.py not found"

        elif action == "inject":
            script = scripts / "screenshot_injector.py"
            if script.exists():
                r = subprocess.run([sys.executable, "-X", "utf8", str(script)],
                                   cwd=str(base), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=300)
                status = "ok" if r.returncode == 0 else f"error(rc={r.returncode})"
            else:
                status = "error: screenshot_injector.py not found"

        elif action == "add-charts":
            script = scripts / "add_excel_charts.py"
            if script.exists():
                r = subprocess.run([sys.executable, "-X", "utf8", str(script)],
                                   cwd=str(base), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=300)
                status = "ok" if r.returncode == 0 else f"error(rc={r.returncode})"
            else:
                status = "error: add_excel_charts.py not found"

    except subprocess.TimeoutExpired:
        status = "error: timeout"
        _slog(f"TIMEOUT id={sched['id']}")
    except Exception as e:
        status = f"error: {e}"
        _slog(f"EXCEPT  id={sched['id']} {e}")

    _slog(f"DONE   id={sched['id']} status={status}")

    # Persist last_run / last_status
    slist = load_schedules()
    for s in slist:
        if s["id"] == sched["id"]:
            s["last_run"]    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            s["last_status"] = status
            break
    save_schedules(slist)

    _push_notification(pid, action, tag, status, env)
    _notify_scheduled_result(sched, pid, action, tag, status, env)


def _notify_scheduled_result(sched: dict, pid: str, action: str, tag: str, status: str, env: str) -> None:
    """Fire chat webhooks for a scheduled run result. Failure-safe.

    Per-schedule notify_on (sched['notify_on']) overrides the global
    notifications.notify_on filter when present, so a noisy schedule
    can be silenced and a critical one (Prod smoke) escalated."""
    try:
        cfg = (load_config().get("notifications", {}) or {}).copy()
        if not (cfg.get("slack_webhook") or cfg.get("teams_webhook") or cfg.get("discord_webhook")):
            return  # no destinations configured

        # Per-schedule override of notify_on filter
        sched_notify_on = sched.get("notify_on") if isinstance(sched, dict) else None
        if sched_notify_on:
            cfg["notify_on"] = sched_notify_on

        proj = next((p for p in load_config().get("projects", []) if p["id"] == pid), None)
        proj_name = proj["name"] if proj else pid

        low = status.lower()
        if low.startswith("ok"):
            level = "ok"
        elif low.startswith("error"):
            level = "error"
        else:
            level = "fail"

        emoji_env = "🔴 PROD" if env == "prod" else "🟢 UAT"
        title = f"{proj_name} — {action} {tag or ''}".strip()
        body = (
            f"*Status:* `{status}`\n"
            f"*Env:* {emoji_env}\n"
            f"*Schedule:* {sched.get('id', '?') if isinstance(sched, dict) else '?'} ({sched.get('schedule_type', '') if isinstance(sched, dict) else ''})\n"
            f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        _notify_webhooks(title, body, level=level, config=cfg)
    except Exception as e:
        logger.warning("chat notify failed: %s", e)


def _scheduler_loop():
    _slog("SCHEDULER started")
    _cleanup_old_sched_locks()
    while True:
        try:
            now        = datetime.now()
            minute_key = now.strftime("%Y-%m-%d %H:%M")
            for sched in load_schedules():
                if not sched.get("enabled", True):
                    continue
                sid = sched["id"]
                if _last_sched_fire.get(sid) == minute_key:
                    continue                      # already fired this minute (in-process)
                if _cron_matches(sched, now):
                    # Cross-process atomic claim — protects against concurrent processes during
                    # service restarts and any future multi-worker deployment
                    if not _claim_fire(sid, minute_key):
                        _last_sched_fire[sid] = minute_key   # someone else owns it; remember + skip
                        continue
                    _last_sched_fire[sid] = minute_key
                    _slog(f"FIRE   id={sid} project={sched.get('project_id')} at {minute_key}")
                    threading.Thread(target=_run_scheduled, args=(sched,), daemon=True).start()
        except Exception as e:
            _slog(f"LOOP_ERR {e}")
        time.sleep(20)   # check 3× per minute; dedup via minute_key + lock file


threading.Thread(target=_scheduler_loop, daemon=True).start()


@app.route("/api/schedules")
def api_schedules_list():
    schedules = load_schedules()
    # Enrich with project name
    cfg = load_config()
    proj_map = {p["id"]: p["name"] for p in cfg["projects"]}
    for s in schedules:
        s["project_name"] = proj_map.get(s["project_id"], s["project_id"])
    return jsonify(schedules)


@app.route("/api/schedules/add", methods=["POST"])
def api_schedules_add():
    data = request.json or {}
    for k in ["project_id", "action", "schedule_type"]:
        if not data.get(k):
            return jsonify({"error": f"missing: {k}"}), 400
    # Optional per-schedule notify_on override (falls back to global filter when missing)
    sched_notify_on = data.get("notify_on")
    if sched_notify_on is not None and not isinstance(sched_notify_on, list):
        return jsonify({"error": "notify_on must be a list when provided"}), 400

    entry = {
        "id":            _next_sched_id(),
        "project_id":    data["project_id"],
        "action":        data.get("action", "tests"),
        "tag":           data.get("tag", "all"),
        "env":           data.get("env", "uat") if data.get("env", "uat") in ("uat", "prod") else "uat",
        "schedule_type": data["schedule_type"],
        "time":          data.get("time", "08:00"),
        "weekday":       int(data.get("weekday", 1)),
        "cron":          data.get("cron", "0 8 * * *"),
        "enabled":       True,
        "created_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_run":      None,
        "last_status":   None,
        **({"notify_on": sched_notify_on} if sched_notify_on else {}),
    }
    schedules = load_schedules()
    schedules.append(entry)
    save_schedules(schedules)
    audit("schedule.add",
          id=entry["id"], project_id=entry["project_id"],
          run_action=entry["action"],   # 'action' is taken by audit's positional arg
          env=entry["env"], tag=entry["tag"], schedule_type=entry["schedule_type"])
    return jsonify({"ok": True, "id": entry["id"]})


@app.route("/api/schedules/toggle", methods=["POST"])
def api_schedules_toggle():
    data = request.json or {}
    sid = data.get("id")
    schedules = load_schedules()
    for s in schedules:
        if s["id"] == sid:
            s["enabled"] = not s.get("enabled", True)
            save_schedules(schedules)
            return jsonify({"ok": True, "enabled": s["enabled"]})
    return jsonify({"error": "not found"}), 404


@app.route("/api/schedules/delete", methods=["POST"])
def api_schedules_delete():
    data = request.json or {}
    sid = data.get("id")
    old = load_schedules()
    schedules = [s for s in old if s["id"] != sid]
    if len(schedules) == len(old):
        return jsonify({"error": "schedule not found"}), 404
    save_schedules(schedules)
    audit("schedule.delete", id=sid)
    return jsonify({"ok": True})


@app.route("/api/flakiness")
def api_flakiness():
    """GET /api/flakiness?p=<id>&window=<N> — flakiness analysis for a project.
    Returns the structure from flakiness.analyse; see that module for fields."""
    pid = request.args.get("p", "").strip()
    if not pid:
        return jsonify({"error": "missing ?p=project_id"}), 400
    try:
        window = int(request.args.get("window", 20))
    except ValueError:
        window = 20
    window = max(1, min(window, 500))  # clamp to sane range

    entries = [
        e for e in _load_history()
        if e.get("project_id") == pid and e.get("step") == "tests"
    ]
    result = _analyse_flakiness(entries, window=window)
    result["project_id"] = pid
    return jsonify(result)


@app.route("/api/config/ai")
def api_config_ai():
    """GET — return AI provider config (api_key NOT exposed in plain;
    we just return whether it's set)."""
    a = load_config().get("ai", {}) or {}
    return jsonify({
        "provider":     a.get("provider", "cli"),
        "model":        a.get("model", ""),
        "api_key_set":  bool(a.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")),
    })


@app.route("/api/config/ai/save", methods=["POST"])
def api_config_ai_save():
    """POST — save AI provider config. api_key only updated when explicitly provided
    (empty string in payload means 'don't change' to avoid accidental clearing)."""
    data = request.get_json(force=True) or {}
    cfg = load_config()
    existing = cfg.get("ai", {}) or {}
    new_ai = {
        "provider": (data.get("provider") or "cli").lower(),
        "model":    (data.get("model") or "").strip(),
    }
    # Preserve existing api_key unless caller sent a new non-empty one,
    # OR explicitly sent api_key=null/None to clear.
    if "api_key" in data:
        if data["api_key"] is None or data["api_key"] == "":
            new_ai["api_key"] = ""
        else:
            new_ai["api_key"] = data["api_key"]
    elif existing.get("api_key"):
        new_ai["api_key"] = existing["api_key"]
    if new_ai["provider"] not in ("cli", "api"):
        return jsonify({"error": "provider must be 'cli' or 'api'"}), 400
    cfg["ai"] = new_ai
    save_config(cfg)
    audit("config.ai.save", provider=new_ai["provider"], model=new_ai.get("model"), api_key_set=bool(new_ai.get("api_key")))
    return jsonify({"ok": True})


@app.route("/api/ai/generate-test-plan", methods=["POST"])
def api_ai_generate_test_plan():
    """POST — call configured AI provider to draft a test plan from a requirement.
    Body: {project_id?, requirement: str}
    Response: {provider, model, output}  or  {error, detail}"""
    from ai_provider import generate, build_test_plan_prompt, AIProviderError

    data = request.get_json(force=True) or {}
    requirement = (data.get("requirement") or "").strip()
    if not requirement:
        return jsonify({"error": "requirement text required"}), 400
    if len(requirement) > 50_000:
        return jsonify({"error": "requirement too long (max 50,000 chars)"}), 400

    pid = data.get("project_id", "")
    proj = next((p for p in load_config().get("projects", []) if p["id"] == pid), {})
    project_name = proj.get("name", "")
    project_type = proj.get("type", "")

    prompt = build_test_plan_prompt(requirement, project_name, project_type)
    ai_cfg = load_config().get("ai", {}) or {}
    try:
        result = generate(prompt, config=ai_cfg)
    except AIProviderError as e:
        return jsonify({"error": "AI provider error", "detail": str(e)}), 502
    audit("ai.generate", provider=result["provider"], project_id=pid, requirement_chars=len(requirement))
    return jsonify(result)


# ── A2 — Smart release summary ──────────────────────────────────────────────
@app.route("/api/ai/release-summary", methods=["POST"])
def api_ai_release_summary():
    """POST /api/ai/release-summary — generate a Thai-language release summary
    for stakeholders. Pulls fresh data (release-gate + bugs + flakiness)
    from existing internals so the UI just sends {project_id}.
    Body: {project_id: str}"""
    from ai_provider import generate, build_release_summary_prompt, AIProviderError

    data = request.get_json(silent=True) or {}
    pid = (data.get("project_id") or "").strip()
    if not pid:
        return jsonify({"error": "project_id required"}), 400

    proj = next((p for p in load_config().get("projects", []) if p["id"] == pid), None)
    if not proj:
        return jsonify({"error": f"project not found: {pid}"}), 404

    # Pull current release-gate state — reuses the same logic the UI sees
    gate = compute_release_gate(pid)
    if "error" in gate:
        return jsonify({"error": gate["error"]}), 404

    # Bug counts by severity for context
    bugs = load_bugs(pid)
    open_critical = sum(1 for b in bugs if b.get("severity") == "Critical" and b.get("status") == "Open")
    open_high     = sum(1 for b in bugs if b.get("severity") == "High"     and b.get("status") == "Open")
    open_total    = sum(1 for b in bugs if b.get("status") == "Open")

    # Recent flakiness — pass rate over the rolling window
    hist = [e for e in _load_history() if e.get("project_id") == pid and e.get("step") == "tests"]
    flak = _analyse_flakiness(hist, window=20) if hist else {}
    pass_rate = flak.get("pass_rate_tests")

    prompt = build_release_summary_prompt(
        project_name=proj.get("name", pid),
        project_type=proj.get("type", "full-pipeline"),
        phase=proj.get("phase", "active"),
        verdict=gate.get("verdict", "UNKNOWN"),
        criteria=gate.get("criteria", []),
        open_bugs=open_total,
        open_critical=open_critical,
        open_high=open_high,
        pass_rate=int(pass_rate) if isinstance(pass_rate, (int, float)) else None,
        runs=flak.get("runs_in_window", 0),
    )
    ai_cfg = load_config().get("ai", {}) or {}
    try:
        result = generate(prompt, config=ai_cfg)
    except AIProviderError as e:
        return jsonify({"error": "AI provider error", "detail": str(e)}), 502
    audit("ai.release_summary", provider=result["provider"], project_id=pid, verdict=gate.get("verdict"))
    return jsonify({**result, "verdict": gate.get("verdict")})


# ── A1 — AI bug triage ──────────────────────────────────────────────────────
@app.route("/api/ai/bug-triage", methods=["POST"])
def api_ai_bug_triage():
    """POST /api/ai/bug-triage — suggest severity, tags, and similar bugs.
    Body: {project_id, title, description?}
    Response: {provider, model, severity, severity_reason, tags[], similar[]}
    Falls back gracefully if AI returns invalid JSON — surfaces raw output."""
    from ai_provider import generate, build_bug_triage_prompt, AIProviderError

    data = request.get_json(silent=True) or {}
    pid   = (data.get("project_id") or "").strip()
    title = (data.get("title") or "").strip()
    desc  = (data.get("description") or "").strip()
    if not pid or not title:
        return jsonify({"error": "project_id and title required"}), 400
    if len(title) + len(desc) > 20_000:
        return jsonify({"error": "input too long (title + description max 20,000 chars)"}), 400

    # Existing open bugs — used by the AI to flag duplicates
    bugs = load_bugs(pid)
    existing_open = [
        {"id": b["id"], "title": b.get("title", "")}
        for b in bugs if b.get("status") == "Open"
    ]

    prompt = build_bug_triage_prompt(title=title, description=desc, existing=existing_open)
    ai_cfg = load_config().get("ai", {}) or {}
    try:
        result = generate(prompt, config=ai_cfg)
    except AIProviderError as e:
        return jsonify({"error": "AI provider error", "detail": str(e)}), 502

    # Parse AI's JSON output. AI provider may wrap in markdown fences despite
    # the prompt — strip them defensively.
    raw = (result.get("output") or "").strip()
    cleaned = raw
    if cleaned.startswith("```"):
        # drop opening fence (and optional language tag)
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Surface the raw output so the UI can show the user what happened
        audit("ai.bug_triage", provider=result["provider"], project_id=pid, parsed=False)
        return jsonify({
            "provider": result["provider"], "model": result["model"],
            "error":    "AI did not return valid JSON",
            "raw":      raw[:2000],
        }), 502

    # Validate shape — we can't trust an LLM output blindly. Default safe values.
    severity = parsed.get("severity")
    if severity not in ("Critical", "High", "Medium", "Low"):
        severity = "Medium"
    tags = parsed.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    similar = parsed.get("similar") or []
    if not isinstance(similar, list):
        similar = []
    # similar must be ids that actually exist in this project
    valid_ids = {b["id"] for b in bugs}
    similar = [s for s in similar if isinstance(s, str) and s in valid_ids][:5]

    audit("ai.bug_triage", provider=result["provider"], project_id=pid,
          severity=severity, tags_count=len(tags), similar_count=len(similar))
    return jsonify({
        "provider":         result["provider"],
        "model":            result["model"],
        "severity":         severity,
        "severity_reason":  parsed.get("severity_reason", "")[:300],
        "tags":             [str(t)[:40] for t in tags[:6]],
        "similar":          similar,
    })


@app.route("/api/metrics")
def api_metrics():
    """Per-route request metrics — count, p50/p95/p99 latency (ms), 5xx errors.
    Sample data is in-memory only (resets on restart) and capped at the last
    200 requests per route, so this is for local observability not historical
    analysis. Sort routes by p95 desc so the slowest endpoints surface first."""
    now = datetime.now()
    with _METRICS_LOCK:
        snapshot = {
            r: list(buf) for r, buf in _metrics_latency.items()
        }
        counts  = dict(_metrics_count)
        errors  = dict(_metrics_errors)

    def _quantile(sorted_data: list[float], q: float) -> float:
        if not sorted_data:
            return 0.0
        # nearest-rank — fine for n ≤ 200
        idx = max(0, min(len(sorted_data) - 1, int(round(q * (len(sorted_data) - 1)))))
        return round(sorted_data[idx], 2)

    routes = []
    for route, samples in snapshot.items():
        sorted_samples = sorted(samples)
        routes.append({
            "route":      route,
            "count":      counts.get(route, 0),
            "errors":     errors.get(route, 0),
            "p50_ms":     _quantile(sorted_samples, 0.50),
            "p95_ms":     _quantile(sorted_samples, 0.95),
            "p99_ms":     _quantile(sorted_samples, 0.99),
            "max_ms":     round(max(samples), 2) if samples else 0,
            "samples":    len(samples),
        })
    routes.sort(key=lambda r: r["p95_ms"], reverse=True)

    total_requests = sum(counts.values())
    total_errors   = sum(errors.values())
    up_seconds = int((now - HUB_STARTED_AT).total_seconds())

    return jsonify({
        "started_at":     HUB_STARTED_AT.strftime("%Y-%m-%d %H:%M:%S"),
        "now":            now.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": up_seconds,
        "total_requests": total_requests,
        "total_errors":   total_errors,
        "error_rate_pct": round(total_errors / total_requests * 100, 2) if total_requests else 0.0,
        "rps_lifetime":   round(total_requests / up_seconds, 3) if up_seconds else 0.0,
        "routes":         routes,
        "window_per_route": _METRICS_WINDOW,
        "tracked_routes":   len(routes),
    })


@app.route("/api/metrics/history")
def api_metrics_history():
    """Per-minute historical metrics from the SQLite ring buffer.

    Query params:
      hours  : window size in hours (default 24, capped at HUB_METRICS_KEEP_HOURS)
      route  : optional — filter to one route's series

    Returns: {entries:[{ts, route, count, errors, p95_ms, max_ms}], hours, keep_hours}.
    Sprint H — backs the historical-trend tile that v2.3.0's /api/metrics
    couldn't deliver (in-memory only resets on Hub restart)."""
    try:
        hours = max(1, min(int(request.args.get("hours", 24)), METRICS_KEEP_HOURS))
    except ValueError:
        hours = 24
    route_filter = (request.args.get("route") or "").strip()

    entries = _metrics_history(hours)
    if route_filter:
        entries = [e for e in entries if e["route"] == route_filter]

    return jsonify({
        "entries":     entries,
        "hours":       hours,
        "keep_hours":  METRICS_KEEP_HOURS,
        "rows":        len(entries),
    })


@app.route("/api/hub/health")
def api_hub_health():
    """Real-time Hub runtime health snapshot (separate from /api/system-check
    which is a pre-flight probe). Polls cheaply — meant for an auto-refreshing
    dashboard widget."""
    now = datetime.now()
    up_seconds = int((now - HUB_STARTED_AT).total_seconds())

    # Recent errors from hub.log (count lines with WARNING or ERROR in last N minutes)
    error_count_1h = 0
    warning_count_1h = 0
    log_path = LOG_DIR / "hub.log"
    if log_path.exists():
        try:
            cutoff = now.timestamp() - 3600
            with log_path.open(encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "ERROR" not in line and "WARNING" not in line:
                        continue
                    # Lines look like: "2026-04-27 02:13:45  WARN  hub: ..."
                    try:
                        ts_str = line[:19]
                        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                        if ts < cutoff:
                            continue
                    except ValueError:
                        continue
                    if "ERROR" in line:
                        error_count_1h += 1
                    elif "WARNING" in line:
                        warning_count_1h += 1
        except Exception as e:
            logger.warning("hub/health log scan failed: %s", e)

    # Recent audit (last 5 entries)
    from audit import tail
    recent_audit = tail(5)

    # Log file sizes
    def _size_kb(p: Path) -> int:
        return int(p.stat().st_size / 1024) if p.exists() else 0

    # Active schedules
    sched_count = sum(1 for s in load_schedules() if s.get("enabled", True))

    # Project count
    project_count = len(load_config().get("projects", []))

    return jsonify({
        "started_at":       HUB_STARTED_AT.strftime("%Y-%m-%d %H:%M:%S"),
        "now":              now.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds":   up_seconds,
        "errors_last_hour":   error_count_1h,
        "warnings_last_hour": warning_count_1h,
        "active_schedules":   sched_count,
        "registered_projects": project_count,
        "log_sizes_kb": {
            "hub_log":      _size_kb(log_path),
            "audit_jsonl":  _size_kb(LOG_DIR / "audit.jsonl"),
            "schedule_log": _size_kb(SCHEDULE_LOG_FILE),
        },
        "recent_audit":  recent_audit,
        "auth_enabled":  bool(HUB_PASSWORD),
        "python":        sys.version.split()[0],
    })


@app.route("/api/config/notifications")
def api_config_notifications():
    """GET — return current notification config (webhooks + notify_on filter)."""
    n = load_config().get("notifications", {}) or {}
    return jsonify({
        "slack_webhook":   n.get("slack_webhook", ""),
        "teams_webhook":   n.get("teams_webhook", ""),
        "discord_webhook": n.get("discord_webhook", ""),
        "notify_on":       n.get("notify_on", ["fail", "error"]),
    })


@app.route("/api/config/notifications/save", methods=["POST"])
def api_config_notifications_save():
    """POST — save notification config + emit audit entry (without leaking webhook URLs)."""
    data = request.get_json(force=True) or {}
    notify_on = data.get("notify_on") or ["fail", "error"]
    if not isinstance(notify_on, list):
        return jsonify({"error": "notify_on must be a list"}), 400
    cfg = load_config()
    cfg["notifications"] = {
        "slack_webhook":   (data.get("slack_webhook") or "").strip(),
        "teams_webhook":   (data.get("teams_webhook") or "").strip(),
        "discord_webhook": (data.get("discord_webhook") or "").strip(),
        "notify_on":       notify_on,
    }
    save_config(cfg)
    audit("config.notifications.save",
          slack=bool(cfg["notifications"]["slack_webhook"]),
          teams=bool(cfg["notifications"]["teams_webhook"]),
          discord=bool(cfg["notifications"]["discord_webhook"]),
          notify_on=notify_on)
    return jsonify({"ok": True})


@app.route("/api/audit")
def api_audit():
    """GET — read recent audit entries.

    Query params:
        limit:   max entries to return (default 100, capped at 1000)
        action:  prefix filter, e.g. 'project.' returns project.add/update/remove
    """
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 1000))
    action_prefix = (request.args.get("action") or "").strip()

    from audit import tail
    entries = tail(limit * 5 if action_prefix else limit)  # over-fetch when filtering
    if action_prefix:
        entries = [e for e in entries if (e.get("action") or "").startswith(action_prefix)]
    entries = entries[-limit:]
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/audit/archive", methods=["POST"])
def api_audit_archive():
    """Trigger audit-log retention archiving on demand.

    Splits logs/audit.jsonl: entries newer than HUB_AUDIT_RETENTION_DAYS
    (default 90) stay in the live file; older entries get appended to
    logs/audit_archive/audit_YYYYMM.jsonl per-month files.

    Optional body: {"retention_days": N} to override the default for one run.
    Returns: {ok, kept, archived, archived_files, skipped}.
    """
    data = request.get_json(silent=True) or {}
    retention = data.get("retention_days")
    if retention is not None:
        try:
            retention = max(0, int(retention))
        except (TypeError, ValueError):
            return jsonify({"error": "retention_days must be a non-negative integer"}), 400
    from audit import archive_old_entries
    result = archive_old_entries(retention)
    audit("audit.archive", **{k: v for k, v in result.items() if k != "archived_files"})
    return jsonify({"ok": True, **result})
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/notifications/test", methods=["POST"])
def api_notifications_test():
    """Fire a test message to whatever webhook(s) are in the request body.
    Used by the settings UI — not persisted. Body: {slack_webhook?, teams_webhook?, discord_webhook?}."""
    data = request.json or {}
    try:
        results = _notify_webhooks(
            title="QA Hub Demo — test notification",
            body="หากเห็นข้อความนี้แสดงว่า webhook ทำงานถูกต้อง",
            level="info",
            config={**data, "notify_on": ["all"]},  # force send regardless of filter
        )
        return jsonify({"ok": True, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/schedules/notifications")
def api_schedules_notifications():
    items = list(_sched_notifications)
    _sched_notifications.clear()
    return jsonify(items)


@app.route("/api/schedules/log")
def api_schedules_log():
    if not SCHEDULE_LOG_FILE.exists():
        return jsonify({"lines": []})
    lines = SCHEDULE_LOG_FILE.read_text(encoding="utf-8").splitlines()
    return jsonify({"lines": lines[-100:]})   # last 100 lines


@app.route("/api/schedules/run-now", methods=["POST"])
def api_schedules_run_now():
    data = request.json or {}
    sid  = data.get("id")
    for sched in load_schedules():
        if sched["id"] == sid:
            threading.Thread(target=_run_scheduled, args=(sched,), daemon=True).start()
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


# ══════════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

HTML = (HUB_DIR / "templates" / "dashboard.html").read_text(encoding="utf-8")


@app.route("/favicon.ico")
def favicon():
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        b'<rect width="32" height="32" rx="7" fill="#1F3864"/>'
        b'<text x="16" y="23" text-anchor="middle" font-size="19" '
        b'font-family="sans-serif" font-weight="bold" fill="#70AD47">H</text>'
        b'</svg>'
    )
    return Response(svg, mimetype="image/svg+xml")


@app.route("/")
def index():
    return HTML


@app.route("/alpine-demo")
def alpine_demo():
    """PoC page — compare vanilla JS vs Alpine.js on the same feature.
    Separate from the main dashboard so it can be evaluated/removed safely."""
    return (HUB_DIR / "templates" / "alpine_demo.html").read_text(encoding="utf-8")


@app.route("/vue-demo")
def vue_demo():
    """PoC — Bug Tracker implemented in Vue 3 (CDN, no build step).
    Hits the real /api/bugs endpoints against _mock-full."""
    return (HUB_DIR / "templates" / "vue_demo.html").read_text(encoding="utf-8")


@app.route("/react-demo")
def react_demo():
    """PoC — Bug Tracker in React 19 (CDN + Babel-standalone, no build step).
    Same API + same UX as /vue-demo so the two can be compared directly."""
    return (HUB_DIR / "templates" / "react_demo.html").read_text(encoding="utf-8")


@app.route("/framework-comparison")
def framework_comparison():
    """Side-by-side comparison page — embeds both /vue-demo and /react-demo
    in iframes plus shows code samples for the same patterns."""
    return (HUB_DIR / "templates" / "framework_comparison.html").read_text(encoding="utf-8")


@app.route("/v2/", defaults={"subpath": ""})
@app.route("/v2/<path:subpath>")
def vue_app(subpath: str):
    """Serve the Vue 3 SPA (built by `cd frontend && npm run build`).
    All /v2/* paths return index.html — vue-router handles client-side routing.
    Static assets live at /static/dist/* and are served by Flask's normal
    static handler (vite.config.ts uses base: '/static/dist/')."""
    index = HUB_DIR / "static" / "dist" / "index.html"
    if not index.exists():
        return Response(
            "<h1>Vue v2 build not found</h1>"
            "<p>Run: <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code></p>"
            "<p>Then refresh this page.</p>",
            status=503,
            mimetype="text/html",
        )
    return Response(index.read_text(encoding="utf-8"), mimetype="text/html")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def _find_free_port(start: int = 8080, end: int = 8090) -> int:
    import socket
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free port in range {start}–{end}")


if __name__ == "__main__":
    import webbrowser, argparse

    parser = argparse.ArgumentParser(description="QA Hub Demo")
    parser.add_argument("--port",       type=int, default=None,  help="Port (default: auto 8080-8090)")
    parser.add_argument("--no-browser", action="store_true",     help="Don't open browser automatically")
    args = parser.parse_args()

    PORT = args.port if args.port else _find_free_port()

    # Kill existing server (if any)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
            else:
                os.kill(old_pid, signal.SIGTERM)
            time.sleep(0.5)
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)

    PID_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))

    print("=" * 58)
    print("  QA Hub Demo — Central Multi-Project Dashboard")
    print(f"  http://localhost:{PORT}" + ("" if PORT == 8080 else f"  (port 8080 busy → using {PORT})"))
    print(f"  Root: {ROOT_DIR}")
    print(f"  Config: {CONFIG_FILE}")

    # ── auth status ────────────────────────────────────────────────────
    if HUB_PASSWORD:
        print(f"  🔐 BasicAuth enabled (username: {HUB_USERNAME!r})")
    else:
        print("  ⚠  BasicAuth disabled — set HUB_PASSWORD env var to require login")

    # ── config validation: warn loudly instead of failing at request time ──
    _cfg_errors = validate_config(load_config())
    if _cfg_errors:
        print(f"  ⚠ config.json has {len(_cfg_errors)} validation issue(s):")
        for _e in _cfg_errors:
            print(f"      - {_e}")
        print("      Fix via UI (Projects → Edit) or edit config.json directly")

    # ── scaffold validation: catch broken Word templates BEFORE they get
    # copied into a fresh project. Past incident: a downloaded v2_1 template
    # had duplicate w:styleId + missing core styles → python-docx parsed it
    # fine but Word refused to open the resulting reports.
    from pathlib import Path as _P
    from validators import validate_scaffolds as _validate_scaffolds
    _scaffold_errors = _validate_scaffolds(_P(__file__).parent / "scaffold")
    if _scaffold_errors:
        print(f"  ⚠ scaffold has {len(_scaffold_errors)} template issue(s):")
        for _e in _scaffold_errors:
            print(f"      - {_e}")
        print("      Restore from a backup or refresh scaffold — broken")
        print("      templates here will propagate to every new project.")

    # ── secret storage advisory ────────────────────────────────────────
    _email_cfg = load_config().get("email", {})
    _smtp_in_cfg   = bool(_email_cfg.get("smtp_pass"))
    _resend_in_cfg = bool(_email_cfg.get("resend_api_key"))
    _smtp_env      = bool(os.environ.get("HUB_SMTP_PASS"))
    _resend_env    = bool(os.environ.get("HUB_RESEND_API_KEY"))
    if (_smtp_in_cfg and not _smtp_env) or (_resend_in_cfg and not _resend_env):
        print("  ⚠ email secret stored in config.json — consider:")
        if _smtp_in_cfg and not _smtp_env:
            print("      set HUB_SMTP_PASS env var + clear smtp_pass in config.json")
        if _resend_in_cfg and not _resend_env:
            print("      set HUB_RESEND_API_KEY env var + clear resend_api_key in config.json")
    elif _smtp_env or _resend_env:
        print(f"  ✓ email secrets from env var (smtp={_smtp_env}, resend={_resend_env})")

    print("  💡 Tip: รัน /hub-structure-check เป็นระยะ เพื่อจับ structure drift ก่อนสะสม")
    print("  กด Ctrl+C เพื่อหยุด")
    print("=" * 58)

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(port=PORT, debug=False, threaded=True)
