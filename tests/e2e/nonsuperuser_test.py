#!/usr/bin/env python3
"""Checks the app for non-superusers. Two scenarios, both cleaned up afterwards:

1. A user allowed to manage roles (user-management authorities + app access):
   the app must offer exactly the roles canManageRole() allows, and creating a
   role must work. The other suites run as a superuser, where every role is
   manageable and that filter is never really exercised.
2. A user who can open the app but not manage roles (app access only): the app
   must show the "Missing permissions" warning and disable the Create button.

Usage:
  DHIS2_BASE_URL=http://dhis2-<instance>:8080 DHIS2_ADMIN_PASSWORD=<password> \
      python3 nonsuperuser_test.py

DHIS2_ADMIN_USER defaults to "local_admin" and must be a superuser (hold ALL):
DHIS2 refuses to grant a user a role carrying authorities the acting user lacks,
which the demo `admin` account does not satisfy on every seed.
"""
import base64
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE = os.environ.get("DHIS2_BASE_URL")
if not BASE:
    sys.exit("DHIS2_BASE_URL is required (see usage in the module docstring)")
HOST = BASE.split("://", 1)[1].split(":")[0]
ADMIN_USER = os.environ.get("DHIS2_ADMIN_USER", "local_admin")
ADMIN_PASSWORD = os.environ.get("DHIS2_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    sys.exit("DHIS2_ADMIN_PASSWORD is required (see usage in the module docstring)")

PROJECT_DIR = Path(__file__).parents[2]
APP_KEY = json.loads((PROJECT_DIR / "package.json").read_text())["name"]
# DHIS2 derives an app's access authority from its key, minus non-alphanumerics
APP_AUTHORITY = "M_" + re.sub(r"[^A-Za-z0-9]", "", APP_KEY)
# What the tester holds: enough to open the app and add roles, nothing more
TESTER_AUTHORITIES = [
    "F_USER_ADD",
    "F_USER_VIEW",
    "F_USER_DELETE",
    "F_USERROLE_PUBLIC_ADD",
    "M_dhis-web-user",
    APP_AUTHORITY,
]
# Enough to open the app, but not to add roles
READ_ONLY_AUTHORITIES = ["F_USER_VIEW", "M_dhis-web-user", APP_AUTHORITY]
# Preselected on the create page, and all held by the tester
DEFAULT_AUTHORITIES = {"F_USER_ADD", "F_USER_DELETE", "F_USER_VIEW", "M_dhis-web-user"}
AUTHORITY_ALL = "ALL"

CREATE_HEADING = "Create new user admin role"
CHECK_HEADING = "Check what a role combination can manage"
LOOKUP_HEADING = "Look up a user"
GUARD_TEXT = "This page needs one of these authorities"
NAV_CREATE = "Create new role"
NAV_UPDATE = "Update existing role"
NAV_CHECK = "Role combination"
NAV_LOOKUP = "Look up user"
TRANSFER = '[data-test="dhis2-uicore-transfer"]'
TRANSFER_OPTION = '[data-test="dhis2-uicore-transferoption"]'
CAN_MANAGE_LIST = '[data-test="can-manage-list"] li'
CANNOT_MANAGE_LIST = '[data-test="cannot-manage-list"] li'
ALERTBAR = '[data-test="dhis2-uicore-alertbar"]'
LOADER = '[data-test="dhis2-uicore-circularloader"]'
# The search field's placeholder, from CheckUserPage's MIN_QUERY_LENGTH (2).
SEARCH_PLACEHOLDER = "At least 2 characters"
# Authorities that let a role administer users at all — mirrors
# canAdministerUsers() in src/domain/userRole.ts.
USER_ADMIN_AUTHORITIES = {"ALL", "F_USER_ADD", "F_USER_ADD_WITHIN_MANAGED_GROUP"}

OUT = Path(__file__).parent / "output" / "nonsuperuser"
OUT.mkdir(parents=True, exist_ok=True)
results = []


def rec(step, status, detail=""):
    results.append((step, status, detail))
    print(f"{status}: {step} {('- ' + detail) if detail else ''}", flush=True)


def api(method, path, data=None, user=ADMIN_USER, password=ADMIN_PASSWORD):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=None if data is None else json.dumps(data).encode(),
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode(),
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read().decode()
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body[:300]}


def created_uid(status, payload):
    """UID from an import report — but only when the import actually succeeded:
    DHIS2 returns a uid alongside the errors on a 409 as well."""
    if status not in (200, 201):
        return None
    return (payload.get("response") or {}).get("uid")


def cookie(user, password):
    req = urllib.request.Request(
        f"{BASE}/api/me",
        headers={"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()},
    )
    with urllib.request.urlopen(req) as r:
        for c in r.headers.get_all("Set-Cookie") or []:
            name, _, value = c.split(";", 1)[0].partition("=")
            if "JSESSIONID" in name:
                return name.strip(), value.strip()
    raise RuntimeError("no session cookie returned")


def app_frame(page):
    for f in page.frames:
        if APP_KEY in (f.url or "") and f != page.main_frame:
            return f
    return page.main_frame


def wait_for_heading(page, heading, timeout_s=10):
    """Poll app_frame(page) fresh on every attempt: the global shell can
    swap the app iframe for a new frame instance shortly after an in-app
    navigation, and a locator built from a captured-then-stale frame would
    otherwise wait out the full timeout even though the heading is already
    visible in the new frame."""
    deadline = time.monotonic() + timeout_s
    frame = app_frame(page)
    while time.monotonic() < deadline:
        frame = app_frame(page)
        if frame.locator("h1", has_text=heading).count() > 0:
            return frame
        page.wait_for_timeout(300)
    raise PlaywrightTimeoutError(f'heading "{heading}" never appeared (url={frame.url})')


def expected_manageable_roles(held):
    """The roles the app should offer, per canManageRole() in src/domain/userRole.ts."""
    _, res = api("GET", "/api/userRoles?fields=id,displayName,authorities&paging=false")
    manageable = []
    for role in res.get("userRoles", []):
        authorities = role.get("authorities") or []
        if AUTHORITY_ALL in authorities:
            continue
        if all(a in held for a in authorities):
            manageable.append(role["displayName"])
    return sorted(manageable)


def find_no_admin_role():
    """A role holding none of the user-administration authorities, so the
    Check page's "cannot administer users" branch actually gets exercised.
    Discovered from the API rather than hardcoded: a fixed pair like
    ["User manager", "M and E Officer"] never reaches that branch (User
    manager carries F_USER_ADD), and this suite must also run against demo
    seeds (e.g. Laos) where Sierra Leone's role names don't exist."""
    _, res = api("GET", "/api/userRoles?fields=id,displayName,authorities&paging=false")
    for role in res.get("userRoles", []):
        authorities = set(role.get("authorities") or [])
        if not authorities & USER_ADMIN_AUTHORITIES:
            return role["displayName"]
    return None


def find_admin_capable_pair():
    """Two roles to check together, at least one carrying a user-administration
    authority so the combination can actually manage somebody. Discovered, not
    named: Sierra Leone has "User manager"/"M and E Officer", Laos has
    "Admin"/"Analytics"/"Data capture", and a hard-coded pair fails on the
    other seed with a KeyError."""
    _, res = api("GET", "/api/userRoles?fields=id,displayName,authorities&paging=false")
    roles = [r for r in res.get("userRoles", [])
             if "ALL" not in (r.get("authorities") or [])]
    admin = next((r for r in roles
                  if set(r.get("authorities") or []) & USER_ADMIN_AUTHORITIES), None)
    if not admin:
        return []
    other = next((r for r in roles
                  if r["displayName"] != admin["displayName"]
                  and (r.get("authorities") or [])), None)
    return [admin["displayName"]] + ([other["displayName"]] if other else [])


def find_lookup_user():
    """A real user's display name, for the user-lookup flow. Not hardcoded,
    for the same seed-portability reason as find_no_admin_role()."""
    _, res = api("GET", "/api/users?fields=id,displayName&pageSize=50")
    for user in res.get("users", []):
        name = (user.get("displayName") or "").strip()
        if len(name) >= 3:
            return name
    return None


def create_role(name, authorities):
    st, resp = api("POST", "/api/userRoles", {
        "name": name,
        "description": "temporary role for the non-superuser e2e check",
        "authorities": authorities,
    })
    uid = created_uid(st, resp)
    rec(f"Create role {name}", "PASS" if uid else "FAIL", f"http {st} {str(resp)[:160]}")
    return uid


def create_user(username, password, role_uid):
    _, ous = api("GET", "/api/organisationUnits?level=1&fields=id&pageSize=1")
    st, resp = api("POST", "/api/users", {
        "username": username,
        "password": password,
        "firstName": "Agent",
        "surname": "Tester",
        "userRoles": [{"id": role_uid}],
        "organisationUnits": [{"id": ous["organisationUnits"][0]["id"]}],
    })
    uid = created_uid(st, resp)
    rec(f"Create user {username}", "PASS" if uid else "FAIL", f"http {st} {str(resp)[:160]}")
    return uid


def open_app_as(page, username, password):
    cookie_name, cookie_value = cookie(username, password)
    page.context.add_cookies([
        {"name": cookie_name, "value": cookie_value, "domain": HOST, "path": "/"}
    ])
    page.goto(f"{BASE}/api/apps/{APP_KEY}/index.html", wait_until="domcontentloaded")
    # On 2.42+ the app renders inside the global-shell iframe, which appears
    # some time after domcontentloaded — poll for the frame and its heading
    # rather than guessing a fixed delay. The app now lands on the Check
    # page ("/") by default for anyone who can open it, regardless of
    # role-management authority.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        frame = app_frame(page)
        try:
            frame.locator("h1", has_text=CHECK_HEADING).wait_for(timeout=2000)
            rec("App loads for non-superuser with app access", "PASS")
            return frame
        except PlaywrightTimeoutError:
            page.wait_for_timeout(500)
    frame = app_frame(page)
    notices = frame.locator('[data-test="dhis2-uicore-noticebox"]').all_inner_texts()
    page.screenshot(path=str(OUT / "app-did-not-render.png"), full_page=True)
    rec("App loads for non-superuser with app access", "FAIL",
        f"heading never rendered; frames={len(page.frames)} url={page.url} notices={notices}")
    return None


def check_manageable_roles(frame, held):
    # The manager holds a create/update authority, so the route guard must
    # not be showing — GUARD_TEXT is what would actually appear if this
    # user were wrongly gated off the Create page.
    guarded = frame.get_by_text(GUARD_TEXT).count() > 0
    rec("No missing-permission warning", "PASS" if not guarded else "FAIL")
    shown = sorted(
        text.strip()
        for text in frame.locator(TRANSFER).nth(0).locator(TRANSFER_OPTION).all_inner_texts()
    )
    expected = expected_manageable_roles(held)
    rec("Manageable roles match canManageRole()", "PASS" if shown == expected else "FAIL",
        f"shown={shown} expected={expected}")


def create_role_as_tester(page, frame, role_name):
    frame.locator('input[type="text"]').first.fill(role_name)
    frame.locator("button", has_text="Create role").click()
    try:
        frame.locator(ALERTBAR, has_text="created successfully").wait_for(timeout=15000)
        rec("Non-superuser can create a role (preselected defaults only)", "PASS")
    except Exception:
        rec("Non-superuser can create a role (preselected defaults only)", "FAIL",
            f"alerts={frame.locator(ALERTBAR).all_inner_texts()}")
    page.screenshot(path=str(OUT / "nonsuperuser-after-create.png"), full_page=True)

    st, res = api("GET", f"/api/userRoles?filter=name:eq:{urllib.request.quote(role_name)}"
                         "&fields=id,authorities")
    found = res.get("userRoles", []) if st == 200 else []
    if not found:
        rec("API verify: created role holds exactly the default authorities", "FAIL", "role not found")
        return None
    authorities = set(found[0].get("authorities") or [])
    rec("API verify: created role holds exactly the default authorities",
        "PASS" if authorities == DEFAULT_AUTHORITIES else "FAIL", f"got={sorted(authorities)}")
    return found[0]["id"]


def check_read_only_user(frame):
    """The write pages are gated off entirely for a user without
    role-management authority: no create/update nav, no page to render even
    on direct navigation to the route."""
    create_visible = frame.get_by_text(NAV_CREATE).count() > 0
    update_visible = frame.get_by_text(NAV_UPDATE).count() > 0
    rec("Read-only user: no create/update nav", "PASS" if not create_visible and not update_visible else "FAIL",
        f"create_visible={create_visible} update_visible={update_visible}")
    check_visible = frame.get_by_text(NAV_CHECK).count() > 0
    rec("Read-only user: check section available", "PASS" if check_visible else "FAIL")

    # Direct navigation to the guarded route: per the app's own navigation
    # rule, a hash is only honored on a *second* navigation — the shell
    # ignores it on the very first load — so land on the root first.
    page = frame.page
    page.goto(f"{BASE}/api/apps/{APP_KEY}/index.html", wait_until="domcontentloaded")
    wait_for_heading(page, CHECK_HEADING, timeout_s=15)
    page.goto(f"{BASE}/api/apps/{APP_KEY}/index.html#/create", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    guarded = app_frame(page).get_by_text(GUARD_TEXT).count() > 0
    rec("Read-only user: /create is guarded", "PASS" if guarded else "FAIL")


def browser_page(p):
    context = p.chromium.launch().new_context(viewport={"width": 1400, "height": 1000})
    return context.new_page()


def check_role_combination(page, frame, role_names):
    """Select roles on the Check page and compare the verdict with the API."""
    _, res = api("GET", "/api/userRoles?fields=id,displayName,authorities&paging=false")
    roles = res["userRoles"]
    by_name = {r["displayName"]: r for r in roles}
    held = set()
    for name in role_names:
        held |= set(by_name[name].get("authorities") or [])
    can_administer = bool(held & USER_ADMIN_AUTHORITIES)
    expected = sorted(
        r["displayName"]
        for r in roles
        if "ALL" not in (r.get("authorities") or [])
        and all(a in held for a in (r.get("authorities") or []))
    ) if can_administer else []

    frame.locator("a", has_text=NAV_CHECK).click()
    frame = wait_for_heading(page, CHECK_HEADING, timeout_s=10)
    transfer = frame.locator(TRANSFER).first
    for name in role_names:
        transfer.locator(
            '[data-test="dhis2-uicore-transfer-filter"] input'
        ).first.fill(name)
        page.wait_for_timeout(400)
        options = [t.strip() for t in transfer.locator(TRANSFER_OPTION).all_inner_texts()]
        index = next(i for i, t in enumerate(options) if name in t)
        transfer.locator(TRANSFER_OPTION).nth(index).dblclick()
        page.wait_for_timeout(400)

    if not can_administer:
        shown = frame.get_by_text("Cannot administer users").count() > 0
        no_lists = (
            frame.locator(CAN_MANAGE_LIST).count() == 0
            and frame.locator(CANNOT_MANAGE_LIST).count() == 0
        )
        rec("Check page: combination without user-admin authority",
            "PASS" if shown and no_lists else "FAIL",
            f"notice_shown={shown} no_lists={no_lists}")
        return

    listed = sorted(t.strip() for t in frame.locator(CAN_MANAGE_LIST).all_inner_texts())
    rec("Check page: can-manage list matches the API", "PASS" if listed == expected else "FAIL",
        f"shown={listed[:5]} expected={expected[:5]}")


def check_user_lookup(page, frame):
    """Navigate in-app to "Look up user" and search for a real, seed-agnostic
    user. Also the regression check for the infinite-spinner/stale-results
    bug (a disabled TanStack Query keeps status 'loading'): no loader should
    be visible before anything is typed."""
    frame.locator("a", has_text=NAV_LOOKUP).click()
    frame = wait_for_heading(page, LOOKUP_HEADING, timeout_s=10)

    loader_before = frame.locator(LOADER).count() > 0
    rec("User lookup: no loader before typing", "PASS" if not loader_before else "FAIL")

    name = find_lookup_user()
    if not name:
        rec("User lookup: search and select a user", "SKIP",
            "no user with a usable display name found on this seed")
        return
    fragment = name[: max(3, len(name) // 2)].strip() or name

    frame.get_by_placeholder(SEARCH_PLACEHOLDER).fill(fragment)
    page.wait_for_timeout(700)  # debounce (300ms) plus the search request

    results = frame.locator("button", has_text=fragment)
    try:
        results.first.wait_for(timeout=10000)
    except PlaywrightTimeoutError:
        rec("User lookup: search and select a user", "FAIL",
            f"no result for fragment {fragment!r} of {name!r}")
        return
    results.first.click()
    page.wait_for_timeout(500)

    report_shown = (
        frame.get_by_text("Can administer users", exact=False).count() > 0
        or frame.get_by_text("Cannot administer users").count() > 0
        or frame.locator(CAN_MANAGE_LIST).count() > 0
        or frame.locator(CANNOT_MANAGE_LIST).count() > 0
    )
    rec("User lookup: report renders for selected user", "PASS" if report_shown else "FAIL")


def drive_app(username, password, role_name):
    """Returns the uid of the role created through the UI, if any."""
    with sync_playwright() as p:
        page = browser_page(p)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            frame = open_app_as(page, username, password)
            if not frame:
                page.screenshot(path=str(OUT / "nonsuperuser-blocked.png"), full_page=True)
                return None
            frame.locator("a", has_text=NAV_CREATE).click()
            try:
                frame = wait_for_heading(page, CREATE_HEADING, timeout_s=10)
            except PlaywrightTimeoutError as e:
                rec("Manager can navigate to Create page", "FAIL", str(e)[:150])
                return None
            check_manageable_roles(frame, set(TESTER_AUTHORITIES))
            page.screenshot(path=str(OUT / "nonsuperuser-create-page.png"), full_page=True)
            # Capture the uid before the role-combination check: that check
            # navigates away and drives another Transfer, and if it raises
            # (a frame-race timeout, or a role name not found in the
            # picker), the already-created role must still make it back to
            # the caller's cleanup rather than being silently leaked.
            new_role_uid = create_role_as_tester(page, frame, role_name)
            admin_pair = find_admin_capable_pair()
            if not admin_pair:
                # Passing [] would select nothing, so the Check page would
                # show its default "no roles selected" state and the
                # no-user-admin branch below would record a PASS for a
                # scenario that was never exercised.
                rec("Check page: role-combination check", "SKIP",
                    "no non-ALL role on this instance carries a user-administration authority")
            else:
                try:
                    check_role_combination(page, app_frame(page), admin_pair)
                except Exception as e:
                    rec("Check page: role-combination check", "FAIL",
                        f"raised {type(e).__name__}: {str(e)[:150]}")

            no_admin_role = find_no_admin_role()
            if no_admin_role:
                try:
                    check_role_combination(page, app_frame(page), [no_admin_role])
                except Exception as e:
                    rec("Check page: no-admin role-combination check", "FAIL",
                        f"raised {type(e).__name__}: {str(e)[:150]}")
            else:
                rec("Check page: no-admin role-combination check", "SKIP",
                    "no role without a user-administration authority exists on this seed")

            try:
                check_user_lookup(page, app_frame(page))
            except Exception as e:
                rec("User lookup flow", "FAIL", f"raised {type(e).__name__}: {str(e)[:150]}")

            return new_role_uid
        finally:
            rec("No page errors", "PASS" if not errors else "FAIL", "; ".join(errors)[:150])
            page.context.browser.close()


def cleanup(uids):
    for resource, uid in uids:
        if uid:
            st, _ = api("DELETE", f"/api/{resource}/{uid}")
            rec(f"Cleanup: delete {resource}/{uid}", "PASS" if st in (200, 204) else "FAIL", f"http {st}")


def run_manager_scenario(stamp):
    """Scenario 1: a non-superuser who may manage roles."""
    username = f"agent_ura_tester_{stamp}"
    password = "Xy7!" + secrets.token_hex(8)
    role_uid = user_uid = new_role_uid = None
    try:
        role_uid = create_role(f"Agent URA Tester {stamp}", TESTER_AUTHORITIES)
        if role_uid:
            user_uid = create_user(username, password, role_uid)
        if user_uid:
            new_role_uid = drive_app(username, password, f"Agent NonSuper Role {stamp}")
    finally:
        cleanup([("userRoles", new_role_uid), ("users", user_uid), ("userRoles", role_uid)])


def run_read_only_scenario(stamp):
    """Scenario 2: a user who can open the app but not manage roles."""
    username = f"agent_ura_readonly_{stamp}"
    password = "Xy7!" + secrets.token_hex(8)
    role_uid = user_uid = None
    try:
        role_uid = create_role(f"Agent URA ReadOnly {stamp}", READ_ONLY_AUTHORITIES)
        if role_uid:
            user_uid = create_user(username, password, role_uid)
        if not user_uid:
            return
        with sync_playwright() as p:
            page = browser_page(p)
            frame = open_app_as(page, username, password)
            if frame:
                check_read_only_user(frame)
                page.screenshot(path=str(OUT / "readonly-user.png"), full_page=True)
            page.context.browser.close()
    finally:
        cleanup([("users", user_uid), ("userRoles", role_uid)])


def main():
    stamp = int(time.time())
    run_manager_scenario(stamp)
    run_read_only_scenario(stamp)
    fails = [r for r in results if r[1] == "FAIL"]
    print(f"\n{len(results)} steps, {len(fails)} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
