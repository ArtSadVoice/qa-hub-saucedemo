"""Chat notifications — Slack, Microsoft Teams, Discord.

All three use inbound webhooks with slightly different payload shapes.
This module normalises them behind a single `notify(title, body, level)`
call. Failures are swallowed: a broken webhook must not crash a
scheduled run or mutate API behaviour.

Config lives under `notifications` in config.json:
    "notifications": {
        "slack_webhook":   "https://hooks.slack.com/services/...",
        "teams_webhook":   "https://outlook.office.com/webhook/...",
        "discord_webhook": "https://discord.com/api/webhooks/...",
        "notify_on":       ["fail", "error"]   // or ["all"] / ["fail"]
    }

`notify_on` controls which events fire (see should_notify()). Default
is ["fail", "error"] — don't spam on green.
"""
import json
import logging
import urllib.request
from typing import Any

_logger = logging.getLogger("hub.notify")

# ── Level → color mapping for each service ────────────────────────────────
# Slack attachments + Discord embeds take hex colours; Teams theme colour is 6-char hex.
_COLORS = {
    "ok":    "#36a64f",  # green
    "info":  "#439fe0",  # blue
    "warn":  "#ffcc00",  # amber
    "fail":  "#e05252",  # red
    "error": "#b71c1c",  # dark red
}
_EMOJIS = {"ok": "✅", "info": "ℹ️", "warn": "⚠️", "fail": "❌", "error": "🔥"}


def should_notify(level: str, notify_on: list[str] | None) -> bool:
    """Check whether a message at `level` should fire given the notify_on filter.
    Defaults to ['fail', 'error'] when notify_on is missing/empty."""
    rules = notify_on or ["fail", "error"]
    if "all" in rules:
        return True
    return level in rules


def _post_json(url: str, payload: dict[str, Any], timeout: float = 5.0) -> bool:
    """POST a JSON body to a webhook. Returns True on 2xx; logs and returns
    False on anything else — never raises to the caller."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                _logger.warning("webhook %s → HTTP %s", url[:60], resp.status)
            return ok
    except Exception as e:
        _logger.warning("webhook %s failed: %s", url[:60], e)
        return False


# ── Service-specific payload builders ─────────────────────────────────────

def _slack_payload(title: str, body: str, level: str) -> dict:
    emoji = _EMOJIS.get(level, "ℹ️")
    return {
        "attachments": [{
            "color": _COLORS.get(level, "#439fe0"),
            "title": f"{emoji} {title}",
            "text":  body,
            "mrkdwn_in": ["text"],
        }]
    }


def _teams_payload(title: str, body: str, level: str) -> dict:
    """MessageCard format — simpler than Adaptive Cards and works on most
    Teams webhook endpoints."""
    emoji = _EMOJIS.get(level, "ℹ️")
    color = _COLORS.get(level, "#439fe0").lstrip("#")
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": color,
        "summary": title,
        "title":   f"{emoji} {title}",
        "text":    body,
    }


def _discord_payload(title: str, body: str, level: str) -> dict:
    """Discord takes a decimal (not hex) color. Convert here."""
    emoji = _EMOJIS.get(level, "ℹ️")
    color_hex = _COLORS.get(level, "#439fe0").lstrip("#")
    try:
        color_dec = int(color_hex, 16)
    except ValueError:
        color_dec = 0x439FE0
    return {
        "embeds": [{
            "title":       f"{emoji} {title}",
            "description": body,
            "color":       color_dec,
        }]
    }


def notify(title: str, body: str, level: str = "info", config: dict | None = None) -> dict:
    """Send `title` + `body` to every configured webhook.

    Returns a per-service {service: bool} status map for callers that care.
    When config is None, it's loaded fresh from config.json (lazy import to
    avoid a circular dependency with app.py at module-load time).

    level drives both the coloured stripe/emoji and the filter logic —
    messages below the `notify_on` threshold are skipped silently.
    """
    if config is None:
        from app import load_config
        config = load_config().get("notifications", {}) or {}

    results = {"slack": None, "teams": None, "discord": None}

    if not should_notify(level, config.get("notify_on")):
        return results

    if config.get("slack_webhook"):
        results["slack"] = _post_json(config["slack_webhook"], _slack_payload(title, body, level))
    if config.get("teams_webhook"):
        results["teams"] = _post_json(config["teams_webhook"], _teams_payload(title, body, level))
    if config.get("discord_webhook"):
        results["discord"] = _post_json(config["discord_webhook"], _discord_payload(title, body, level))

    return results
