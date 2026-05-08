"""AI provider abstraction — wraps either Claude CLI (default) or
the Anthropic API (opt-in) behind a single generate(prompt) call.

Why both?
- CLI: zero extra cost / no API key needed. Uses the user's existing
  Claude Code subscription. Slower (subprocess overhead) but free.
- API: faster, scriptable, parallelizable. Requires ANTHROPIC_API_KEY
  and metered cost.

Config (in config.json under "ai"):
    "ai": {
        "provider": "cli" | "api",     // default "cli"
        "model":    "claude-opus-4-7", // optional, provider-specific
        "api_key":  ""                 // ApiProvider falls back to env var ANTHROPIC_API_KEY
    }

Failure modes are surfaced as RuntimeError with a human-readable message
so the API endpoint can return a clean 4xx/5xx instead of a stack trace.
"""
import os
import shutil
import subprocess
from typing import Any

CLAUDE_CLI_TIMEOUT = 120  # seconds — generous; long requirements take a while


class AIProviderError(RuntimeError):
    """Raised when the underlying provider can't fulfil a request."""


def _cli_generate(prompt: str, model: str | None = None) -> str:
    """Run `claude -p <prompt>` and return stdout."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise AIProviderError(
            "Claude CLI not found in PATH. Install Claude Code or switch provider to 'api'."
        )
    cmd = [claude_bin, "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise AIProviderError(f"Claude CLI timed out after {CLAUDE_CLI_TIMEOUT}s")
    if result.returncode != 0:
        raise AIProviderError(
            f"Claude CLI returned code {result.returncode}: {result.stderr.strip() or 'no stderr'}"
        )
    out = (result.stdout or "").strip()
    if not out:
        raise AIProviderError("Claude CLI returned empty output")
    return out


def _api_generate(prompt: str, api_key: str, model: str | None = None) -> str:
    """Call the Anthropic API. Imports the SDK lazily so users on the CLI
    path don't pay the cold-import cost."""
    if not api_key:
        raise AIProviderError(
            "API provider selected but no API key configured. Set ANTHROPIC_API_KEY env var "
            "or fill it in About → AI Settings."
        )
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise AIProviderError(
            "Anthropic SDK not installed. Run: pip install anthropic"
        )
    client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = client.messages.create(
            model=model or "claude-opus-4-7",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise AIProviderError(f"Anthropic API call failed: {e}")
    # Concatenate text blocks
    parts: list[str] = []
    for block in msg.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts).strip()


def generate(prompt: str, config: dict | None = None) -> dict[str, Any]:
    """Provider-agnostic entry point. Returns:
        {"provider": "cli"|"api", "model": str, "output": str}
    Raises AIProviderError on any failure."""
    config = config or {}
    provider = (config.get("provider") or "cli").lower()
    model = config.get("model") or None

    if provider == "cli":
        out = _cli_generate(prompt, model=model)
    elif provider == "api":
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        out = _api_generate(prompt, api_key=api_key, model=model)
    else:
        raise AIProviderError(f"Unknown ai.provider={provider!r} — expected 'cli' or 'api'")

    return {"provider": provider, "model": model or "default", "output": out}


# ── Prompt builders ─────────────────────────────────────────────────────────

TEST_PLAN_PROMPT_TEMPLATE = """You are helping a QA team draft a Test Case Matrix (TCM) from a requirement document.

Project context: {project_name} (type: {project_type})

Requirement:
{requirement}

Produce a draft test plan in markdown with:
1. Test scenarios (TS_001 ... TS_NNN), each with:
   - title (short)
   - precondition
   - steps (numbered)
   - expected_result
2. Coverage notes — which requirements are covered, which are not
3. Risk assessment — what could go wrong, what edge cases need attention

Keep it actionable. The QA reviewer will edit this draft, not blindly trust it.
"""


def build_test_plan_prompt(requirement: str, project_name: str = "", project_type: str = "") -> str:
    return TEST_PLAN_PROMPT_TEMPLATE.format(
        requirement=requirement.strip(),
        project_name=project_name or "(unnamed)",
        project_type=project_type or "full-pipeline",
    )


# ── A2 — Smart release summary ──────────────────────────────────────────────
RELEASE_SUMMARY_PROMPT = """You are summarizing a software release-readiness report for non-technical stakeholders (product manager, team lead, customer-facing roles).

Project: {project_name} ({project_type})
Phase:   {phase}
Verdict: {verdict}

Pass/fail breakdown (criteria):
{criteria_block}

Open bugs: {open_bugs} ({open_critical} Critical, {open_high} High)
Recent test runs: {pass_rate}% pass rate over last {runs} runs

Write a 4-6 sentence summary in Thai (use English for technical terms). Cover:
1. The verdict in plain language — what it means for shipping
2. The 1-2 most important blocking issues (if any), explained simply
3. What needs to happen next, prioritized
4. Confidence level / risk in one sentence

Tone: factual, calm, decision-oriented. Don't list every criterion — focus on the signal that drives the decision."""


def build_release_summary_prompt(*, project_name: str, project_type: str, phase: str,
                                 verdict: str, criteria: list, open_bugs: int,
                                 open_critical: int, open_high: int,
                                 pass_rate: int | None, runs: int) -> str:
    """Build the prompt fed to the AI provider for /api/ai/release-summary.
    Pure data → string transform; tested in isolation."""
    crit_lines = []
    for c in criteria:
        icon = "PASS" if c.get("ok") else ("WARN" if c.get("warn") else "FAIL")
        crit_lines.append(f"  [{icon}] {c.get('label', '')}: {c.get('detail', '')}")
    return RELEASE_SUMMARY_PROMPT.format(
        project_name=project_name or "(unnamed)",
        project_type=project_type or "full-pipeline",
        phase=phase or "active",
        verdict=verdict or "UNKNOWN",
        criteria_block="\n".join(crit_lines) if crit_lines else "  (no criteria)",
        open_bugs=open_bugs,
        open_critical=open_critical,
        open_high=open_high,
        pass_rate=pass_rate if pass_rate is not None else "n/a",
        runs=runs,
    )


# ── A1 — AI bug triage ──────────────────────────────────────────────────────
BUG_TRIAGE_PROMPT = """You are helping a QA engineer triage a newly-reported bug. The output must be valid JSON only — no prose, no markdown fences, just one JSON object.

New bug report:
Title: {title}
Description:
{description}

Existing open bugs in this project (id, title):
{existing_block}

Return JSON with these exact fields:
{{
  "severity": "Critical" | "High" | "Medium" | "Low",
  "severity_reason": "<one sentence in Thai explaining the choice>",
  "tags": [<0-4 short keyword strings, lowercase, derived from the description>],
  "similar": [<bug ids from the existing list that look like duplicates or close variants — empty if none>]
}}

Severity guideline:
- Critical: ระบบใช้ไม่ได้ / data loss / security vuln
- High: feature สำคัญพัง, blocks workflow
- Medium: ทำได้ workaround, minor inconvenience
- Low: cosmetic / typo / polish

Be conservative on severity (when in doubt go one level lower) and on similar (only flag clear matches)."""


def build_bug_triage_prompt(*, title: str, description: str, existing: list) -> str:
    """Build the AI bug-triage prompt. existing = list of {id, title} dicts
    for the open bugs in the same project; capped at 30 to keep the prompt
    bounded."""
    if existing:
        lines = [f"  - {b.get('id', '?')}: {b.get('title', '')[:120]}" for b in existing[:30]]
        existing_block = "\n".join(lines)
    else:
        existing_block = "  (none)"
    return BUG_TRIAGE_PROMPT.format(
        title=title.strip() or "(untitled)",
        description=description.strip() or "(no description)",
        existing_block=existing_block,
    )
