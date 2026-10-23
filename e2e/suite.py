#!/usr/bin/env python3
"""End-to-end suite for the User Admin Role Aggregator.

Run it through e2e/run.sh, which documents the inputs. The suite installs the
bundle, seeds a handful of roles and users with run-unique names, drives the
app in Chromium as a superuser, a role manager, a read-only user and a user
without app access, checks every write against the API, cleans up, and
uninstalls the app. It writes $RESULTS_DIR/results.json (TESTING.md).
"""

import contextlib
import json
import os
import secrets
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from app_ui import (
    CAN_MANAGE_LIST,
    CANNOT_MANAGE_LIST,
    CHECK_HEADING,
    CREATE_HEADING,
    GUARD_TEXT,
    LOADER,
    LOOKUP_HEADING,
    NAV_CHECK,
    NAV_CREATE,
    NAV_LOOKUP,
    NAV_UPDATE,
    UPDATE_HEADING,
    Session,
)
from dhis2_api import ApiError, Dhis2, StateRecord, app_authority, new_uid, read_manifest

CONTRACT_VERSION = 1
EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2
REPO = "tool-user-role-aggregator"

# Authorities of the seeded roles. Ordinary ones, present on every DHIS2
# version the tool supports; checked against /api/authorities before use.
CLERK = ["F_DATAVALUE_ADD", "M_dhis-web-aggregate-data-entry"]
ANALYST = ["F_VISUALIZATION_PUBLIC_ADD", "M_dhis-web-data-visualizer"]
MAPPER = ["F_MAP_PUBLIC_ADD", "M_dhis-web-maps"]
# Added to the clerk role mid-test, to prove the app re-checks at submit time.
LATE_AUTHORITY = "F_REPORT_DELETE"
USER_MANAGER = ["F_USER_ADD", "F_USER_VIEW", "F_USER_DELETE", "F_USERROLE_PUBLIC_ADD", "M_dhis-web-user"]
READ_ONLY = ["F_USER_VIEW", "M_dhis-web-user"]
# Preselected on the Create page; mirrors DEFAULT_AUTHORITIES in
# src/pages/CreateRolePage.tsx.
DEFAULT_AUTHORITIES = {"F_USER_ADD", "F_USER_DELETE", "M_dhis-web-user", "F_USER_VIEW"}
# Mirrors canAdministerUsers() in src/domain/userRole.ts.
USER_ADMIN_AUTHORITIES = {"ALL", "F_USER_ADD", "F_USER_ADD_WITHIN_MANAGED_GROUP"}
# Characters i18next would escape; the mapper role's name carries them.
SPECIAL_NAME_SUFFIX = "Maps & Reports / <PNC>"


def env(name, required=True):
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise SetupError("environment", f"{name} is required (see e2e/README.md)")
    return value


class SetupError(Exception):
    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage


class Results:
    def __init__(self, label):
        self.label = label
        self.tests = []

    def add(self, test_id, status, message=""):
        self.tests.append({"id": test_id, "status": status, "message": message[:500]})
        print(f"[{self.label}] {status.upper():4} {test_id} {message[:200]}", flush=True)

    def check(self, test_id, ok, message=""):
        self.add(test_id, "pass" if ok else "fail", "" if ok else message)
        return ok

    def skip(self, test_id, message):
        self.add(test_id, "skip", message)

    def failed(self):
        return sum(1 for t in self.tests if t["status"] == "fail")


def manageable(held, roles):
    """Role names a holder of `held` may manage, per canManageRole()."""
    if "ALL" in held:
        return sorted(r["displayName"] for r in roles)
    if not held & USER_ADMIN_AUTHORITIES:
        return []
    return sorted(
        r["displayName"]
        for r in roles
        if "ALL" not in (r.get("authorities") or []) and set(r.get("authorities") or []) <= held
    )


class Run:
    def __init__(self):
        self.base = env("DHIS2_URL").rstrip("/")
        self.zip_path = Path(env("APP_ZIP"))
        self.results_dir = Path(env("RESULTS_DIR"))
        self.api = Dhis2(self.base, env("DHIS2_USER"), env("DHIS2_PASS"))
        self.label = env("LABEL", required=False)
        self.app_key = env("APP_KEY", required=False)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + secrets.token_hex(2)
        self.prefix = f"E2E {REPO} {self.run_id}"
        self.state = StateRecord(self.api)
        self.server_version = ""
        self.app_version = ""
        self.launch_url = ""
        self.results = None
        self.seed = {}
        self.shots = 0

    # ---- setup ----

    def prepare(self):
        if not self.zip_path.is_absolute() or not self.zip_path.is_file():
            raise SetupError("environment", f"APP_ZIP must be the absolute path of a .zip file: {self.zip_path}")
        if not self.results_dir.is_dir():
            raise SetupError("environment", f"RESULTS_DIR must be an existing directory: {self.results_dir}")
        try:
            self.server_version = self.api.system_version()
            self.api.warm_up()
        except Exception as err:
            raise SetupError("connect", f"cannot read /api/system/info: {err}") from err
        self.label = self.label or self.server_version
        self.results = Results(self.label)
        manifest = read_manifest(self.zip_path)
        self.app_version = manifest.get("version", "")
        try:
            self.api.install_app(self.zip_path)
            app = self.api.find_app(manifest["name"])
        except ApiError as err:
            raise SetupError("install", str(err)) from err
        if not app:
            raise SetupError("install", f"app {manifest['name']!r} not listed in /api/apps after install")
        self.app_key = self.app_key or app["key"]
        self.launch_url = app.get("launchUrl") or f"{self.base}/api/apps/{self.app_key}/index.html"
        try:
            self.state.clear_leftovers()
            self.seed_metadata()
        except ApiError as err:
            raise SetupError("seed", str(err)) from err

    def seed_metadata(self):
        app_auth = app_authority(self.app_key)
        missing = set(CLERK + ANALYST + MAPPER + USER_MANAGER + [LATE_AUTHORITY]) - self.api.system_authorities()
        if missing:
            raise ApiError(f"authorities missing on this instance: {sorted(missing)}")
        org_unit = self.api.root_org_unit() or self.create_org_unit()
        self.seed["clerk"] = self.create_role("Clerk", CLERK)
        self.seed["analyst"] = self.create_role("Analyst", ANALYST)
        self.seed["mapper"] = self.create_role(SPECIAL_NAME_SUFFIX, MAPPER)
        self.seed["manager"] = self.create_role("Manager", USER_MANAGER + CLERK + [app_auth])
        self.seed["readonly"] = self.create_role("Read only", READ_ONLY + [app_auth])
        for kind, role in (("manager", "manager"), ("readonly", "readonly"), ("noaccess", "clerk")):
            self.seed[f"{kind}_user"] = self.create_user(kind, self.seed[role]["id"], org_unit)

    def create_org_unit(self):
        uid = new_uid()
        self.state.add("organisationUnits", uid)
        self.api.create(
            "organisationUnits",
            {"id": uid, "name": self.prefix, "shortName": f"E2E {self.run_id}", "openingDate": "2020-01-01"},
        )
        return uid

    def create_role(self, suffix, authorities):
        role = {"id": new_uid(), "name": f"{self.prefix} {suffix}", "authorities": sorted(set(authorities))}
        self.state.add("userRoles", role["id"])
        self.api.create("userRoles", {**role, "description": "Seeded by the e2e suite"})
        return {**role, "displayName": role["name"]}

    def create_user(self, kind, role_id, org_unit):
        user = {
            "id": new_uid(),
            "username": f"e2e_ura_{self.run_id.lower()}_{kind}",
            "password": "E2e!" + secrets.token_urlsafe(12),
            "firstName": "E2E",
            "surname": f"{self.run_id} {kind}",
        }
        self.state.add("users", user["id"])
        self.api.create(
            "users",
            {
                **user,
                "userRoles": [{"id": role_id}],
                "organisationUnits": [{"id": org_unit}],
                # 2.41 reads credentials from here; later versions ignore it.
                "userCredentials": {"username": user["username"], "password": user["password"]},
            },
        )
        return user

    # ---- browser ----

    def shot(self, session, name):
        self.shots += 1
        session.screenshot(self.results_dir / f"{self.label}-{self.shots:02d}-{name}.png")

    def session(self, browser, user=None):
        user = user or {"username": self.api.user, "password": self.api.password}
        return Session(browser, self.api, user["username"], user["password"], self.app_key)

    def scenario(self, browser, name, user, steps):
        """Runs `steps(session)` in a fresh session as `user`. An exception
        fails the scenario, not the run, so later scenarios still run."""
        session = None
        try:
            session = self.session(browser, user)
            steps(session)
        except Exception as err:
            traceback.print_exc()
            self.results.add(f"{name}-completed", "fail", f"{type(err).__name__}: {err}")
        finally:
            if session:
                self.shot(session, name)
                self.results.check(f"{name}-no-page-errors", not session.page_errors, "; ".join(session.page_errors))
                self.results.check(
                    f"{name}-no-http-errors", not session.http_errors, "; ".join(session.http_errors[:5])
                )
                session.close()

    # ---- superuser ----

    def superuser_steps(self, session):
        r = self.results
        session.open_app(self.launch_url)
        r.check("superuser-check-page-loads", True)
        session.navigate(NAV_CREATE, CREATE_HEADING)
        options = session.transfer_options(0)
        r.check(
            "create-roles-listed",
            all(self.seed[k]["name"] in options for k in ("clerk", "analyst", "mapper")),
            f"{len(options)} options",
        )
        picked = session.transfer_picked(1)
        r.check("create-default-authorities-preselected", len(picked) == len(DEFAULT_AUTHORITIES), f"picked={picked}")

        session.click_button("Create role")
        session.page.wait_for_timeout(500)
        r.check("create-empty-name-rejected", session.frame().get_by_text("Role name is required").count() > 0)

        role_name = f"{self.prefix} Created"
        self.state.add("userRoles", name=role_name)
        session.frame().locator('input[type="text"]').first.fill(role_name)
        session.transfer_pick(0, self.seed["clerk"]["name"])
        session.transfer_pick(0, self.seed["mapper"]["name"])
        session.click_button("Create role")
        alert = session.wait_for_alert("created successfully")
        r.check("create-role-succeeds", alert is not None, f"alerts={session.alerts()}")

        created = self.api.roles_named(role_name)
        if not r.check("create-role-exists", len(created) == 1, f"found {len(created)} roles named {role_name!r}"):
            return
        role = self.api.role(created[0]["id"])
        expected = set(CLERK) | set(MAPPER) | DEFAULT_AUTHORITIES
        got = set(role.get("authorities") or [])
        r.check("create-role-authorities", got == expected, f"got={sorted(got)} expected={sorted(expected)}")
        description = role.get("description") or ""
        r.check(
            "create-role-description-not-escaped",
            self.seed["mapper"]["name"] in description and "&#x" not in description and "&amp;" not in description,
            f"description={description!r}",
        )

        self.check_can_manage(session, role_name, "superuser-check-created-role", "clerk")
        self.update_role(session, role_name, created[0]["id"])
        # Here rather than as the manager: DHIS2 leaves the searching user
        # out of a non-superuser's user search.
        self.lookup_user(session)

    def check_can_manage(self, session, role_name, test_id, seed_key):
        session.navigate(NAV_CHECK, CHECK_HEADING)
        session.transfer_pick(0, role_name)
        listed = session.list_items(CAN_MANAGE_LIST)
        name = self.seed[seed_key]["name"]
        self.results.check(test_id, name in listed, f"{name!r} not in can-manage list ({len(listed)} items)")

    def update_role(self, session, role_name, role_id):
        r = self.results
        session.navigate(NAV_UPDATE, UPDATE_HEADING)
        session.select_option(role_name)
        session.transfer_pick(0, self.seed["analyst"]["name"])
        session.click_button("Add authorities to role")
        alert = session.wait_for_alert("updated successfully")
        r.check("update-role-succeeds", alert is not None, f"alerts={session.alerts()}")
        role = self.api.role(role_id)
        got = set(role.get("authorities") or [])
        expected = set(CLERK) | set(MAPPER) | set(ANALYST) | DEFAULT_AUTHORITIES
        r.check("update-role-authorities", got == expected, f"got={sorted(got)} expected={sorted(expected)}")
        r.check("update-role-keeps-fields", role.get("name") == role_name and bool(role.get("description")))
        # Read without a reload: proves the role list was refetched.
        self.check_can_manage(session, role_name, "superuser-check-after-update", "analyst")

    def url_sync_steps(self, session):
        major = int(self.server_version.split(".")[1])
        if major < 42:
            self.results.skip("global-shell-url-sync", "no global shell before DHIS2 2.42")
            return
        session.page.goto(f"{self.base}/apps/{self.app_key}", wait_until="domcontentloaded")
        session.wait_for_heading(CHECK_HEADING, 60)
        in_shell = session.frame() != session.page.main_frame
        session.navigate(NAV_CREATE, CREATE_HEADING)
        session.page.wait_for_timeout(1000)
        on_create = "create" in session.page.url
        session.navigate(NAV_CHECK, CHECK_HEADING)
        session.page.wait_for_timeout(1000)
        back = "create" not in session.page.url
        self.results.check(
            "global-shell-url-sync", in_shell and on_create and back, f"in_shell={in_shell} url={session.page.url}"
        )

    # ---- other users ----

    def manager_steps(self, session):
        r = self.results
        held = set(USER_MANAGER + CLERK + [app_authority(self.app_key)])
        session.open_app(self.launch_url)
        session.navigate(NAV_CREATE, CREATE_HEADING)
        r.check("manager-not-guarded", session.frame().get_by_text(GUARD_TEXT).count() == 0)
        shown = sorted(session.transfer_options(0))
        expected = manageable(held, self.api.roles())
        r.check("manager-offered-roles-match", shown == expected, f"shown={shown} expected={expected}")

        role_name = f"{self.prefix} By manager"
        self.state.add("userRoles", name=role_name)
        session.frame().locator('input[type="text"]').first.fill(role_name)
        session.click_button("Create role")
        r.check("manager-create-role-succeeds", session.wait_for_alert("created successfully") is not None)
        created = self.api.roles_named(role_name)
        got = set(self.api.role(created[0]["id"]).get("authorities") or []) if created else set()
        r.check("manager-created-role-authorities", got == DEFAULT_AUTHORITIES, f"got={sorted(got)}")

        self.check_combination(session, [self.seed["manager"], self.seed["analyst"]], "manager-combination-admin")
        self.check_combination(session, [self.seed["clerk"]], "manager-combination-no-admin")
        self.late_authority(session)

    def check_combination(self, session, roles, test_id):
        held = set().union(*(set(role["authorities"]) for role in roles))
        expected = manageable(held, self.api.roles())
        session.navigate(NAV_CHECK, CHECK_HEADING)
        for role in roles:
            session.transfer_pick(0, role["name"])
        if not held & USER_ADMIN_AUTHORITIES:
            notice = session.frame().get_by_text("Cannot administer users").count() > 0
            lists = session.list_items(CAN_MANAGE_LIST) + session.list_items(CANNOT_MANAGE_LIST)
            self.results.check(test_id, notice and not lists, f"notice={notice} items={lists[:5]}")
            return
        listed = session.list_items(CAN_MANAGE_LIST)
        self.results.check(test_id, listed == expected, f"shown={listed} expected={expected}")

    def lookup_user(self, session):
        r = self.results
        session.navigate(NAV_LOOKUP, LOOKUP_HEADING)
        r.check("lookup-no-loader-before-typing", session.frame().locator(LOADER).count() == 0)
        user = self.seed["manager_user"]
        name = f"{user['firstName']} {user['surname']}"
        session.frame().get_by_placeholder("At least 2 characters").fill(self.run_id)
        result = session.frame().locator("button", has_text=name).first
        result.wait_for(timeout=15000)
        result.click()
        session.wait_for(
            lambda f: f.locator(CAN_MANAGE_LIST).count() > 0, 15, "the lookup report's can-manage list"
        )
        expected = manageable(set(self.seed["manager"]["authorities"]), self.api.roles())
        listed = session.list_items(CAN_MANAGE_LIST)
        r.check("lookup-report-matches", listed == expected, f"shown={listed} expected={expected}")

    def late_authority(self, session):
        """A role offered in the picker gains an authority the manager does
        not hold before they submit. The app must refuse to create a role
        that grants it."""
        r = self.results
        clerk = self.seed["clerk"]
        session.navigate(NAV_CREATE, CREATE_HEADING)
        role_name = f"{self.prefix} Late"
        self.state.add("userRoles", name=role_name)
        session.frame().locator('input[type="text"]').first.fill(role_name)
        session.transfer_pick(0, clerk["name"])
        self.put_role_authorities(clerk["id"], clerk["authorities"] + [LATE_AUTHORITY])
        try:
            session.click_button("Create role")
            alert = session.wait_for_alert("do not hold")
            r.check("manager-late-authority-refused", alert is not None, f"alerts={session.alerts()}")
            r.check("manager-late-authority-no-role", not self.api.roles_named(role_name))
        finally:
            self.put_role_authorities(clerk["id"], clerk["authorities"])

    def put_role_authorities(self, uid, authorities):
        role = self.api.get(f"/api/userRoles/{uid}?fields=:owner")
        status, body = self.api.request("PUT", f"/api/userRoles/{uid}", {**role, "authorities": authorities})
        if status != 200:
            raise ApiError(f"PUT userRoles/{uid} returned {status}: {str(body)[:200]}")

    def readonly_steps(self, session):
        r = self.results
        session.open_app(self.launch_url)
        frame = session.frame()
        r.check(
            "readonly-no-write-nav",
            frame.get_by_text(NAV_CREATE).count() == 0 and frame.get_by_text(NAV_UPDATE).count() == 0,
        )
        r.check("readonly-check-nav", frame.get_by_text(NAV_CHECK).count() > 0)
        # A hash is honoured on a second navigation, once the app is up.
        session.page.goto(self.launch_url.split("#", 1)[0] + "#/create", wait_until="domcontentloaded")
        guarded = session.wait_for(lambda f: f.get_by_text(GUARD_TEXT).count() > 0, 20, "the authority guard")
        r.check("readonly-create-guarded", guarded is not None)

    def noaccess_steps(self, session):
        session.page.goto(self.launch_url, wait_until="domcontentloaded")
        session.page.wait_for_timeout(8000)
        frame = session.frame()
        rendered = any(
            frame.locator("h1", has_text=heading).count() > 0 for heading in (CHECK_HEADING, CREATE_HEADING)
        )
        self.results.check("noaccess-app-not-rendered", not rendered, "the app rendered for a user without access")
        # DHIS2 refuses the app's own requests for this user; that is the
        # expected outcome here, not an app error.
        session.http_errors.clear()

    # ---- teardown ----

    def clean_up(self):
        left = self.state.clean_up()
        self.results.check("cleanup-seeded-objects", not left, f"left behind: {left}")
        status = self.api.uninstall_app(self.app_key)
        self.results.check("cleanup-uninstall-app", status in (200, 204), f"http {status}")

    def run(self):
        self.prepare()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    self.scenario(browser, "superuser", None, self.superuser_steps)
                    self.scenario(browser, "url-sync", None, self.url_sync_steps)
                    self.scenario(browser, "manager", self.seed["manager_user"], self.manager_steps)
                    self.scenario(browser, "readonly", self.seed["readonly_user"], self.readonly_steps)
                    self.scenario(browser, "noaccess", self.seed["noaccess_user"], self.noaccess_steps)
                finally:
                    browser.close()
        finally:
            self.clean_up()

    def write_results(self, started, error=None):
        tests = self.results.tests if self.results and not error else []
        counts = {s: sum(1 for t in tests if t["status"] == s) for s in ("pass", "fail", "skip")}
        payload = {
            "contract_version": CONTRACT_VERSION,
            "label": self.label or "",
            "server_version": self.server_version,
            "app_key": self.app_key,
            "app_version": self.app_version,
            "duration_s": round(time.monotonic() - started),
            "total": len(tests),
            "passed": counts["pass"],
            "failed": counts["fail"],
            "skipped": counts["skip"],
            "tests": tests,
        }
        if error:
            payload["error"] = error
        (self.results_dir / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
        return payload


def main():
    started = time.monotonic()
    try:
        run = Run()
    except SetupError as err:
        print(f"setup failed ({err.stage}): {err}", file=sys.stderr)
        return EXIT_ERROR
    try:
        run.run()
    except SetupError as err:
        print(f"setup failed ({err.stage}): {err}", file=sys.stderr)
        with contextlib.suppress(Exception):
            run.write_results(started, error=f"{err.stage}: {err}")
        with contextlib.suppress(Exception):
            run.state.clean_up()
            run.api.uninstall_app(run.app_key)
        return EXIT_ERROR
    payload = run.write_results(started)
    print(f"[{run.label}] {payload['passed']} passed, {payload['failed']} failed, {payload['skipped']} skipped")
    return EXIT_FAIL if payload["failed"] else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
