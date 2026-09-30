#!/usr/bin/env python3
"""Extra tests: global-shell URL sync (2.42+, skipped below that) + non-privileged user warning.

Usage:
  DHIS2_BASE_URL=http://dhis2-<instance>:8080 DHIS2_ADMIN_PASSWORD=<password> python3 extra_tests.py

DHIS2_ADMIN_USER defaults to "admin"; broker/demo instances use the standard demo password.
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

from playwright.sync_api import sync_playwright

BASE = os.environ.get("DHIS2_BASE_URL")
if not BASE:
    sys.exit("DHIS2_BASE_URL is required (see usage in the module docstring)")
HOST = BASE.split("://", 1)[1].split(":")[0]
ADMIN_USER = os.environ.get("DHIS2_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("DHIS2_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    sys.exit("DHIS2_ADMIN_PASSWORD is required (see usage in the module docstring)")
# temporary non-privileged user, created and deleted by this script
LIMITED_USERNAME = "agent_review_limited"
LIMITED_PASSWORD = "Xy7!" + secrets.token_hex(8)
# The DHIS2 app key equals the app name in package.json / d2.config.js
APP_KEY = json.loads((Path(__file__).parents[2] / "package.json").read_text())["name"]
# DHIS2 derives an app's access authority from its key, minus non-alphanumerics
APP_AUTHORITY = "M_" + re.sub(r"[^A-Za-z0-9]", "", APP_KEY)
OUT = Path(__file__).parent / "output" / "extra-tests"
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
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            return r.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None


def cookie(user, password):
    req = urllib.request.Request(
        f"{BASE}/api/me",
        headers={"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()},
    )
    with urllib.request.urlopen(req) as r:
        for c in r.headers.get_all("Set-Cookie") or []:
            head = c.split(";", 1)[0]
            n, _, v = head.partition("=")
            if "JSESSIONID" in n:
                return n.strip(), v.strip()
    raise RuntimeError("no cookie")


def dhis2_major():
    """Major version of the target instance, e.g. 41 for 2.41.9.1."""
    _, info = api("GET", "/api/system/info")
    parts = (info.get("version") or "").split(".")
    if parts[0] == "2":
        parts = parts[1:]
    return int(parts[0]) if parts and parts[0].isdigit() else 0


def app_frame(page):
    for f in page.frames:
        if APP_KEY in (f.url or "") and f != page.main_frame:
            return f
    return page.main_frame


def test_url_sync(p):
    # The global shell (and the /apps/<key> path) only exists on 2.42+
    if dhis2_major() < 42:
        rec("Global shell URL sync", "SKIP", "requires DHIS2 2.42+")
        return
    cn, cv = cookie(ADMIN_USER, ADMIN_PASSWORD)
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_cookies([{"name": cn, "value": cv, "domain": HOST, "path": "/"}])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # global shell path on 2.42+
    page.goto(f"{BASE}/apps/{APP_KEY}", wait_until="domcontentloaded")
    # The global-shell iframe mounts some time after domcontentloaded — poll
    # for the app's nav rather than guessing a fixed delay, which was flaky.
    deadline = time.monotonic() + 20
    f = app_frame(page)
    while time.monotonic() < deadline:
        f = app_frame(page)
        if f.get_by_text("Update existing role").count() > 0:
            break
        page.wait_for_timeout(300)
    in_shell = f != page.main_frame
    rec("Global shell wraps app in iframe", "PASS" if in_shell else "WARN", f"frames={len(page.frames)}")
    f.locator("a", has_text="Update existing role").click()
    page.wait_for_timeout(1500)
    url = page.url
    rec("URL syncs with global shell on navigation", "PASS" if "update" in url else "FAIL", f"url={url}")
    page.screenshot(path=str(OUT / "urlsync.png"), full_page=True)
    # navigate back
    f = app_frame(page)
    f.locator("a", has_text="Create new role").click()
    page.wait_for_timeout(1000)
    rec("URL syncs back", "PASS" if "update" not in page.url else "FAIL", f"url={page.url}")
    rec("No page errors during shell navigation", "PASS" if not errors else "FAIL", "; ".join(errors)[:150])
    b.close()


def test_nonprivileged(p):
    # A role carrying no app access and no user administration, so the user
    # holding it must not be able to open the app at all. Discovered rather
    # than named ("Data entry clerk" exists only on the Sierra Leone seeds;
    # this script also runs against Laos).
    st, roles = api("GET", "/api/userRoles?fields=id,displayName,authorities&paging=false")
    blocked = [
        r for r in roles.get("userRoles", [])
        if not (set(r.get("authorities") or []) & {"ALL", APP_AUTHORITY})
    ]
    if not blocked:
        rec("Find a role without app access", "SKIP", "every role on this instance can open the app")
        return None
    clerk_id = blocked[0]["id"]
    # find an org unit
    st, ous = api("GET", "/api/organisationUnits?level=1&fields=id&pageSize=1")
    ou = ous["organisationUnits"][0]["id"]
    payload = {
        "username": LIMITED_USERNAME,
        "password": LIMITED_PASSWORD,
        "firstName": "Agent",
        "surname": "Limited",
        "userRoles": [{"id": clerk_id}],
        "organisationUnits": [{"id": ou}],
    }
    st, resp = api("POST", "/api/users", payload)
    uid = None
    if st in (200, 201) and resp and resp.get("response"):
        uid = resp["response"].get("uid")
    rec("Create limited test user", "PASS" if uid else "FAIL", f"http {st} uid={uid}")
    if not uid:
        return None

    try:
        cn, cv = cookie(LIMITED_USERNAME, LIMITED_PASSWORD)
    except Exception as e:
        rec("Limited user login", "FAIL", str(e)[:100])
        return uid
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_cookies([{"name": cn, "value": cv, "domain": HOST, "path": "/"}])
    page = ctx.new_page()
    page.goto(f"{BASE}/api/apps/{APP_KEY}/index.html", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    f = app_frame(page)
    page.screenshot(path=str(OUT / "limited-user.png"), full_page=True)
    # The limited user holds only "Data entry clerk" and so lacks the app's
    # own access authority — DHIS2 must refuse to serve the app UI at all.
    # Check both known landing headings (version-agnostic: 2.40/2.41 serve
    # the app at top level, 2.42+ inside the global shell) rather than the
    # shell's exact error copy, so this does not rot the next time the
    # default route changes.
    rendered = (
        f.locator("h1", has_text="Check what a role combination can manage").count() > 0
        or f.locator("h1", has_text="Create new user admin role").count() > 0
    )
    rec("App does not render for a user without app access",
        "PASS" if not rendered else "FAIL",
        "" if not rendered else "app UI rendered despite missing app-access authority")
    b.close()
    return uid


with sync_playwright() as p:
    test_url_sync(p)
    uid = test_nonprivileged(p)

# cleanup user
if uid:
    st, _ = api("DELETE", f"/api/users/{uid}")
    rec("Cleanup: delete limited user", "PASS" if st in (200, 204) else "FAIL", f"http {st}")

fails = [r for r in results if r[1] == "FAIL"]
(Path(OUT) / "results.json").write_text(json.dumps(results, indent=2))
sys.exit(1 if fails else 0)
