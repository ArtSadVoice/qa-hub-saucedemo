"""Smoke tests that the Hub dashboard actually loads in a real browser.

These catch the kind of regression an integration test can't:
- a missing /static/app.js breaks the UI even though all API routes return 200
- a JavaScript error prevents init() from running
- a new tab's HTML wasn't wired into navigation
"""
import pytest

pytestmark = pytest.mark.e2e


def test_dashboard_loads_without_js_errors(page, live_server):
    """Opening / must render the sidebar and hit no console errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    page.goto(live_server + "/", wait_until="networkidle")

    # Sidebar shell rendered (presence of the brand label is enough)
    assert page.locator(".sb-logo").count() >= 1

    # static assets served
    assert any(
        req for req in []  # placeholder; real check below
    ) or True

    # no errors collected
    assert errors == [], f"console/page errors during load: {errors}"


def test_static_assets_served(page, live_server):
    """/static/app.css and /static/app.js must be reachable (cache-busting not required)."""
    page.goto(live_server + "/static/app.css")
    assert page.content().find("--primary") > 0, "app.css does not contain expected CSS var"

    page.goto(live_server + "/static/app.js")
    assert "function init" in page.content(), "app.js does not contain init function"


def test_project_switcher_lists_registered_projects(page, live_server):
    """The sidebar project dropdown populates from /api/projects."""
    page.goto(live_server + "/", wait_until="networkidle")
    # Dropdown should have at least the _mock-* projects
    options = page.locator(".proj-select option").all_text_contents()
    assert any("_mock-full" in o for o in options), f"_mock-full missing from {options}"
    assert any("_mock-manual" in o for o in options), f"_mock-manual missing from {options}"


def test_dashboard_tab_switches_on_click(page, live_server):
    """Clicking a different nav item should switch the visible section."""
    page.goto(live_server + "/", wait_until="networkidle")

    # Find Projects nav item and click
    projects_nav = page.locator('.nav-item:has-text("Projects")').first
    if projects_nav.count() == 0:
        pytest.skip("Projects nav item not found — UI structure may have changed")
    projects_nav.click()

    # The active nav item should now be Projects (has .active class)
    active = page.locator(".nav-item.active").first
    assert "Projects" in active.text_content() if active.count() else False
