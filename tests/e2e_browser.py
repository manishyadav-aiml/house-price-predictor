"""Optional real-browser test (needs: pip install playwright && playwright install chromium).
Start the app first (python app.py on port 5055 with PORT=5055), then run:  python tests/e2e_browser.py"""
from playwright.sync_api import sync_playwright
ok = []
def check(n, c): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n)
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1100, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:5055/?utm_source=test&utm_medium=e2e"); pg.wait_for_selector("#f-MedInc")
    check("model status pill loaded", "R²" in pg.inner_text("#mstat"))
    check("demo warning visible", pg.is_visible("#demo"))
    check("8 input fields built from /api/meta", pg.locator("#fields input").count() == 8)
    check("cookie banner shown", pg.is_visible("#cookie")); pg.click("[data-c=accepted]"); check("cookie banner hides", not pg.is_visible("#cookie"))
    check("UTM captured from URL", "utm_source=test" in pg.inner_text("#utm"))
    pg.click("#pf button[type=submit]"); pg.wait_for_selector("#result:not([hidden])")
    price = pg.inner_text("#price"); check("prediction shown as dollars: " + price, price.startswith("$"))
    pg.fill("#f-MedInc", "999"); pg.click("#pf button[type=submit]"); pg.locator("#e-f-MedInc:not(:empty)").wait_for()
    check("error state shown for bad input", pg.get_attribute("#f-MedInc", "aria-invalid") == "true"); pg.click("#reset")
    pg.click("#copy"); pg.wait_for_timeout(300); check("copy button gives feedback", "Copied" in pg.inner_text("#copy"))
    pg.click("#theme"); t1 = pg.evaluate("document.documentElement.dataset.theme"); check("dark mode toggles (" + t1 + ")", t1 in ("dark", "light"))
    pg.reload(); pg.wait_for_selector("#f-MedInc"); check("theme persists after reload", pg.evaluate("document.documentElement.dataset.theme") == t1)
    pg.fill("#q", "stored"); pg.wait_for_timeout(200); vis = pg.locator(".searchable:visible").count(); check(f"search filters content ({vis} match)", vis == 1)
    pg.fill("#q", "zzzz"); check("search shows no-results message", pg.is_visible("#none")); pg.fill("#q", "")
    # password toggle + register + history
    pg.fill("#ae", "e2e@example.com"); pg.fill("#ap", "a-long-password-1"); pg.click("#pwt"); check("password toggle shows text", pg.get_attribute("#ap", "type") == "text")
    pg.click("[data-a=register]"); pg.wait_for_selector("#member:not([hidden])"); check("registered and signed in", "e2e@example.com" in pg.inner_text("#who"))
    pg.click("#pf button[type=submit]"); pg.wait_for_selector("#htable:not([hidden])"); check("history row saved", pg.locator("#htable tbody tr").count() == 1)
    pg.click("#clear"); check("confirmation modal opens", pg.is_visible("#dlg")); pg.click("#dlg button[value=no]"); check("cancel keeps history", pg.locator("#htable tbody tr").count() == 1)
    pg.click("#clear"); pg.click("#dlg button[value=yes]"); pg.locator("#htable").wait_for(state="hidden"); check("confirm clears history", True)
    pg.click("#logout"); pg.wait_for_selector("#guest:not([hidden])"); check("signed out", pg.is_visible("#guest"))
    # batch
    open("/tmp/h.csv", "w").write("MedInc,HouseAge,AveRooms,AveBedrms,Population,AveOccup,Latitude,Longitude\n5,20,6,1,1500,3,37.8,-122.3\nx,1,1,1,1,1,35,-120\n")
    pg.set_input_files("#file", "/tmp/h.csv"); pg.click("#bgo"); pg.wait_for_selector("#btable:not([hidden])"); check("batch table shows 2 rows", pg.locator("#btable tbody tr").count() == 2); check("batch button re-enabled", pg.is_enabled("#bgo"))
    # feedback error + success
    pg.click("#cf button[type=submit]"); pg.locator("#e-name:not(:empty)").wait_for(); check("feedback error state", "name" in pg.inner_text("#e-name").lower())
    pg.fill("#cn", "Tester"); pg.fill("#ce", "t@example.com"); pg.fill("#cm", "This is a long enough message."); pg.click("#cf button[type=submit]"); pg.wait_for_selector("#ok:not([hidden])"); check("feedback success state", True)
    # scroll features
    pg.evaluate("scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(300)
    check("back-to-top appears", pg.is_visible("#top2")); check("progress bar moved", "scaleX(0)" not in pg.evaluate("document.querySelector('#bar').style.transform"))
    check("sticky header stays visible", pg.evaluate("document.querySelector('header').getBoundingClientRect().top") <= 1)
    check("floating contact button visible", pg.is_visible(".fab")); check("last-updated date shown", len(pg.inner_text("#trained")) >= 8)
    pg.screenshot(path="/tmp/desktop.png", full_page=False)
    # print stylesheet
    pg.emulate_media(media="print"); check("print hides header and forms", not pg.is_visible("header") and not pg.is_visible("#pf")); pg.emulate_media(media="screen")
    # skip link
    pg.reload(); pg.wait_for_selector("#f-MedInc"); pg.keyboard.press("Tab"); check("skip link is first tab stop", pg.evaluate("document.activeElement.className") == "skip")
    # mobile
    m = b.new_context(viewport={"width": 390, "height": 800}, is_mobile=True).new_page(); m.goto("http://localhost:5055/"); m.wait_for_selector("#f-MedInc")
    check("mobile: menu button visible, nav hidden", m.is_visible("#menu") and not m.is_visible("#nav")); m.click("#menu"); check("mobile: menu opens", m.is_visible("#nav"))
    check("mobile: no horizontal scroll", m.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")); m.screenshot(path="/tmp/mobile.png")
    # dark screenshot
    d = b.new_context(color_scheme="dark", viewport={"width": 1100, "height": 900}).new_page(); d.goto("http://localhost:5055/"); d.wait_for_selector("#f-MedInc"); d.click("[data-c=accepted]"); d.click("#pf button[type=submit]"); d.wait_for_selector("#result:not([hidden])"); d.screenshot(path="/tmp/dark.png")
    csp = [e for e in errs if "Content Security" in e or "Refused" in e]; check("no CSP violations", not csp)
    other = [e for e in errs if e not in csp and "favicon" not in e and "status of 400" not in e]; check("no console errors", not other); print(other[:3])
    b.close()
print(f"\n{sum(ok)}/{len(ok)} browser checks passed")
