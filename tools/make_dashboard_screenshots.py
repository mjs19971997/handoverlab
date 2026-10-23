# SPDX-License-Identifier: MIT
"""Take the dashboard screenshots shown in the README and the dashboard guide (docs/images).

docs/images/dashboard.png is the Map tab after a run, docs/images/dashboard-charts.png the Charts tab.  The run
uses the settings of tools/make_readme_images.py: street grid, 2 blocks per side, 150 m site spacing, 30 users
(veh16), 60 s with 10 s warm-up, 5 seeds from seed 1, rules A3 (3 dB, 0.16 s) and CHO (-2 / 3 dB, 0.08 s).

The browser is Microsoft Edge or Chrome in headless mode, driven through the Chrome DevTools Protocol with the
websocket client of the ``websockets`` package (a dependency of Streamlit).  Start the dashboard first, then:

    handoverlab gui --port 8611 --headless
    python tools/make_dashboard_screenshots.py --url http://localhost:8611 --browser "C:/.../msedge.exe"

The run takes about two minutes.  The screenshots are 1440 x 1080 pixels.
"""
import argparse
import base64
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from websockets.sync.client import connect

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "images")
WIDTH, HEIGHT = 1440, 1080
#: slider label -> value of the run (the other widgets keep their defaults, which match the run)
SLIDERS = {"Users": 30, "Run length [s]": 60, "Seeds": 5}
KEYS = {"ArrowRight": 39, "ArrowLeft": 37}


class Page:
    """A minimal Chrome DevTools Protocol client for one page."""

    def __init__(self, ws):
        self.ws = ws
        self.ids = itertools.count(1)

    def call(self, method: str, **params):
        i = next(self.ids)
        self.ws.send(json.dumps({"id": i, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == i:
                if "error" in msg:
                    raise RuntimeError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})

    def js(self, expression: str):
        r = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError("script error: %s" % r["exceptionDetails"])
        return r["result"].get("value")

    def wait(self, expression: str, timeout: float = 60.0, what: str = "") -> None:
        end = time.time() + timeout
        while time.time() < end:
            if self.js(expression):
                return
            time.sleep(0.25)
        raise TimeoutError("waited %.0f s for %s" % (timeout, what or expression))

    def idle(self, settle: float = 1.0) -> None:
        """Wait until the Streamlit script has finished running and the page has settled."""
        time.sleep(0.4)
        self.wait("!document.querySelector('[data-testid=\"stStatusWidget\"]')", 300, "the script to finish")
        time.sleep(settle)

    def key(self, name: str) -> None:
        for kind in ("keyDown", "keyUp"):
            self.call("Input.dispatchKeyEvent", type=kind, key=name, code=name, windowsVirtualKeyCode=KEYS[name])

    def screenshot(self, path: str) -> None:
        data = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        print("wrote", path)


SLIDER_JS = """(() => {
  for (const s of document.querySelectorAll('[data-testid="stSlider"]')) {
    const label = s.querySelector('[data-testid="stWidgetLabel"]');
    if (label && label.innerText.trim() === %s) {
      const thumb = s.querySelector('input[type="range"]');
      %s
    }
  }
  return null;
})()"""


def set_slider(page: Page, label: str, value: float) -> None:
    for _ in range(200):
        now = page.js(SLIDER_JS % (json.dumps(label), "return Number(thumb.value);"))
        if now is None:
            raise RuntimeError("no slider %r" % label)
        if now == value:
            return
        page.js(SLIDER_JS % (json.dumps(label), "thumb.focus(); return true;"))
        page.key("ArrowRight" if now < value else "ArrowLeft")
        page.idle(0.3)
    raise RuntimeError("could not set %r to %s" % (label, value))


def click_text(page: Page, selector: str, text: str) -> None:
    """Click the first element of `selector` whose last line of text is `text` (icons come first)."""
    ok = page.js("""(() => { for (const e of document.querySelectorAll(%s)) {
        if (e.innerText.trim().split(/\\n/).pop().trim() === %s) { e.click(); return true; } } return false; })()"""
                 % (json.dumps(selector), json.dumps(text)))
    if not ok:
        raise RuntimeError("nothing to click: %s %r" % (selector, text))


def scroll_to(page: Page, selector: str, y: int) -> None:
    """Scroll the main column so that the top of `selector` is `y` pixels below the top of the window."""
    page.js("""(() => { const m = document.querySelector('[data-testid="stMain"]');
        m.scrollTop += Math.round(document.querySelector(%s).getBoundingClientRect().top) - %d; })()"""
            % (json.dumps(selector), y))
    time.sleep(0.5)


def figures_loaded(page: Page, count: int) -> None:
    """Wait until the open tab shows `count` figures, all loaded."""
    page.wait("""(() => { const im = document.querySelectorAll('[role="tabpanel"]:not([hidden]) img');
        return im.length >= %d && Array.from(im).every(i => i.complete && i.naturalWidth > 0); })()""" % count,
              120, "the figures")
    time.sleep(1.0)


def take(page: Page, url: str, out: str) -> None:
    """Set the inputs, run, and save the two screenshots."""
    page.call("Emulation.setDeviceMetricsOverride", width=WIDTH, height=HEIGHT, deviceScaleFactor=1, mobile=False)
    page.call("Page.enable")
    page.call("Page.navigate", url=url)
    page.wait("!!document.querySelector('[data-testid=\"stSidebar\"] [data-testid=\"stSlider\"]')", 60,
              "the dashboard")
    page.idle(2.0)

    for label, value in SLIDERS.items():
        set_slider(page, label, value)
    page.js("document.activeElement.blur(); document.querySelector('[data-testid=\"stSidebarContent\"]').scrollTop = 0")
    click_text(page, "summary", "Handover rules")             # collapse the rules, as on the pictures
    page.idle()
    click_text(page, "button", "Run")
    page.wait("document.body.innerText.includes('done in')", 900, "the run")
    page.idle(2.0)

    figures_loaded(page, 1)                                   # the Map tab is open after a run
    scroll_to(page, '[data-testid="stTabs"]', 260)
    page.screenshot(os.path.join(out, "dashboard.png"))

    click_text(page, "[role='tab']", "Charts")
    page.idle()
    figures_loaded(page, 3)
    scroll_to(page, "h1", 30)
    page.screenshot(os.path.join(out, "dashboard-charts.png"))


def find_browser() -> str:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if os.path.exists(p):
            return p
    for name in ("msedge", "google-chrome", "chromium", "chrome"):
        if shutil.which(name):
            return shutil.which(name)
    raise SystemExit("error: no Edge or Chrome found; pass --browser")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="http://localhost:8501", help="address of the running dashboard")
    ap.add_argument("--browser", default=None, help="path of msedge.exe or chrome.exe")
    ap.add_argument("--debug-port", type=int, default=9333)
    ap.add_argument("--out", default=OUT, help="folder of the PNG files")
    a = ap.parse_args()

    profile = tempfile.mkdtemp(prefix="hl-shots-")
    browser = subprocess.Popen([a.browser or find_browser(), "--headless=new", "--disable-gpu",
                                "--remote-debugging-port=%d" % a.debug_port, "--user-data-dir=" + profile,
                                "--window-size=%d,%d" % (WIDTH, HEIGHT), "--hide-scrollbars", "--no-first-run",
                                "--no-default-browser-check", "about:blank"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/json" % a.debug_port, timeout=2) as r:
                    ws_url = next(t["webSocketDebuggerUrl"] for t in json.load(r) if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.5)
        if ws_url is None:
            raise SystemExit("error: the browser did not open its debugging port")
        with connect(ws_url, max_size=None, open_timeout=30) as ws:
            take(Page(ws), a.url, a.out)
    finally:
        try:                                                      # close the browser with all its processes
            with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % a.debug_port, timeout=2) as r:
                with connect(json.load(r)["webSocketDebuggerUrl"], open_timeout=10) as ws:
                    ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            browser.wait(10)
        except (OSError, KeyError, subprocess.TimeoutExpired):
            pass
        browser.terminate()
        try:
            browser.wait(10)
        except subprocess.TimeoutExpired:
            browser.kill()
        shutil.rmtree(profile, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
