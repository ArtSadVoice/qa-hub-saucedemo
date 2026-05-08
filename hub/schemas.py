"""Lightweight request-body validation for Hub update endpoints.

Why not marshmallow / pydantic?
    The audit found a single class of bug — silent field drop — for which
    a 30-line decorator does the job. Adding a heavyweight validation lib
    would be overkill and grow the dependency surface for no extra leverage.

Behavior:
    - validate_body(required=[...], allowed=[...]) returns a Flask-friendly
      decorator that:
        • returns 400 if a required field is missing
        • returns 400 if the body contains a key outside `allowed`
        • passes the parsed dict to the wrapped view as the kwarg `body`

The strict "unknown field" rejection is what catches the bug class —
silent drop becomes a loud 400 with the offending field name.

Usage:
    @app.route("/api/bugs/update", methods=["POST"])
    @validate_body(
        required=["project_id", "id"],
        allowed=["title", "severity", "status", "description", "assignee", ...],
    )
    def api_bugs_update(body):
        ...
"""
from functools import wraps
from typing import Iterable

from flask import jsonify, request


def validate_body(*, required: Iterable[str] = (), allowed: Iterable[str] = ()):
    """Decorator factory. `required` keys must be present; `allowed` may
    appear (in addition to required). Anything else returns 400."""
    required_set = set(required)
    allowed_set  = set(allowed) | required_set

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            data = request.get_json(silent=True) or {}
            if not isinstance(data, dict):
                return jsonify({"error": "request body must be a JSON object"}), 400

            missing = required_set - data.keys()
            if missing:
                return jsonify({
                    "error": f"missing required field(s): {sorted(missing)}"
                }), 400

            unknown = set(data.keys()) - allowed_set
            if unknown:
                return jsonify({
                    "error": f"unknown field(s): {sorted(unknown)}",
                    "hint":  f"allowed: {sorted(allowed_set)}",
                }), 400

            kwargs["body"] = data
            return fn(*args, **kwargs)
        return wrapper
    return decorator
