# Cross-version test results: role access checking

Tested: 2026-08-19 · App under test: production bundle `tool-user-role-aggregator-1.0.0.zip` installed via `POST /api/apps` · Suites: `tests/e2e/suite.py`, `tests/e2e/nonsuperuser_test.py`, `tests/e2e/extra_tests.py`

Every version from the declared minimum (2.40) to the current release (2.43), across two different demo databases, so the app is exercised against two unrelated metadata shapes rather than one. Each instance was provisioned from a broker seed, tested, and deleted; instances were run one at a time.

## Results

| DHIS2    | Seed             | `suite.py`                  | `nonsuperuser_test.py` | `extra_tests.py`                           |
| -------- | ---------------- | --------------------------- | ---------------------- | ------------------------------------------ |
| 2.40.12  | Sierra Leone v40 | 23/23                       | 23/23                  | pass — global-shell sync SKIP (2.42+ only) |
| 2.41.9.1 | Laos v41         | 23/23 (escaping check SKIP) | 23/23                  | pass — global-shell sync SKIP (2.42+ only) |
| 2.42.5.2 | Sierra Leone v42 | 23/23                       | 23/23                  | 7/7 incl. global-shell URL sync            |
| 2.43.1   | Laos v43         | 23/23                       | 23/23                  | 7/7 incl. global-shell URL sync            |

**0 FAIL on every version.** No version-specific behaviour differences were found in the app itself.

## What the suites covered

- **Both write flows**, API-verified: create a role aggregating another role's authorities, then extend an existing role, with the merged authorities and preserved owner fields checked over the API.
- **The new Check pages**: a role combination's can-manage / cannot-manage verdict compared against an expectation computed independently from the API; the "this combination cannot administer users" case, exercised with a role discovered to hold no user-administration authority; and the user lookup, including an assertion that no loader renders before typing.
- **Gating**: a user holding the app authority but no role-management authority sees no Create/Update nav and gets the guard notice at `#/create`; a user without the app authority cannot load the app at all.
- **Cache invalidation**: after an update, the Check page reflects the new authorities without a page reload.
- **The i18n escaping regression net**: the created role's persisted `description` must contain no HTML entity and must contain the source role's display name verbatim.

## Version-specific notes

- **Global shell** exists only on 2.42+, so the URL-sync test records SKIP on 2.40 and 2.41 rather than failing. On 2.42 and 2.43 it confirms the app is wrapped in the shell iframe and the browser URL tracks in-app navigation.
- **`GET /api/authorities` returns 500 on a freshly booted 2.41.x** until the legacy web layer is initialised (`Struts Dispatcher.getInstance() is null`). Every instance was warmed with one request to a legacy page before testing; without that, the app's authority picker would show its error notice.
- **Escaping check on Laos**: no Laos role name contains a character that i18next would escape, so `suite.py` records that step as SKIP rather than passing vacuously. On the Sierra Leone seeds it runs for real against "MNCH / PNC (Adult Woman) program".

## Seed portability

The first Laos run failed on three hard-coded Sierra Leone role names (`Data entry clerk`, `M and E Officer`, `User manager`). The suites now discover the roles they need by property — smallest non-empty authority set, a role carrying a user-administration authority, a role with neither app access nor `ALL` — so they run unchanged on any seed. That fix is what makes the two Laos rows above meaningful.

## Instances

All created via the d2 broker, one at a time, and **all deleted after testing**: `agent-xver-240b` (2.40), `agent-xver-241` (2.41), `agent-xver-242` (2.42), `agent-xver-243` (2.43).
