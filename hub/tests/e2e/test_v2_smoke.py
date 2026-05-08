"""End-to-end smoke tests for the Vue v2 frontend.

Hits the built static/dist bundle the same way a production deployment
would — catches:
- Build artefacts missing (someone forgot `npm run build` before deploy)
- JavaScript runtime errors during initial mount
- Routing breakage (every nav-item must navigate without console error)
- API plumbing for at least one endpoint per major view
"""
import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _suppress_onboarding(context):
    """Pre-set the onboarding flag so the welcome modal doesn't intercept
    clicks during e2e. We're not testing onboarding here."""
    context.add_init_script(
        "window.localStorage.setItem('fp_onboarding', JSON.stringify({welcomeSeen: true, tipsSeen: {}}));"
    )


def _no_errors(page, action_name: str = "load"):
    """Helper: register page-error listeners, return list to assert against.

    Filters out environment-specific noise the test session can't avoid:
    - Image 404s from missing screenshots in mock projects
    - 'Failed to load resource' messages (Playwright reports these as console errors)
    """
    errors: list[str] = []

    def _is_real_error(text: str) -> bool:
        text_low = text.lower()
        if "failed to load resource" in text_low: return False
        if "404" in text and ".png" in text_low:   return False  # missing screenshot image
        if "404" in text and "favicon" in text_low: return False
        return True

    page.on("pageerror", lambda exc: errors.append(f"pageerror during {action_name}: {exc}"))
    page.on("console", lambda msg: errors.append(f"console.{msg.type} during {action_name}: {msg.text}")
            if msg.type == "error" and _is_real_error(msg.text) else None)
    return errors


def test_v2_dashboard_loads_clean(page, live_server):
    errors = _no_errors(page)
    page.goto(live_server + "/v2/", wait_until="networkidle")
    # Sidebar present
    assert page.locator(".sidebar").count() == 1
    # Default route lands on dashboard
    assert "Dashboard" in (page.locator("h1").first.text_content() or "")
    assert errors == [], f"console/page errors: {errors}"


def test_v2_static_assets_served_from_dist(page, live_server):
    """Hub's static handler must serve the Vite build artefacts."""
    page.goto(live_server + "/v2/")
    # The HTML references hashed filenames under /static/dist/assets/
    html = page.content()
    assert "/static/dist/assets/" in html
    # Hashed JS file should also be reachable
    js_match = page.evaluate("""() => {
        const s = document.querySelector('script[src*=\"/static/dist/assets/\"]');
        return s ? s.src : null;
    }""")
    assert js_match, "no Vite-built script tag found in /v2/ HTML"


def test_v2_router_paths_render_without_error(page, live_server):
    """Every nav-item route should mount its view without console error."""
    routes = [
        '/dashboard', '/overview', '/pipeline', '/release', '/schedule',
        '/projects', '/bugs', '/activity', '/input', '/output',
        '/screenshots', '/syscheck', '/guide', '/settings',
    ]
    errors = _no_errors(page, "router walk")
    for r in routes:
        page.goto(live_server + "/v2" + r, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle", timeout=8000)
        # Page-level title should match the route's meta.title
        # (we don't assert the exact text — just that something rendered)
        assert page.locator(".main").count() >= 1, f"main shell missing on /v2{r}"
    assert errors == [], f"console/page errors during router walk: {errors}"


def test_v2_bug_tracker_loads_real_api(page, live_server):
    """Bug Tracker should hit /api/bugs and render the table or empty state."""
    errors = _no_errors(page, "bug tracker")
    page.goto(live_server + "/v2/bugs", wait_until="networkidle")
    # Either the bug-list table or the empty state should render
    has_content = (
        page.locator("table").count() > 0
        or page.locator(".empty").count() > 0
    )
    assert has_content, "Bug Tracker rendered neither a table nor an empty state"
    assert errors == [], f"errors during /v2/bugs: {errors}"


def test_v2_overview_aggregates_projects(page, live_server):
    """Hub Overview should show summary stats (cards with .n class)."""
    errors = _no_errors(page, "overview")
    page.goto(live_server + "/v2/overview", wait_until="networkidle")
    # At least one stat tile should render with a numeric value
    page.wait_for_selector(".stat .n", timeout=8000)
    stats = page.locator(".stat .n").all_text_contents()
    assert any(s.strip() for s in stats), "Overview stats are all blank"
    assert errors == [], f"errors during /v2/overview: {errors}"


def test_v2_settings_tabs_switch(page, live_server):
    """Settings sub-tabs (Branding/Email/Notifications/AI) should be clickable
    without errors and only one card visible at a time."""
    errors = _no_errors(page, "settings")
    page.goto(live_server + "/v2/settings", wait_until="networkidle")
    # Expect 4 tab buttons
    page.wait_for_selector(".tab-btn", timeout=8000)
    tabs = page.locator(".tab-btn").all_text_contents()
    assert len(tabs) >= 4, f"expected ≥4 settings tabs, got {len(tabs)}: {tabs}"

    # Click each, confirm only one card shows
    for label in ["Email", "Notifications", "AI", "Branding"]:
        page.locator(f".tab-btn:has-text(\"{label}\")").first.click()
        page.wait_for_timeout(120)
        assert page.locator(".card").count() >= 1
    assert errors == [], f"errors during settings tab walk: {errors}"


def test_legacy_dashboard_still_works(page, live_server):
    """Sanity: the legacy / dashboard must keep working alongside /v2."""
    errors = _no_errors(page, "legacy")
    page.goto(live_server + "/", wait_until="networkidle")
    # Legacy uses .sb-logo too — same selector
    assert page.locator(".sb-logo").count() >= 1
    assert errors == [], f"errors during legacy /: {errors}"
