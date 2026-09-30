#!/usr/bin/env python3
"""Functional test suite for the User Role Aggregator app (App Platform build).

Installs the built zip into a DHIS2 instance, drives the UI with Playwright,
verifies effects via the API, and cleans up created metadata.

Usage:
  DHIS2_ADMIN_PASSWORD=<password> python3 suite.py \
      --base http://dhis2-<instance>:8080 --label 2.42 [--user admin] [--zip <bundle.zip>]

The password can also be passed with --password. The zip defaults to the
bundle for the current package.json name and version.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OUTDIR = Path(__file__).parent / "output"
PROJECT_DIR = Path(__file__).parents[2]
PKG = json.loads((PROJECT_DIR / "package.json").read_text())
# The DHIS2 app key equals the app name in package.json / d2.config.js
APP_KEY = PKG["name"]
DEFAULT_ZIP = PROJECT_DIR / "build" / "bundle" / f"{APP_KEY}-{PKG['version']}.zip"
TRANSFER = '[data-test="dhis2-uicore-transfer"]'
TRANSFER_OPTION = '[data-test="dhis2-uicore-transferoption"]'
CAN_MANAGE_LIST = '[data-test="can-manage-list"] li'
# Characters i18next's default escaping would mangle; used to find a seed
# role whose display name proves the persisted description survives
# unescaped (Ruling 3's regression check needs *some* such character to be
# present in the picked roles, and Sierra Leone's role names don't
# reliably provide one on their own).
SPECIAL_CHARS = set('&<>"\'/')
# The authorities the Create page preselects, so they are already on any role
# the suite creates. Kept in sync with DEFAULT_AUTHORITIES in
# src/pages/CreateRolePage.tsx.
DEFAULT_AUTHORITIES = {"F_USER_ADD", "F_USER_DELETE", "M_dhis-web-user", "F_USER_VIEW"}
# App-side /api/ HTTP errors that are expected regardless of DHIS2 version
# or permissions, so they must not fail the suite. Keep this list narrow —
# anything else >=400 from the app is a real regression, in particular the
# version-specific permission differences this suite runs 2.40-2.43 to catch.
BENIGN_HTTP_ERROR_PATTERNS = [
    # The header bar's logo request 404s on any instance with no custom
    # logo configured — normal on a fresh demo seed.
    "staticContent/logo_banner",
]
CHECK_HEADING = "Check what a role combination can manage"
CREATE_HEADING = "Create new user admin role"
UPDATE_HEADING = "Update existing user role"
NAV_CHECK = "Role combination"
NAV_CREATE = "Create new role"
NAV_UPDATE = "Update existing role"


def api(base, user, password, method, path, data=None, content_type="application/json", raw=False):
    req = urllib.request.Request(
        f"{base}{path}",
        data=data if isinstance(data, (bytes, type(None))) else json.dumps(data).encode(),
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode(),
            **({"Content-Type": content_type} if data is not None else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            if raw:
                return r.status, body
            return r.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:500]


def install_app(base, user, password, zip_path):
    zip_file = Path(zip_path).resolve()
    if zip_file.suffix != ".zip" or not zip_file.is_file():
        raise ValueError(f"--zip must point to an existing .zip file, got: {zip_path}")
    boundary = "----agentboundary42"
    payload = zip_file.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="app.zip"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    return api(base, user, password, "POST", "/api/apps", data=body,
               content_type=f"multipart/form-data; boundary={boundary}")


def login_cookie(base, user, password):
    req = urllib.request.Request(
        f"{base}/api/me",
        headers={"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()},
    )
    with urllib.request.urlopen(req) as r:
        for c in r.headers.get_all("Set-Cookie") or []:
            head = c.split(";", 1)[0]
            n, _, v = head.partition("=")
            if "JSESSIONID" in n:
                return n.strip(), v.strip()
    raise RuntimeError("No JSESSIONID returned")


class Suite:
    def __init__(self, base, label, user, password):
        self.base, self.label, self.user, self.password = base, label, user, password
        self.results = []
        self.console = []
        self.pageerrors = []
        self.reqfailed = []
        self.http_errors = []
        self.created_role_uids = []
        self.shot_n = 0
        self.dir = OUTDIR / label
        self.dir.mkdir(parents=True, exist_ok=True)

    def record(self, step, status, detail=""):
        self.results.append({"step": step, "status": status, "detail": detail})
        print(f"[{self.label}] {status}: {step} {('- ' + detail) if detail else ''}", flush=True)

    def shot(self, page, name):
        self.shot_n += 1
        path = self.dir / f"{self.shot_n:02d}-{name}.png"
        page.screenshot(path=str(path), full_page=True)
        return path

    # ---- helpers on the app frame ----
    def app_frame(self, page):
        # App may render inside global shell iframe (2.42+) or top-level (2.40)
        for f in page.frames:
            if APP_KEY in (f.url or "") and f != page.main_frame:
                return f
        return page.main_frame

    def wait_for_heading(self, page, heading, timeout_s=20):
        """Poll for an <h1> across the (possibly-replaced) app frame, rather
        than waiting on a single captured frame reference: the global shell
        can swap the app iframe for a new frame instance shortly after
        navigation, which would otherwise leave wait_for() watching a
        frame that is never going to change again."""
        deadline = time.monotonic() + timeout_s
        last_frame = self.app_frame(page)
        while time.monotonic() < deadline:
            last_frame = self.app_frame(page)
            if last_frame.locator("h1", has_text=heading).count() > 0:
                return last_frame
            page.wait_for_timeout(300)
        raise TimeoutError(f'heading "{heading}" never appeared (frame url={last_frame.url})')

    def transfer_pick(self, frame, transfer_index, option_label):
        transfers = frame.locator(TRANSFER)
        t = transfers.nth(transfer_index)
        filt = t.locator('[data-test="dhis2-uicore-transfer-filter"] input').first
        # filter to the option to avoid scrolling long lists
        filt.fill(option_label)
        frame.page.wait_for_timeout(200)
        opt = t.locator(TRANSFER_OPTION, has_text=option_label).first
        if opt.count() == 0:
            # Some display names (e.g. containing an unmatched parenthesis,
            # as in "MNCH / PNC (Adult Woman) program") break the Transfer's
            # fuzzy filter, which then silently shows zero options instead
            # of raising. Clear the filter and locate the option directly —
            # dblclick auto-scrolls into view, so filtering was only ever a
            # convenience for long lists, not a correctness requirement.
            filt.fill("")
            frame.page.wait_for_timeout(200)
            opt = t.locator(TRANSFER_OPTION, has_text=option_label).first
        opt.dblclick()

    def select_update_role(self, frame, role_name):
        frame.locator('[data-test="dhis2-uicore-select"]').click()
        menu = frame.locator('[data-test="dhis2-uicore-select-menu-menuwrapper"]')
        if menu.count() == 0:  # menu rendered in a portal/layer on the page
            menu = frame.locator('[data-test="dhis2-uicore-layer"]')
        filt = frame.locator('[data-test="dhis2-uicore-select-filter"] input')
        if filt.count() > 0:
            filt.fill(role_name)
        frame.locator('[data-test="dhis2-uicore-singleselectoption"]', has_text=role_name).first.click()

    def assert_can_manage(self, page, role_name, expected_name, step_label):
        """Navigate in-app to the Check page, select role_name, and assert
        expected_name appears in its can-manage list. Never reloads the page,
        so this also proves cache invalidation when called post-update."""
        f = self.app_frame(page)
        f.locator("a", has_text=NAV_CHECK).click()
        f = self.wait_for_heading(page, CHECK_HEADING, timeout_s=10)
        self.transfer_pick(f, 0, role_name)
        page.wait_for_timeout(600)
        listed = [t.strip() for t in f.locator(CAN_MANAGE_LIST).all_inner_texts()]
        found = any(expected_name in item for item in listed)
        self.record(step_label, "PASS" if found else "FAIL", f"listed={listed[:8]}")
        return f

    def run(self, zip_path):
        self.api_preflight()
        launch = self.install(zip_path)
        role_name = f"Agent Test Admin Role {int(time.time())}"
        try:
            self.run_browser_flows(launch, role_name)
        finally:
            # Always attempt cleanup, even if a browser-flow step raised
            # (e.g. a wait_for_heading timeout from the stale-frame race) —
            # otherwise a role created earlier in the flow is never deleted.
            self.cleanup_roles()
        self.summarize()

    def api_preflight(self):
        st, info = api(self.base, self.user, self.password, "GET", "/api/system/info")
        self.record("API: system/info", "PASS" if st == 200 else "FAIL", f"version={info.get('version') if st==200 else st}")
        st, roles = api(self.base, self.user, self.password, "GET",
                        "/api/userRoles?fields=id,displayName,authorities&paging=false")
        n_roles = len(roles.get("userRoles", [])) if st == 200 else 0
        self.record("API: userRoles list", "PASS" if st == 200 and n_roles > 0 else "FAIL", f"{n_roles} roles")
        st, auths = api(self.base, self.user, self.password, "GET", "/api/authorities")
        n_auths = len(auths.get("systemAuthorities", [])) if st == 200 else 0
        self.record("API: authorities list", "PASS" if st == 200 and n_auths > 0 else "FAIL", f"{n_auths} authorities")
        self.demo_roles = {r["displayName"]: r for r in roles.get("userRoles", [])}
        # A role whose display name contains a character i18next's default
        # escaping would mangle, so the description assertion below has
        # something to actually catch. Exclude ALL-holding roles: granting
        # ALL to a throwaway test role would make it a superuser-equivalent.
        # Seed-agnostic: Sierra Leone has "MNCH / PNC (Adult Woman)
        # program"; other seeds (e.g. Laos) may have a different one, or
        # none, in which case the assertion is recorded as SKIP.
        candidates = [
            r for r in roles.get("userRoles", [])
            if SPECIAL_CHARS & set(r["displayName"])
            and "ALL" not in (r.get("authorities") or [])
        ]
        self.escape_test_role = candidates[0] if candidates else None
        # The role whose authorities the created role aggregates. Discovered
        # rather than named: Sierra Leone has "Data entry clerk", Laos has
        # "Admin"/"Analytics"/"Data capture", and a suite that hard-codes
        # either cannot run on the other. Smallest non-empty authority set
        # wins, so the update flow below still has a role left to add.
        usable = sorted(
            (r for r in roles.get("userRoles", [])
             if (r.get("authorities") or []) and "ALL" not in (r.get("authorities") or [])),
            key=lambda r: len(r["authorities"]),
        )
        self.source_role = usable[0]["displayName"] if usable else None
        self.record("Preflight: source role for aggregation",
                    "PASS" if self.source_role else "FAIL", str(self.source_role))

    def install(self, zip_path):
        st, _ = install_app(self.base, self.user, self.password, zip_path)
        self.record("Install app zip via /api/apps", "PASS" if st in (200, 201, 204) else "FAIL", f"http {st}")
        st, apps = api(self.base, self.user, self.password, "GET", "/api/apps")
        entry = next((a for a in apps if APP_KEY in (a.get("key") or "")), None) if st == 200 else None
        launch = entry.get("launchUrl") if entry else f"{self.base}/api/apps/{APP_KEY}/index.html"
        self.record("App registered", "PASS" if entry else "WARN", f"launchUrl={launch}")
        return launch

    def run_browser_flows(self, launch, role_name):
        cn, cv = login_cookie(self.base, self.user, self.password)
        host = self.base.split("://", 1)[1].split(":")[0]
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1400, "height": 900})
            ctx.add_cookies([{"name": cn, "value": cv, "domain": host, "path": "/"}])
            page = ctx.new_page()
            page.on("console", lambda m: self.console.append((m.type, m.text)) if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: self.pageerrors.append(str(e)))
            page.on("requestfailed", lambda r: self.reqfailed.append((r.url, str(r.failure))))
            page.on("response", lambda r: self.http_errors.append((r.status, r.url)) if r.status >= 400 else None)
            try:
                self.flow_create(page, launch, role_name)
                self.flow_update(page, role_name)
            finally:
                self.shot(page, "final")
                browser.close()

    def cleanup_roles(self):
        for uid in self.created_role_uids:
            st, _ = api(self.base, self.user, self.password, "DELETE", f"/api/userRoles/{uid}")
            self.record(f"Cleanup: delete role {uid}", "PASS" if st in (200, 204) else "FAIL", f"http {st}")

    def summarize(self):
        self.record("Console errors", "PASS" if not [c for c in self.console if c[0] == "error"] else "WARN",
                    f"{len([c for c in self.console if c[0]=='error'])} errors")
        self.record("Page errors", "PASS" if not self.pageerrors else "FAIL", f"{len(self.pageerrors)}")
        app_http_errors = [e for e in self.http_errors if "/api/" in e[1]]
        unexpected_http_errors = [
            e for e in app_http_errors
            if not any(pattern in e[1] for pattern in BENIGN_HTTP_ERROR_PATTERNS)
        ]
        # App-side >=400 responses are a FAIL, not a WARN: this suite runs
        # across DHIS2 2.40-2.43 specifically to catch version-specific
        # permission differences (403/409 etc.) in the new read-only pages'
        # API calls, and a WARN would never trip the suite's exit code.
        self.record("HTTP >=400 responses", "PASS" if not unexpected_http_errors else "FAIL",
                    "; ".join(f"{s} {u.split('/api/')[-1][:60]}" for s, u in unexpected_http_errors[:5]))

        (self.dir / "results.json").write_text(json.dumps({
            "results": self.results,
            "console": self.console[:50],
            "pageerrors": self.pageerrors[:20],
            "requestfailed": self.reqfailed[:20],
            "http_errors": self.http_errors[:50],
        }, indent=2))

    def flow_create(self, page, launch, role_name):
        page.goto(launch, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        # The app lands on the Check page by default. Never trust a hash on
        # first load — the App Platform shell ignores it — so wait for the
        # app to mount here, then navigate in-app via the sidebar link.
        try:
            f = self.wait_for_heading(page, CHECK_HEADING, timeout_s=20)
            self.record("App loads: check page renders", "PASS")
        except Exception as e:
            self.shot(page, "load-fail")
            self.record("App loads: check page renders", "FAIL", str(e)[:120])
            raise
        f.locator("a", has_text=NAV_CREATE).click()
        # wait for the create page heading
        try:
            f = self.wait_for_heading(page, CREATE_HEADING, timeout_s=20)
            self.record("App loads: create page renders", "PASS")
        except Exception as e:
            self.shot(page, "load-fail")
            self.record("App loads: create page renders", "FAIL", str(e)[:120])
            raise
        self.shot(page, "create-page")

        transfers = f.locator(TRANSFER)
        n_role_opts = transfers.nth(0).locator(TRANSFER_OPTION).count()
        self.record("Roles transfer populated", "PASS" if n_role_opts > 0 else "FAIL", f"{n_role_opts} options")

        picked = f.locator(TRANSFER).nth(1) \
            .locator(f'[data-test="dhis2-uicore-transfer-pickedoptions"] {TRANSFER_OPTION}')
        picked_labels = picked.all_inner_texts()
        # authority *names* are shown, not ids; just assert some defaults picked
        self.record("Default authorities preselected", "PASS" if len(picked_labels) >= 3 else "FAIL",
                    f"{len(picked_labels)} picked: {picked_labels[:6]}")

        # --- validation: submit empty form ---
        f.locator("button", has_text="Create role").click()
        page.wait_for_timeout(500)
        err_visible = f.get_by_text("Role name is required").count() > 0
        self.record("Validation: empty name rejected", "PASS" if err_visible else "FAIL")
        self.shot(page, "validation")

        # --- fill and submit ---
        f.locator('input[type="text"]').first.fill(role_name)
        self.transfer_pick(f, 0, self.source_role)
        # Also pick the escape-test role (if this seed has one): adding a
        # role only adds authorities, so every existing assertion about the
        # clerk's authorities and the can-manage list keeps working.
        if self.escape_test_role:
            self.transfer_pick(f, 0, self.escape_test_role["displayName"])
        self.shot(page, "create-filled")
        f.locator("button", has_text="Create role").click()
        try:
            f.locator('[data-test="dhis2-uicore-alertbar"]', has_text="created successfully").wait_for(timeout=15000)
            self.record("Create role: success alert", "PASS")
        except Exception:
            self.shot(page, "create-fail")
            self.record("Create role: success alert", "FAIL")
        self.shot(page, "create-done")

        # --- API verify ---
        st, res = api(self.base, self.user, self.password, "GET",
                      f"/api/userRoles?filter=name:eq:{urllib.request.quote(role_name)}&fields=id,name,description,authorities")
        found = res.get("userRoles", []) if st == 200 else []
        if found:
            self.created_role_uids.append(found[0]["id"])
            source = self.demo_roles.get(self.source_role, {})
            clerk_auths = set(source.get("authorities", []))
            new_auths = set(found[0].get("authorities", []))
            missing = clerk_auths - new_auths
            has_defaults = {"F_USER_ADD", "F_USER_VIEW"} <= new_auths
            ok = not missing and has_defaults
            self.record("API verify: created role aggregates authorities", "PASS" if ok else "FAIL",
                        f"{len(new_auths)} auths, missing from clerk: {sorted(missing)[:5]}, defaults={has_defaults}")

            # Regression check: i18next previously escaped interpolated values
            # in the persisted description, e.g. "/" became "&#x2F;". Only
            # meaningful if a picked role's name actually contains a
            # character escaping would touch — Data entry clerk alone
            # never does, which would make this assertion pass
            # unconditionally regardless of whether escaping regressed.
            description = found[0].get("description") or ""
            if self.escape_test_role:
                escaped_name = self.escape_test_role["displayName"]
                not_escaped = "&#x" not in description
                contains_role_name = escaped_name in description
                ok = not_escaped and contains_role_name
                self.record("API verify: description is not HTML-escaped",
                            "PASS" if ok else "FAIL",
                            f"description={description[:160]!r} "
                            f"expected_role={escaped_name!r} "
                            f"contains_role={contains_role_name} not_escaped={not_escaped}")
            else:
                self.record("API verify: description is not HTML-escaped", "SKIP",
                            "no role on this instance has a display name containing "
                            f"one of {sorted(SPECIAL_CHARS)}; nothing for escaping to mangle")
        else:
            self.record("API verify: created role exists", "FAIL", f"http {st}")

    def flow_update(self, page, role_name):
        f = self.app_frame(page)
        f.locator("a", has_text=NAV_UPDATE).click()
        try:
            f = self.wait_for_heading(page, UPDATE_HEADING, timeout_s=10)
            self.record("Update page renders", "PASS")
        except Exception as e:
            self.shot(page, "update-load-fail")
            self.record("Update page renders", "FAIL", str(e)[:120])
            return
        self.shot(page, "update-page")

        # select the role created in flow_create
        self.select_update_role(f, role_name)
        page.wait_for_timeout(500)
        self.shot(page, "update-selected")

        # The managed-roles analysis moved to the Check page: select the
        # created role there and confirm it can manage the role whose
        # authorities it was created from.
        self.assert_can_manage(page, role_name, self.source_role,
                                f"Check page: created role can manage {self.source_role}")

        # back to the Update page to add another role's authorities
        f = self.app_frame(page)
        f.locator("a", has_text=NAV_UPDATE).click()
        f = self.wait_for_heading(page, UPDATE_HEADING, timeout_s=10)
        self.select_update_role(f, role_name)
        page.wait_for_timeout(500)

        # add another role's authorities
        # A different role that still has something to contribute. Excluding
        # source_role is not enough: the created role also absorbed the
        # escape-test role's authorities, and the defaults. A target already
        # covered by that union would make the merge assertion below vacuous
        # — it would pass before the update button was ever clicked.
        already_held = set(self.demo_roles.get(self.source_role, {}).get("authorities") or [])
        already_held |= DEFAULT_AUTHORITIES
        if self.escape_test_role:
            already_held |= set(self.escape_test_role.get("authorities") or [])
        target = next((n for n, r in self.demo_roles.items()
                       if n != self.source_role
                       and (r.get("authorities") or [])
                       and "ALL" not in r["authorities"]
                       and set(r["authorities"]) - already_held), None)
        if not target:
            self.record("Update flow: a target with new authorities to add", "SKIP",
                        "every other role's authorities are already covered by the created role")
            return
        self.transfer_pick(f, 0, target)  # only one transfer on this page
        self.shot(page, "update-picked")
        f.locator("button", has_text="Add authorities to role").click()
        try:
            f.locator('[data-test="dhis2-uicore-alertbar"]', has_text="updated successfully").wait_for(timeout=15000)
            self.record("Update role: success alert", "PASS")
        except Exception:
            self.shot(page, "update-fail")
            self.record("Update role: success alert", "FAIL")
        page.wait_for_timeout(1500)
        self.shot(page, "update-done")

        # The Check page's can-manage list should now include the target
        # role too, without a page reload — proof the userRoles query was
        # invalidated after the update.
        self.assert_can_manage(page, role_name, target,
                                "Check page: can-manage list refreshes after update (cache invalidation)")

        # API verify merge
        if self.created_role_uids:
            uid = self.created_role_uids[0]
            st, role = api(self.base, self.user, self.password, "GET",
                           f"/api/userRoles/{uid}?fields=name,description,authorities")
            tgt_auths = set(self.demo_roles.get(target, {}).get("authorities", []))
            new_auths = set(role.get("authorities", [])) if st == 200 else set()
            missing = tgt_auths - new_auths
            self.record("API verify: authorities merged, nothing lost",
                        "PASS" if st == 200 and not missing and role.get("description") else "FAIL",
                        f"missing={sorted(missing)[:5]} description_kept={bool(role.get('description'))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--user", default=os.environ.get("DHIS2_ADMIN_USER", "admin"))
    ap.add_argument("--password", default=os.environ.get("DHIS2_ADMIN_PASSWORD"))
    ap.add_argument("--zip", default=str(DEFAULT_ZIP))
    args = ap.parse_args()
    if not args.password:
        ap.error("--password or DHIS2_ADMIN_PASSWORD is required")
    s = Suite(args.base, args.label, args.user, args.password)
    s.run(args.zip)
    fails = [r for r in s.results if r["status"] == "FAIL"]
    print(f"\n[{args.label}] {len(s.results)} steps, {len(fails)} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
