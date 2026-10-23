"""DHIS2 Web API access for the e2e suite: requests, app install, and the
dataStore record of what a run creates (TESTING.md, "Seeding and cleanup")."""

import base64
import io
import json
import re
import secrets
import string
import urllib.error
import urllib.parse
import urllib.request
import zipfile

STATE_NAMESPACE = "e2e-state"
STATE_KEY = "tool-user-role-aggregator"
# Delete users before the roles they hold, and roles before org units.
DELETE_ORDER = ["users", "userRoles", "organisationUnits"]
DELETE_PASSES = 3
UID_FIRST = string.ascii_letters
UID_REST = string.ascii_letters + string.digits
REQUEST_TIMEOUT_S = 120


class ApiError(RuntimeError):
    pass


def new_uid():
    """A DHIS2 UID, made client side so it can be recorded before use."""
    return secrets.choice(UID_FIRST) + "".join(secrets.choice(UID_REST) for _ in range(10))


def app_authority(app_key):
    """DHIS2 names an app's access authority after its key, minus
    everything that is not a letter or digit."""
    return "M_" + re.sub(r"[^A-Za-z0-9]", "", app_key)


def read_manifest(zip_path):
    with zipfile.ZipFile(zip_path) as bundle:
        return json.loads(bundle.read("manifest.webapp"))


class Dhis2:
    def __init__(self, base, user, password):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password

    def auth_header(self, user=None, password=None):
        token = f"{user or self.user}:{password or self.password}".encode()
        return "Basic " + base64.b64encode(token).decode()

    def request(self, method, path, data=None, content_type="application/json"):
        """Returns (status, parsed JSON or raw text). Never raises on an
        HTTP error status, so callers can assert on it."""
        body = data
        if data is not None and not isinstance(data, bytes):
            body = json.dumps(data).encode()
        headers = {"Authorization": self.auth_header(), "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(f"{self.base}{path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as res:
                return res.status, parse_body(res.read())
        except urllib.error.HTTPError as err:
            return err.code, parse_body(err.read())

    def get(self, path):
        status, body = self.request("GET", path)
        if status != 200:
            raise ApiError(f"GET {path} returned {status}: {str(body)[:200]}")
        return body

    def warm_up(self):
        """On a freshly started 2.41, /api/authorities fails with a 500
        until the legacy Struts layer has served one page. A browser
        sign-in does that; an API-only client must do it by hand."""
        req = urllib.request.Request(f"{self.base}/dhis-web-commons/security/login.action")
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S):
                pass
        except urllib.error.URLError:
            pass  # absent on 2.42 and later, where nothing needs warming

    def system_version(self):
        return self.get("/api/system/info")["version"]

    def session_cookie(self, user, password):
        """A session cookie for `user`, so the browser starts signed in."""
        req = urllib.request.Request(
            f"{self.base}/api/me",
            headers={"Authorization": self.auth_header(user, password)},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as res:
            for header in res.headers.get_all("Set-Cookie") or []:
                name, _, value = header.split(";", 1)[0].partition("=")
                if "JSESSIONID" in name:
                    return name.strip(), value.strip()
        raise ApiError(f"no session cookie returned for {user}")

    # ---- apps ----

    def install_app(self, zip_path):
        boundary = "----e2e" + secrets.token_hex(8)
        with open(zip_path, "rb") as handle:
            payload = handle.read()
        body = io.BytesIO()
        body.write(
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="app.zip"\r\n'
                "Content-Type: application/zip\r\n\r\n"
            ).encode()
        )
        body.write(payload)
        body.write(f"\r\n--{boundary}--\r\n".encode())
        status, res = self.request(
            "POST", "/api/apps", body.getvalue(), f"multipart/form-data; boundary={boundary}"
        )
        # 201 on 2.42 and later, 204 on 2.41 and earlier.
        if not 200 <= status < 300:
            raise ApiError(f"app install returned {status}: {str(res)[:200]}")

    def find_app(self, manifest_name):
        return next((app for app in self.get("/api/apps") if app.get("name") == manifest_name), None)

    def uninstall_app(self, key):
        status, _ = self.request("DELETE", f"/api/apps/{urllib.parse.quote(key)}")
        return status

    # ---- metadata ----

    def create(self, resource, payload):
        status, res = self.request("POST", f"/api/{resource}", payload)
        if status not in (200, 201):
            raise ApiError(f"POST /api/{resource} returned {status}: {str(res)[:300]}")

    def delete(self, resource, uid):
        """Returns None once the object is gone, else the failing response."""
        status, body = self.request("DELETE", f"/api/{resource}/{uid}")
        if status in (200, 204, 404):
            return None
        return f"{status} {str(body)[:200]}"

    def roles(self):
        return self.get("/api/userRoles?fields=id,name,displayName,description,authorities&paging=false")[
            "userRoles"
        ]

    def role(self, uid):
        return self.get(f"/api/userRoles/{uid}?fields=id,name,description,authorities")

    def roles_named(self, name):
        query = urllib.parse.urlencode({"filter": f"name:eq:{name}", "fields": "id,name", "paging": "false"})
        return self.get(f"/api/userRoles?{query}")["userRoles"]

    def system_authorities(self):
        return {a["id"] for a in self.get("/api/authorities")["systemAuthorities"]}

    def root_org_unit(self):
        units = self.get("/api/organisationUnits?filter=level:eq:1&fields=id&paging=false")["organisationUnits"]
        return units[0]["id"] if units else None


def parse_body(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw[:500].decode(errors="replace")


class StateRecord:
    """What this run created, kept on the instance at e2e-state/<repo>.

    Each entry is written before its object is created. An entry has a UID,
    or, for roles the app itself creates (where the server assigns the UID),
    the run-unique role name to look up."""

    def __init__(self, api):
        self.api = api
        self.path = f"/api/dataStore/{STATE_NAMESPACE}/{STATE_KEY}"
        self.entries = []

    def load(self):
        status, body = self.api.request("GET", self.path)
        if status == 404:
            return []
        if status != 200:
            raise ApiError(f"reading the state record returned {status}")
        return (body or {}).get("objects", [])

    def save(self):
        status, _ = self.api.request("PUT", self.path, {"objects": self.entries})
        if status == 404:
            status, _ = self.api.request("POST", self.path, {"objects": self.entries})
        if status not in (200, 201):
            raise ApiError(f"writing the state record returned {status}")

    def add(self, resource, uid=None, name=None):
        self.entries.append({"type": resource, "id": uid, "name": name})
        self.save()

    def delete_all(self, entries):
        """Deletes the listed objects; returns the entries it could not
        delete. Objects can block each other (a user is the creator of a
        role it made in the app, and that role must go first), so what is
        left after one pass is tried again."""
        left = sorted(entries, key=lambda e: DELETE_ORDER.index(e["type"]))
        for _ in range(DELETE_PASSES):
            left = [entry for entry in left if not self.delete_entry(entry)]
            if not left:
                break
        return left

    def delete_entry(self, entry):
        if entry.get("id"):
            uids = [entry["id"]]
        else:
            uids = [role["id"] for role in self.api.roles_named(entry["name"])]
        errors = [error for error in (self.api.delete(entry["type"], uid) for uid in uids) if error]
        entry["error"] = errors[0] if errors else None
        return not errors

    def clear_leftovers(self):
        """Start of a run: remove whatever an earlier, killed run left."""
        left = self.delete_all(self.load())
        if left:
            raise ApiError(f"could not delete leftovers from an earlier run: {left}")
        self.api.request("DELETE", self.path)

    def clean_up(self):
        """End of a run: delete this run's objects, then the record."""
        left = self.delete_all(self.entries)
        if not left:
            self.api.request("DELETE", self.path)
        return left
