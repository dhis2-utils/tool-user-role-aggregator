> [!WARNING]
> The suite creates and deletes users, user roles and organisation units, and installs and uninstalls the app. Run it only against a throwaway DHIS2 instance that you can reset or recreate. Never run it against a production, shared or play server.

# End-to-end tests

The suite installs the built bundle, drives the app in Chromium, and checks every change through the Web API. It follows the `e2e/run.sh` contract (version 1) in [TESTING.md](https://github.com/dhis2-utils/reference-tool-conventions/blob/main/TESTING.md) in reference-tool-conventions.

## Get a throwaway instance

[DHIS2 in Docker](https://developers.dhis2.org/docs/tutorials/dhis2-docker/) describes how to start a local instance. The suite seeds everything it needs, so an empty database works as well as a demo database.

## Run it

Install Python 3, Playwright for Python and Chromium:

```bash
pip install -r e2e/requirements.txt
python3 -m playwright install chromium
```

Build the bundle, then run the suite:

```bash
pnpm run build
mkdir -p /tmp/e2e-out
DHIS2_URL=http://localhost:8080 DHIS2_USER=admin DHIS2_PASS=district \
LABEL=2.42 RESULTS_DIR=/tmp/e2e-out APP_ZIP=$(ls "$PWD"/build/bundle/*.zip) \
  e2e/run.sh
```

| Variable                   | Required | Meaning                                                       |
| -------------------------- | -------- | ------------------------------------------------------------- |
| `DHIS2_URL`                | yes      | Instance base URL, no trailing slash                          |
| `DHIS2_USER`, `DHIS2_PASS` | yes      | A user with the `ALL` authority                               |
| `APP_ZIP`                  | yes      | Absolute path of the bundle to test                           |
| `RESULTS_DIR`              | yes      | Existing directory for `results.json` and screenshots         |
| `LABEL`                    | no       | Label for output and screenshots; default: the server version |
| `APP_KEY`                  | no       | Default: the key the server reports for the installed app     |

The exit code is `0` when every test passed, `1` when a test failed, and `2` when the suite could not run. `results.json` lists each test by a stable `id`.

## What it tests

The suite seeds five roles and three users, with names that start with `E2E tool-user-role-aggregator` and a run id. It then runs five scenarios, each in its own browser session:

- **superuser**: the create page lists the seeded roles and preselects the user-management authorities; an empty name is rejected; a created role holds exactly the authorities of the chosen roles plus the defaults; its description keeps special characters unescaped; the update page offers only user admin roles, and adding a role's authorities there merges them without losing anything; the role combination check lists what the role can manage, before and after the update, without a reload; the user lookup report for a seeded user matches the API.
- **url-sync**: on 2.42 and later, the global shell's address follows navigation in the app. Skipped on 2.41 and earlier.
- **manager**, a user who may manage roles but is not a superuser: the create page offers exactly the roles that the user may grant; the user can create a role; the role combination check matches the API, with and without user administration; and when a chosen role gains an authority that the user does not hold before they submit, the app refuses to create the role.
- **readonly**, a user who can open the app but not manage roles: the create and update pages are absent from the sidebar, and opening `#/create` directly shows the authority guard.
- **noaccess**, a user without the app's authority: the app does not render.

Every scenario also fails on a page error, or on an HTTP error from the Web API that the app did not expect.

## Cleanup

Before it creates anything, the suite writes the object to a record in the dataStore at `e2e-state/tool-user-role-aggregator`. At the end it deletes what the record lists, deletes the record, and uninstalls the app. A run that was killed leaves the record behind, and the next run deletes the leftovers first.

On a freshly started 2.41 instance, `/api/authorities` returns an error until the legacy login page has been served once. The suite requests that page before it starts.
