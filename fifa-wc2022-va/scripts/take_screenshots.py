"""
Capture screenshots of all 12 visualizations for the README.
Requires: pip install playwright && python -m playwright install chromium
Run the app first: streamlit run app.py
"""
import time, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
OUT_DIR = Path(__file__).parent.parent / "docs" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def wait_idle(page, extra=3):
    page.wait_for_load_state("networkidle")
    time.sleep(extra)


def click_tab(page, label):
    page.locator(f"button:has-text('{label}')").first.click()
    time.sleep(1)


def select_sidebar_box(page, label_text, option_text):
    box = page.locator(
        f'[data-testid="stSelectbox"]:has(label:has-text("{label_text}"))'
        f' [data-baseweb="select"]'
    ).first
    box.click()
    time.sleep(0.4)
    page.keyboard.type(option_text, delay=40)
    time.sleep(0.5)
    option = page.locator(f'[role="option"]:has-text("{option_text}")').first
    option.wait_for(state="visible", timeout=5000)
    option.click()
    time.sleep(0.4)


def scroll_to_heading(page, heading_text):
    """Scroll so the section heading is near the top of the viewport."""
    page.evaluate(f"""
        const els = Array.from(document.querySelectorAll('h3, h2, h1, p'));
        const el = els.find(e => e.innerText && e.innerText.includes({repr(heading_text)}));
        if (el) el.scrollIntoView({{behavior: 'instant', block: 'start'}});
    """)
    time.sleep(0.8)


def scroll_to_nth_plot(page, n):
    page.evaluate(f"""
        const charts = document.querySelectorAll('.js-plotly-plot');
        if (charts[{n}]) {{
            charts[{n}].scrollIntoView({{behavior: 'instant', block: 'center'}});
        }}
    """)
    time.sleep(0.8)


def count_plots(page):
    return page.evaluate("document.querySelectorAll('.js-plotly-plot').length")


def shot(page, filename, plot_index=None, heading=None):
    if heading:
        scroll_to_heading(page, heading)
    elif plot_index is not None:
        scroll_to_nth_plot(page, plot_index)
    path = str(OUT_DIR / filename)
    page.screenshot(path=path, full_page=False)
    print(f"  saved {filename}")


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            viewport={"width": 1400, "height": 900}
        ).new_page()

        print(f"Opening {BASE_URL} ...")
        page.goto(BASE_URL, timeout=30000)
        wait_idle(page, 7)

        # ── Tab 1: Tournament ─────────────────────────────────────────
        print("Tab 1 — Tournament")
        click_tab(page, "Tournament")
        wait_idle(page, 4)
        shot(page, "tab1_bracket.png",    heading="Knockout Bracket")
        shot(page, "tab1_xg_scatter.png", heading="xG vs Goals")

        # ── Select the Argentina vs France Final in the sidebar ───────
        print("  Selecting match: Argentina 3-3 France (Final)")
        select_sidebar_box(page, "Match", "Argentina")
        wait_idle(page, 6)

        # ── Tab 2: Match ──────────────────────────────────────────────
        print("Tab 2 — Match")
        click_tab(page, "Match")
        wait_idle(page, 6)

        n = count_plots(page)
        print(f"  Found {n} Plotly charts on Match tab")

        # Actual DOM render order: Momentum → Passing Network → Shot Map × 2 → Scrubber
        shot(page, "tab2_momentum.png",        heading="Match Momentum")
        shot(page, "tab2_passing_network.png", heading="Passing Network")
        shot(page, "tab2_shot_map.png",        heading="Shot Map")
        # Scrubber appears after Shot Map
        shot(page, "tab2_scrubber.png",        heading="Animated Time")

        # ── Select Argentina + Messi ──────────────────────────────────
        print("  Selecting team: Argentina, player: Messi")
        select_sidebar_box(page, "Team", "Argentina")
        wait_idle(page, 2)
        select_sidebar_box(page, "Player", "Messi")
        wait_idle(page, 5)

        # ── Tab 3: Player ─────────────────────────────────────────────
        print("Tab 3 — Player")
        click_tab(page, "Player")
        wait_idle(page, 6)
        shot(page, "tab3_heatmap.png",     heading="Action Density")
        shot(page, "tab3_progressive.png", heading="Progressive Pass")
        shot(page, "tab3_3d_shots.png",    heading="3D Shot")
        shot(page, "tab3_goalmouth.png",   heading="Goalmouth")

        # ── Tab 4: Tactical ───────────────────────────────────────────
        print("Tab 4 — Tactical")
        click_tab(page, "Tactical")
        wait_idle(page, 6)
        shot(page, "tab4_voronoi.png", heading="Voronoi")
        shot(page, "tab4_xt.png",      heading="Expected Threat")

        browser.close()
        print(f"\nAll 12 screenshots saved to {OUT_DIR}")


if __name__ == "__main__":
    run()
