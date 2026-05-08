"""
explore_survey.py — Survey path exploration via Claude + Playwright MCP

Usage:
    python scripts/explore_survey.py              # reads BASE_URL from CLAUDE.md
    python scripts/explore_survey.py <URL>        # explicit URL
"""

import sys, io, os, re, subprocess, tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent


def get_base_url():
    claude_md = PROJECT_ROOT / "CLAUDE.md"
    if claude_md.exists():
        m = re.search(r'Base URL.*?`([^`]+)`', claude_md.read_text(encoding="utf-8"), re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else get_base_url()
    if not url:
        print("Error: No URL provided and BASE_URL not found in CLAUDE.md")
        sys.exit(1)

    explore_cmd = PROJECT_ROOT / ".claude" / "commands" / "explore.md"
    if not explore_cmd.exists():
        print("Error: .claude/commands/explore.md not found — run /explore from Claude Code first")
        sys.exit(1)

    system_prompt = explore_cmd.read_text(encoding="utf-8")
    prompt_text = f"{system_prompt}\n\n---\n\nExplore this survey URL: {url}"

    print(f"▶ Exploring survey: {url}")
    print("  Using Playwright MCP to walk all branch paths...")
    print("  Output: requirements/survey_map.md + FLOW.md")
    print()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt_text)
        tmp_path = f.name

    try:
        with open(tmp_path, "r", encoding="utf-8") as f:
            proc = subprocess.Popen(
                ["claude", "--dangerously-skip-permissions", "-p"],
                stdin=f,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=str(PROJECT_ROOT),
            )
        for line in proc.stdout:
            print(line, end="", flush=True)
        proc.wait()
        sys.exit(proc.returncode)
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
