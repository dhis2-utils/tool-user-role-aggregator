"""Browser helpers: sessions, the app frame, and the @dhis2/ui widgets the
app uses. Selectors are kept here, so a UI change is fixed in one place."""

import contextlib
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

TRANSFER = '[data-test="dhis2-uicore-transfer"]'
TRANSFER_OPTION = '[data-test="dhis2-uicore-transferoption"]'
TRANSFER_FILTER = '[data-test="dhis2-uicore-transfer-filter"] input'
TRANSFER_PICKED = '[data-test="dhis2-uicore-transfer-pickedoptions"]'
SELECT = '[data-test="dhis2-uicore-select"]'
SELECT_FILTER = '[data-test="dhis2-uicore-select-filter"] input'
SELECT_OPTION = '[data-test="dhis2-uicore-singleselectoption"]'
ALERTBAR = '[data-test="dhis2-uicore-alertbar"]'
LOADER = '[data-test="dhis2-uicore-circularloader"]'
CAN_MANAGE_LIST = '[data-test="can-manage-list"] li'
CANNOT_MANAGE_LIST = '[data-test="cannot-manage-list"] li'

CHECK_HEADING = "Check what a role combination can manage"
CREATE_HEADING = "Create new user admin role"
UPDATE_HEADING = "Update existing user admin role"
LOOKUP_HEADING = "Look up a user"
NAV_CHECK = "Role combination"
NAV_LOOKUP = "Look up user"
NAV_CREATE = "Create new role"
NAV_UPDATE = "Update existing role"
GUARD_TEXT = "This page needs one of these authorities"

# Requests that fail on any instance and say nothing about the app: the
# header bar asks for a custom logo that a fresh instance does not have.
BENIGN_HTTP_ERRORS = ["staticContent/logo_banner"]
VIEWPORT = {"width": 1400, "height": 1000}
SETTLE_MS = 400


class Session:
    """One signed-in browser context, with the errors it collects."""

    def __init__(self, browser, dhis2, user, password, app_key):
        self.app_key = app_key
        self.page_errors = []
        self.http_errors = []
        name, value = dhis2.session_cookie(user, password)
        host = dhis2.base.split("://", 1)[1].split("/", 1)[0].split(":")[0]
        self.context = browser.new_context(viewport=VIEWPORT)
        self.context.add_cookies([{"name": name, "value": value, "domain": host, "path": "/"}])
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda err: self.page_errors.append(str(err)))
        self.page.on("response", self.on_response)

    def on_response(self, response):
        url = response.url
        if response.status >= 400 and "/api/" in url and not any(p in url for p in BENIGN_HTTP_ERRORS):
            self.http_errors.append(f"{response.status} {url.split('/api/', 1)[-1][:80]}")

    def close(self):
        with contextlib.suppress(Exception):
            self.context.close()

    def screenshot(self, path):
        with contextlib.suppress(Exception):
            self.page.screenshot(path=str(path), full_page=True)

    def frame(self):
        """The app's frame: the global-shell iframe on 2.42 and later, the
        top-level page on 2.41 and earlier. Looked up fresh each time,
        because the shell can replace the iframe after a navigation."""
        for frame in self.page.frames:
            if frame != self.page.main_frame and self.app_key in (frame.url or ""):
                return frame
        return self.page.main_frame

    def wait_for(self, predicate, timeout_s, what):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            frame = self.frame()
            with contextlib.suppress(Exception):
                if predicate(frame):
                    return frame
            self.page.wait_for_timeout(300)
        raise PlaywrightTimeoutError(f"{what} did not appear within {timeout_s}s (url={self.page.url})")

    def wait_for_heading(self, heading, timeout_s=20):
        return self.wait_for(
            lambda f: f.locator("h1", has_text=heading).count() > 0, timeout_s, f'heading "{heading}"'
        )

    def open_app(self, launch_url, timeout_s=60):
        """Loads the app and waits for its landing page. The App Platform
        shell ignores a route hash on the first load, so tests navigate with
        the sidebar after this."""
        self.page.goto(launch_url, wait_until="domcontentloaded")
        return self.wait_for_heading(CHECK_HEADING, timeout_s)

    def navigate(self, link_text, heading):
        self.frame().locator("a", has_text=link_text).first.click()
        return self.wait_for_heading(heading)

    # ---- widgets ----

    def transfer_pick(self, transfer_index, label):
        transfer = self.frame().locator(TRANSFER).nth(transfer_index)
        transfer.locator(TRANSFER_FILTER).first.fill(label)
        self.page.wait_for_timeout(SETTLE_MS)
        option = transfer.locator(TRANSFER_OPTION, has_text=label).first
        if option.count() == 0:
            # Some names (an unmatched parenthesis, say) break the
            # Transfer's filter, which then shows nothing. The filter is a
            # convenience; clear it and find the option in the full list.
            transfer.locator(TRANSFER_FILTER).first.fill("")
            self.page.wait_for_timeout(SETTLE_MS)
            option = transfer.locator(TRANSFER_OPTION, has_text=label).first
        option.dblclick()
        self.page.wait_for_timeout(SETTLE_MS)

    def transfer_options(self, transfer_index):
        transfer = self.frame().locator(TRANSFER).nth(transfer_index)
        return [text.strip() for text in transfer.locator(TRANSFER_OPTION).all_inner_texts()]

    def transfer_picked(self, transfer_index):
        transfer = self.frame().locator(TRANSFER).nth(transfer_index)
        return [t.strip() for t in transfer.locator(f"{TRANSFER_PICKED} {TRANSFER_OPTION}").all_inner_texts()]

    def select_options(self):
        """Labels in the first single select, which is closed again after."""
        frame = self.frame()
        frame.locator(SELECT).first.click()
        frame.locator(SELECT_OPTION).first.wait_for()
        labels = [t.strip() for t in frame.locator(SELECT_OPTION).all_inner_texts()]
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(SETTLE_MS)
        return labels

    def select_option(self, label):
        frame = self.frame()
        frame.locator(SELECT).first.click()
        search = frame.locator(SELECT_FILTER)
        if search.count() > 0:
            search.first.fill(label)
        frame.locator(SELECT_OPTION, has_text=label).first.click()
        self.page.wait_for_timeout(SETTLE_MS)

    def click_button(self, label):
        self.frame().locator("button", has_text=label).first.click()

    def wait_for_alert(self, text, timeout_ms=20000):
        """Returns the alert's text, or None if no matching alert appeared."""
        alert = self.frame().locator(ALERTBAR, has_text=text).first
        try:
            alert.wait_for(timeout=timeout_ms)
        except PlaywrightTimeoutError:
            return None
        return alert.inner_text()

    def alerts(self):
        return self.frame().locator(ALERTBAR).all_inner_texts()

    def list_items(self, selector):
        return sorted(text.strip() for text in self.frame().locator(selector).all_inner_texts())
