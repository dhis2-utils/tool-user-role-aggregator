# Design: role access checking

Date: 2026-08-19 · Status: approved, ready for implementation planning

## Problem

The app has three shortcomings that this design addresses.

1. **Write actions are shown to users who cannot use them.** The Create and Update pages render in full for any user who can open the app; the submit buttons are disabled and a warning is shown when the user lacks `F_USERROLE_PRIVATE_ADD` / `F_USERROLE_PUBLIC_ADD`. A read-only way to inspect role access is useful to those users, but the write forms are not.

2. **Checking one role in isolation gives wrong answers.** The Update page reports which roles a _single_ selected role can manage. A user's ability to administer other users comes from the union of all their roles' authorities (`User.canModifyUser` in DHIS2 core: hold `ALL`, or possess all of the target's authorities), so a user holding "Data entry clerk" + "M and E Officer" can manage roles that neither role covers alone. Today's answer therefore under-reports. It also over-reports in a different sense: a role carrying no user-administration authority (`F_USER_ADD`, `F_USER_ADD_WITHIN_MANAGED_GROUP`) cannot administer anyone, however many other authorities it holds, yet the page still lists roles it "can manage".

3. **There is no way to inspect a real user.** Administrators troubleshooting "why can't X manage Y" have to reconstruct the union of X's roles by hand.

## Rules (the domain model)

All of the following are pure functions over authority sets, in a new `src/domain/userRole.ts`. The rules and their tests move there from `src/types/userRole.ts` (which keeps the `UserRole` / `SystemAuthority` interfaces and the `AUTHORITY_ALL` constant, so the split is types vs rules); the five importing sites update accordingly. They are the correctness core of this change and carry the bulk of the tests.

| Function                              | Rule                                                                                                                                                                                                                   |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `aggregateAuthorities(roles)`         | Union of the roles' authorities. **The subject of every check is a set of authorities, never a single role.**                                                                                                          |
| `isUserAdminRole(role)`               | Role holds `F_USER_ADD`, `F_USER_ADD_WITHIN_MANAGED_GROUP`, or `ALL`. Drives the picker badge.                                                                                                                         |
| `canAdministerUsers(held)`            | Same test against an aggregated set. True when `held` has `ALL`, `F_USER_ADD`, or `F_USER_ADD_WITHIN_MANAGED_GROUP`. When false, the report states that the combination cannot administer users **and lists nothing**. |
| `canManageRole(held, role)`           | Existing rule, unchanged: `held ⊇ role.authorities`; a role containing `ALL` is manageable only by an `ALL` holder.                                                                                                    |
| `canGrantAuthority(held, id)`         | Existing rule, unchanged: `held` contains `id`, or `ALL`.                                                                                                                                                              |
| `missingAuthorities(held, role)`      | `role.authorities − held`, so a blocked role can be explained.                                                                                                                                                         |
| `manageabilityReport(held, allRoles)` | `{ canAdminister, limitedToManagedGroups, manageable: Role[], blocked: [{ role, missing }] }`.                                                                                                                         |

`ALL` short-circuits every rule, as it does in core.

**Managed groups are out of scope, and the report says so.** Core's `canManage(user)` is a user-group graph — true when one of the target's groups lists one of the subject's groups in its `managedByGroups` — entirely separate from authorities. When `held` contains `F_USER_ADD_WITHIN_MANAGED_GROUP` but neither `F_USER_ADD` nor `ALL` — so the capability exists but is confined to managed groups — `manageabilityReport` sets `limitedToManagedGroups` and the UI states that the verdict also depends on user-group management, which this tool does not evaluate. No user-group API calls are made.

## Navigation and gating

| Route         | Page                            | Visible when                                                                  |
| ------------- | ------------------------------- | ----------------------------------------------------------------------------- |
| `/`           | Check access — role combination | always                                                                        |
| `/check-user` | Check access — look up user     | current user holds `F_USER_VIEW` or `ALL`                                     |
| `/create`     | Create role                     | current user holds `F_USERROLE_PRIVATE_ADD` / `F_USERROLE_PUBLIC_ADD` / `ALL` |
| `/update`     | Update role                     | as `/create`                                                                  |

The landing page becomes the role-combination check, the only page guaranteed to be available. `/update` keeps its meaning; `/` changes from Create to Check, which the CHANGELOG notes (no redirect — the app is new as of 1.0).

The sidebar has two labelled groups, "Check access" and "Manage roles", and the second is **omitted entirely** (not disabled) when the user cannot write. Grouping needs only a plain `SidenavHeading`, not a collapsible parent.

Gating is enforced on the route as well as the nav: a `RequireAuthority` wrapper, parameterised with the accepted authorities (`[F_USERROLE_PRIVATE_ADD, F_USERROLE_PUBLIC_ADD]` for the write pages, `[F_USER_VIEW]` for the user lookup; `ALL` always passes), renders a NoticeBox naming the missing authority instead of the page, so a bookmarked `/create` degrades to an explanation rather than a form that cannot submit. This replaces `AddRolesWarning`, which exists to explain a disabled button that will no longer be rendered; that component and both of its usages are removed, along with the now-unused `canAddUserRoles` handling inside the two write pages.

## Check page

**Role-combination mode (`/`)** uses the existing `Transfer` widget with `renderOption` to draw each role name plus a small "user admin" tag; user-admin roles sort first. Selection is reflected in a query param (`/?roles=<id>,<id>`) so it can be deep-linked; ids that do not match a role visible to the current user are ignored rather than erroring.

**User-lookup mode (`/check-user`)** is a search field (debounced ~300 ms, minimum 2 characters) calling:

```
GET /api/users?query=<q>&fields=id,displayName,username,userRoles[id,displayName,authorities]&pageSize=10
```

One call returns the roles and their authorities, so there is no per-role fan-out. Results show display name and username; selecting a user renders their roles (same badges) followed by the report.

**Both modes render the same `ManageabilityReport` component**, which is presentational and single-column:

1. Summary — "2 roles → 57 authorities combined".
2. Capability verdict — either "can administer users", naming the authority that grants it, or "cannot administer users: none of these roles carries a user-administration authority", in which case no lists follow. Plus the managed-group caveat when applicable.
3. When capable — **Can manage (k)** as a role list, and **Cannot manage (j)** where each row names the role and the authorities it lacks, resolved to display names via `useSystemAuthorities`. Long lists collapse to a count with an expand toggle (blocked-by-Superuser is ~150 authorities).

**Data:** `useUserRoles` and `useSystemAuthorities` are reused unchanged (both `staleTime: Infinity`, so switching modes is free). One new `useUserSearch(query)`, keyed on the query, `enabled` only past the minimum length, with `keepPreviousData` to avoid flicker while typing.

## Write pages

**Create** keeps its shape — name, roles to manage, additional authorities, submit — and keeps the existing filtering of both pickers to what the signed-in user holds. It loses `canAddUserRoles` and `AddRolesWarning`. It gains one warning: if the selected authorities contain no user-administration authority, say so before submit ("this role will not be able to administer any users; add Add/Update User"), since building an admin role is the page's purpose and the defaults can be deselected.

**Update** becomes purely a write flow: target role → source roles → submit, with the existing subset filtering. Its manageability list moves to the Check page, and a "check what this role can manage →" link deep-links to `/?roles=<id>`.

## Testing

Unit tests (jest, alongside the code) carry the weight, since the rules are what is currently wrong: `aggregateAuthorities`, `isUserAdminRole`, `canAdministerUsers` including the managed-group-only case setting `limitedToManagedGroups`, `missingAuthorities`, and `manageabilityReport`. One test asserts the bug being fixed directly: roles A ∪ B manage a role that neither A nor B manages alone. The existing 8 tests for `canManageRole` / `canGrantAuthority` stay.

End-to-end (`tests/e2e/`) additions, with expectations computed from the API as the existing suites do: nav gating (write items absent for a user without `F_USERROLE_*_ADD`; `/create` renders the notice), role-combination verdicts, the no-user-admin-authority case showing no lists, and a user lookup against a seeded demo user.

## Non-goals

No user-group graph modelling. No enumerating which _users_ a subject can manage. No reverse lookup ("who can manage this role"). No user editing. No export.

## Implementation order

Each step leaves the app working, so the plan can stage them:

1. Domain module + unit tests (no UI change; existing pages keep working through the moved functions).
2. Routing, sidebar groups and `RequireAuthority` — write pages hidden/guarded, `AddRolesWarning` removed.
3. `ManageabilityReport` + role-combination mode at `/`, including the `?roles=` param.
4. User-lookup mode at `/check-user` with `useUserSearch`.
5. Write-page trims: Update loses its analysis and gains the Check link; Create gains the no-user-admin-authority warning.
6. i18n extraction, MANUAL/CHANGELOG updates, e2e additions.

## Risks

The Check page can get dense — a picker plus three stacked result blocks. Mitigation is keeping `ManageabilityReport` presentational and single-column; it is the first thing built, so the layout is visible early.
