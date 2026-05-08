"""Flakiness analysis over run_history entries.

Pure domain logic — no Flask. Exposed via /api/flakiness in app.py.

Input: a list of run entries (filtered to one project's 'tests' step).
Output: a summary dict with counts, rates, fail clusters, and a verdict.

The verdict classifies the project at a glance:
- stable: < 5% failure rate and last run passed
- warn:   5–20% failure rate
- flaky:  > 20% failure rate OR flaky field > 0 in > 10% of runs
- broken: last 3+ consecutive runs all failed

The point is not perfect classification — it's a signal strong enough
that someone scanning the dashboard knows where to look.
"""
from typing import Any

# Thresholds — tuned for small teams. Tweak in one place if needed.
BROKEN_CONSECUTIVE_FAILS = 3
FLAKY_FAIL_RATE_PCT      = 20
WARN_FAIL_RATE_PCT       = 5


def _is_failure(entry: dict) -> bool:
    """A run counts as a failure if it has any fail and no error-code wrap."""
    return int(entry.get("fail", 0)) > 0


def _run_pass_rate(entry: dict) -> float | None:
    p = int(entry.get("pass", 0))
    f = int(entry.get("fail", 0))
    tot = p + f
    return round(p / tot * 100, 1) if tot else None


def _fail_clusters(runs: list[dict]) -> list[dict]:
    """Return consecutive-failure spans as {start_ts, end_ts, length}.
    A cluster of length 1 means an isolated failure; longer = more serious."""
    clusters = []
    cur: dict | None = None
    for r in runs:
        if _is_failure(r):
            if cur is None:
                cur = {"start_ts": r.get("ts"), "end_ts": r.get("ts"), "length": 1}
            else:
                cur["end_ts"] = r.get("ts")
                cur["length"] += 1
        else:
            if cur is not None:
                clusters.append(cur)
                cur = None
    if cur is not None:
        clusters.append(cur)
    return clusters


def _verdict(runs: list[dict], fail_rate_pct: float, flaky_runs: int) -> tuple[str, str]:
    """Return (verdict, reason). Ordered from most severe to least so we
    stop at the first match."""
    if not runs:
        return ("unknown", "no runs in window")

    # Broken: N consecutive failures at the tail
    tail = runs[-BROKEN_CONSECUTIVE_FAILS:]
    if len(tail) >= BROKEN_CONSECUTIVE_FAILS and all(_is_failure(r) for r in tail):
        return ("broken", f"last {BROKEN_CONSECUTIVE_FAILS} consecutive runs all failed")

    # Flaky: high fail rate OR flaky counter non-zero often
    flaky_ratio = flaky_runs / len(runs) if runs else 0
    if fail_rate_pct > FLAKY_FAIL_RATE_PCT:
        return ("flaky", f"failure rate {fail_rate_pct}% > {FLAKY_FAIL_RATE_PCT}%")
    if flaky_ratio > 0.10:
        return ("flaky", f"flaky counter non-zero in {flaky_ratio * 100:.0f}% of runs")

    if fail_rate_pct >= WARN_FAIL_RATE_PCT:
        return ("warn", f"failure rate {fail_rate_pct}% within warn band")

    return ("stable", "no failures beyond warn threshold")


def analyse(entries: list[dict], window: int = 20) -> dict[str, Any]:
    """Summarise the last `window` test-step runs for one project.

    Caller should filter entries to project_id + step='tests' before calling.
    Entries should be in oldest-first order (matches run_history.json insertion order).
    """
    runs = entries[-window:]
    total = len(runs)
    failed = sum(1 for r in runs if _is_failure(r))
    passed = total - failed
    flaky_runs = sum(1 for r in runs if int(r.get("flaky", 0)) > 0)

    tests_pass = sum(int(r.get("pass", 0)) for r in runs)
    tests_fail = sum(int(r.get("fail", 0)) for r in runs)
    tests_total = tests_pass + tests_fail

    fail_rate_pct = round(failed / total * 100, 1) if total else 0
    pass_rate_tests = round(tests_pass / tests_total * 100, 1) if tests_total else None

    clusters = _fail_clusters(runs)
    verdict, reason = _verdict(runs, fail_rate_pct, flaky_runs)

    last_run = runs[-1] if runs else None
    last_status = "pass" if last_run and not _is_failure(last_run) else "fail" if last_run else None

    return {
        "window_size":     window,
        "runs_in_window":  total,
        "passed_runs":     passed,
        "failed_runs":     failed,
        "flaky_runs":      flaky_runs,
        "fail_rate_pct":   fail_rate_pct,
        "tests_total":     tests_total,
        "tests_passed":    tests_pass,
        "tests_failed":    tests_fail,
        "pass_rate_tests": pass_rate_tests,
        "fail_clusters":   clusters,
        "last_status":     last_status,
        "last_ts":         last_run.get("ts") if last_run else None,
        "verdict":         verdict,          # stable | warn | flaky | broken | unknown
        "verdict_reason":  reason,
    }
