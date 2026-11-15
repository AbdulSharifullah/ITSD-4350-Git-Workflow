"""Render the maintained SVG diagram as a submission PNG."""
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent
target = root / 'evidence'
target.mkdir(exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1200, 'height': 760})
    page.goto((root / 'architecture.svg').as_uri())
    page.screenshot(path=str(target / 'architecture.png'))
    browser.close()
