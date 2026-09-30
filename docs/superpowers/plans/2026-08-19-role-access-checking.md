# Role Access Checking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the app into three sections — a read-only "Check access" area that evaluates a _combination_ of roles or a real user, plus Create and Update pages that are hidden unless the signed-in user may manage user roles.

**Architecture:** All authority rules move into a pure module (`src/domain/userRole.ts`) that knows nothing about React or DHIS2, so the two Check modes and the write-page gating share one implementation and the rules are unit-testable. A single presentational `ManageabilityReport` component renders the verdict for both modes. Route-level guards replace the current disabled-button-plus-warning pattern.

**Tech Stack:** DHIS2 App Platform (`@dhis2/cli-app-scripts` 12.10.3), React 18, TypeScript, `@dhis2/ui` 10.11, `@dhis2/app-runtime` 3.15, TanStack Query v4, react-router-dom 7.18 (hash router), jest via `d2-app-scripts test`, Playwright for e2e.

**Spec:** `docs/superpowers/specs/2026-08-19-role-access-checking-design.md`

## Global Constraints

- **DHIS2 2.40+** — `d2.config.js` declares `minDHIS2Version: '2.40'`. Every endpoint used here (`/api/me`, `/api/userRoles`, `/api/authorities`, `/api/users?query=`) exists on 2.40.
- **Version stays `1.0.0`** — this ships as part of 1.0.0; do not bump `package.json`.
- **No new dependencies.** React Testing Library is not available and must not be added: pure logic is tested with jest, component behaviour with the Playwright suites in `tests/e2e/`.
- **`ALL` short-circuits every rule** — a holder of `ALL` implicitly holds every authority.
- **Every user-facing string goes through `i18n.t()`.** A string containing a colon needs `{ nsSeparator: '###' }` as the second argument, or the i18next scanner drops it from extraction.
- **Preserve the existing picker restrictions**: the Create page's authority picker lists only authorities the signed-in user holds (`canGrantAuthority`), and the Update page's source-role picker only roles whose authorities the user holds (`canManageRole`). No task may widen these.
- **Managed groups are out of scope.** The report flags `limitedToManagedGroups` and the UI states the limitation; no user-group API calls.
- **Commands:** `pnpm test` (all), `pnpm test -- <path>` (one file), `pnpm run lint` (eslint + prettier check), `pnpm run format` (prettier write), `pnpm exec tsc --noEmit`.
- **Sandbox caveat:** if `pnpm test` fails with `Cannot find module '@babel/plugin-transform-private-methods'`, the `node_modules` tree came from the host's pnpm store and cannot resolve. Run the suite from a clean copy instead: `git archive HEAD | tar -x -C <tmpdir> && cd <tmpdir> && pnpm install --frozen-lockfile && pnpm test`. Do not reinstall in place.

---

## File Structure

**Created**

| File                                            | Responsibility                                                      |
| ----------------------------------------------- | ------------------------------------------------------------------- |
| `src/domain/userRole.ts`                        | All authority rules as pure functions. No React, no DHIS2 imports.  |
| `src/domain/userRole.test.ts`                   | Unit tests for every rule (moved from `src/types/`, then extended). |
| `src/components/RequireAuthority.tsx`           | Route guard: renders children or a "missing authority" notice.      |
| `src/components/ManageabilityReport.tsx`        | Presentational verdict for both Check modes.                        |
| `src/components/ManageabilityReport.module.css` | Styles for the report.                                              |
| `src/pages/CheckRolesPage.tsx`                  | Check mode A: pick a role combination.                              |
| `src/pages/CheckRolesPage.module.css`           | Styles.                                                             |
| `src/pages/CheckUserPage.tsx`                   | Check mode B: search a user.                                        |
| `src/pages/CheckUserPage.module.css`            | Styles.                                                             |
| `src/hooks/useUserSearch.ts`                    | Debounced user search query.                                        |
| `src/hooks/useDebouncedValue.ts`                | 300 ms debounce helper.                                             |

**Modified**

| File                                                   | Change                                                                   |
| ------------------------------------------------------ | ------------------------------------------------------------------------ |
| `src/types/userRole.ts`                                | Keeps `UserRole`, `SystemAuthority`, `AUTHORITY_ALL`; rules removed.     |
| `src/hooks/useCurrentUserAuthorities.ts`               | Adds `canViewUsers`; keeps `canAddUserRoles`, `isSuperuser`.             |
| `src/App.tsx`                                          | New routes, guards.                                                      |
| `src/components/sidebar/Sidebar.tsx`                   | Two labelled groups, conditional rendering.                              |
| `src/components/sidebar/sidenav/Sidenav.tsx`           | Adds `SidenavHeading`.                                                   |
| `src/components/sidebar/sidenav/Sidenav.module.css`    | Heading style.                                                           |
| `src/components/sidebar/sidenav/index.ts`              | Exports `SidenavHeading`.                                                |
| `src/pages/CreateRolePage.tsx`                         | Drops `AddRolesWarning` / `canAddUserRoles`; adds no-user-admin warning. |
| `src/pages/UpdateRolePage.tsx`                         | Drops the managed-roles list; adds Check link.                           |
| `i18n/en.pot`, `CHANGELOG.md`, `docs/MANUAL.md`        | Strings and docs.                                                        |
| `tests/e2e/suite.py`, `tests/e2e/nonsuperuser_test.py` | New coverage.                                                            |

**Deleted:** `src/components/AddRolesWarning.tsx`, `src/components/AddRolesWarning.module.css`.

---

### Task 1: Domain module — move the rules, add aggregation and reporting

**Files:**

- Create: `src/domain/userRole.ts`, `src/domain/userRole.test.ts`
- Modify: `src/types/userRole.ts`, `src/hooks/useCurrentUserAuthorities.ts`, `src/pages/CreateRolePage.tsx` (import only), `src/pages/UpdateRolePage.tsx` (import only)
- Delete: `src/types/userRole.test.ts` (moves to `src/domain/`)

**Interfaces:**

- Consumes: nothing.
- Produces: `aggregateAuthorities(roles: UserRole[]): Set<string>`; `canManageRole(held: ReadonlySet<string>, role: UserRole): boolean`; `canGrantAuthority(held: ReadonlySet<string>, authorityId: string): boolean`; `canAdministerUsers(held: ReadonlySet<string>): boolean`; `isUserAdminRole(role: UserRole): boolean`; `missingAuthorities(held: ReadonlySet<string>, role: UserRole): string[]`; `manageabilityReport(held: ReadonlySet<string>, allRoles: UserRole[]): ManageabilityReport` where `ManageabilityReport = { canAdminister: boolean; limitedToManagedGroups: boolean; manageable: UserRole[]; blocked: Array<{ role: UserRole; missing: string[] }> }`; constants `AUTHORITY_USER_ADD`, `AUTHORITY_USER_ADD_IN_GROUP`, `AUTHORITY_USER_VIEW`, `USERROLE_ADD_AUTHORITIES`. `src/types/userRole.ts` still exports `UserRole`, `SystemAuthority`, `AUTHORITY_ALL`.

- [ ] **Step 1: Move the existing rules and tests, leaving types behind**

`git mv src/types/userRole.test.ts src/domain/userRole.test.ts` (create the directory first). Then `src/types/userRole.ts` becomes exactly:

```ts
export interface UserRole {
    id: string
    displayName: string
    authorities?: string[]
}

export interface SystemAuthority {
    id: string
    name: string
}

/** The special authority that grants superuser access to everything */
export const AUTHORITY_ALL = 'ALL'
```

Create `src/domain/userRole.ts` with the two rules moved verbatim from the old file, unchanged in behaviour:

```ts
import { AUTHORITY_ALL, UserRole } from '@/types/userRole'

/** Lets a user administer any user. */
export const AUTHORITY_USER_ADD = 'F_USER_ADD'
/** Lets a user administer only users in user groups they manage. */
export const AUTHORITY_USER_ADD_IN_GROUP = 'F_USER_ADD_WITHIN_MANAGED_GROUP'
/** Required to list and read users. */
export const AUTHORITY_USER_VIEW = 'F_USER_VIEW'
/** Either of these lets a user create or change user roles. */
export const USERROLE_ADD_AUTHORITIES = [
    'F_USERROLE_PRIVATE_ADD',
    'F_USERROLE_PUBLIC_ADD',
]

/**
 * A role is manageable by someone holding `heldAuthorities` when every
 * authority of the role is included in the held set (the DHIS2 user
 * management rule: you may only manage users with equal or fewer
 * privileges than yourself).
 */
export const canManageRole = (
    heldAuthorities: ReadonlySet<string>,
    role: UserRole
): boolean => {
    if (heldAuthorities.has(AUTHORITY_ALL)) {
        return true
    }
    const roleAuthorities = role.authorities ?? []
    if (roleAuthorities.includes(AUTHORITY_ALL)) {
        return false
    }
    return roleAuthorities.every((authority) => heldAuthorities.has(authority))
}

/**
 * Whether a user holding `heldAuthorities` may grant `authorityId` — a
 * superuser (holder of `ALL`) implicitly holds every authority. Used to
 * limit the authority picker to the current user's own authorities.
 */
export const canGrantAuthority = (
    heldAuthorities: ReadonlySet<string>,
    authorityId: string
): boolean =>
    heldAuthorities.has(AUTHORITY_ALL) || heldAuthorities.has(authorityId)
```

Update the four importing files to `from '@/domain/userRole'` for the rules, keeping `@/types/userRole` for `UserRole` / `SystemAuthority` / `AUTHORITY_ALL`. In `src/domain/userRole.test.ts`, change the import to:

```ts
import { AUTHORITY_ALL } from '@/types/userRole'
import { canGrantAuthority, canManageRole } from './userRole'
import type { UserRole } from '@/types/userRole'
```

- [ ] **Step 2: Run the moved tests and the typechecker**

Run: `pnpm test -- src/domain/userRole.test.ts` and `pnpm exec tsc --noEmit`
Expected: 8 tests PASS, tsc clean. This step only proves the move was behaviour-neutral.

- [ ] **Step 3: Commit the move**

```bash
git add -A src/domain src/types src/hooks src/pages
git commit -m "refactor: split user-role rules out of the types module"
```

- [ ] **Step 4: Write the failing tests for the new rules**

Append to `src/domain/userRole.test.ts`:

```ts
describe('aggregateAuthorities', () => {
    it('unions the authorities of several roles and de-duplicates', () => {
        const result = aggregateAuthorities([
            role(['F_A', 'F_B']),
            role(['F_B', 'F_C']),
        ])
        expect([...result].sort()).toEqual(['F_A', 'F_B', 'F_C'])
    })

    it('ignores roles without authorities', () => {
        expect(aggregateAuthorities([role(undefined), role([])]).size).toBe(0)
    })
})

describe('canAdministerUsers', () => {
    it('is true for ALL, F_USER_ADD, or the managed-group variant', () => {
        expect(canAdministerUsers(new Set([AUTHORITY_ALL]))).toBe(true)
        expect(canAdministerUsers(new Set(['F_USER_ADD']))).toBe(true)
        expect(
            canAdministerUsers(new Set(['F_USER_ADD_WITHIN_MANAGED_GROUP']))
        ).toBe(true)
    })

    it('is false without any user-administration authority', () => {
        expect(canAdministerUsers(new Set(['F_USER_VIEW', 'F_A']))).toBe(false)
        expect(canAdministerUsers(new Set<string>())).toBe(false)
    })
})

describe('isUserAdminRole', () => {
    it('detects roles that confer user administration', () => {
        expect(isUserAdminRole(role(['F_USER_ADD']))).toBe(true)
        expect(isUserAdminRole(role([AUTHORITY_ALL]))).toBe(true)
        expect(isUserAdminRole(role(['F_USER_VIEW']))).toBe(false)
        expect(isUserAdminRole(role(undefined))).toBe(false)
    })
})

describe('missingAuthorities', () => {
    it('returns the role authorities the holder lacks, sorted', () => {
        const held = new Set(['F_B'])
        expect(missingAuthorities(held, role(['F_C', 'F_A', 'F_B']))).toEqual([
            'F_A',
            'F_C',
        ])
    })

    it('returns nothing for a superuser', () => {
        expect(
            missingAuthorities(new Set([AUTHORITY_ALL]), role(['F_A']))
        ).toEqual([])
    })

    it('reports ALL as missing for a non-superuser', () => {
        expect(
            missingAuthorities(new Set(['F_A']), role([AUTHORITY_ALL]))
        ).toEqual([AUTHORITY_ALL])
    })
})

describe('manageabilityReport', () => {
    const named = (id: string, authorities?: string[]): UserRole => ({
        id,
        displayName: id,
        authorities,
    })

    it('reports nothing manageable when the set cannot administer users', () => {
        const report = manageabilityReport(new Set(['F_A', 'F_B']), [
            named('target', ['F_A']),
        ])
        expect(report.canAdminister).toBe(false)
        expect(report.manageable).toEqual([])
        expect(report.blocked).toEqual([])
    })

    it('combines the authorities of several roles — the union manages what neither role alone can', () => {
        const adminRole = named('admin', ['F_USER_ADD', 'F_A'])
        const extraRole = named('extra', ['F_B'])
        const target = named('target', ['F_A', 'F_B'])

        const fromAdminOnly = manageabilityReport(
            aggregateAuthorities([adminRole]),
            [target]
        )
        expect(fromAdminOnly.manageable).toEqual([])

        const fromBoth = manageabilityReport(
            aggregateAuthorities([adminRole, extraRole]),
            [target]
        )
        expect(fromBoth.manageable).toEqual([target])
    })

    it('explains each blocked role with the authorities it is missing', () => {
        const report = manageabilityReport(new Set(['F_USER_ADD']), [
            named('blocked', ['F_X', 'F_Y']),
        ])
        expect(report.manageable).toEqual([])
        expect(report.blocked).toEqual([
            { role: named('blocked', ['F_X', 'F_Y']), missing: ['F_X', 'F_Y'] },
        ])
    })

    it('flags a set limited to managed groups', () => {
        const limited = manageabilityReport(
            new Set(['F_USER_ADD_WITHIN_MANAGED_GROUP']),
            []
        )
        expect(limited.canAdminister).toBe(true)
        expect(limited.limitedToManagedGroups).toBe(true)

        const unlimited = manageabilityReport(
            new Set(['F_USER_ADD', 'F_USER_ADD_WITHIN_MANAGED_GROUP']),
            []
        )
        expect(unlimited.limitedToManagedGroups).toBe(false)
    })

    it('lets a superuser manage every role, including superuser roles', () => {
        const report = manageabilityReport(new Set([AUTHORITY_ALL]), [
            named('super', [AUTHORITY_ALL]),
            named('plain', ['F_A']),
        ])
        expect(report.blocked).toEqual([])
        expect(report.manageable).toHaveLength(2)
        expect(report.limitedToManagedGroups).toBe(false)
    })
})
```

Extend the import at the top of the test file to include the new names:

```ts
import {
    aggregateAuthorities,
    canAdministerUsers,
    canGrantAuthority,
    canManageRole,
    isUserAdminRole,
    manageabilityReport,
    missingAuthorities,
} from './userRole'
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `pnpm test -- src/domain/userRole.test.ts`
Expected: FAIL — `aggregateAuthorities is not a function` (and the same for the other new names).

- [ ] **Step 6: Implement the new rules**

Append to `src/domain/userRole.ts`:

```ts
/** Union of the authorities of every given role. */
export const aggregateAuthorities = (roles: UserRole[]): Set<string> =>
    new Set(roles.flatMap((role) => role.authorities ?? []))

/**
 * Whether the holder can administer users at all. Without one of these
 * authorities, "which roles can this set manage" has no meaning: the holder
 * cannot administer anybody, however many other authorities they have.
 */
export const canAdministerUsers = (
    heldAuthorities: ReadonlySet<string>
): boolean =>
    heldAuthorities.has(AUTHORITY_ALL) ||
    heldAuthorities.has(AUTHORITY_USER_ADD) ||
    heldAuthorities.has(AUTHORITY_USER_ADD_IN_GROUP)

/** Whether a single role confers user administration. Drives the picker badge. */
export const isUserAdminRole = (role: UserRole): boolean =>
    canAdministerUsers(new Set(role.authorities ?? []))

/** The role's authorities the holder lacks, sorted for stable display. */
export const missingAuthorities = (
    heldAuthorities: ReadonlySet<string>,
    role: UserRole
): string[] => {
    if (heldAuthorities.has(AUTHORITY_ALL)) {
        return []
    }
    return (role.authorities ?? [])
        .filter((authority) => !heldAuthorities.has(authority))
        .sort()
}

export interface BlockedRole {
    role: UserRole
    missing: string[]
}

export interface ManageabilityReport {
    /** False when the set holds no user-administration authority. */
    canAdminister: boolean
    /** True when administration is confined to managed user groups. */
    limitedToManagedGroups: boolean
    manageable: UserRole[]
    blocked: BlockedRole[]
}

/**
 * Which of `allRoles` a holder of `heldAuthorities` may manage. When the
 * holder cannot administer users at all, both lists are empty — listing
 * roles would imply an ability that does not exist.
 */
export const manageabilityReport = (
    heldAuthorities: ReadonlySet<string>,
    allRoles: UserRole[]
): ManageabilityReport => {
    const canAdminister = canAdministerUsers(heldAuthorities)
    const limitedToManagedGroups =
        heldAuthorities.has(AUTHORITY_USER_ADD_IN_GROUP) &&
        !heldAuthorities.has(AUTHORITY_USER_ADD) &&
        !heldAuthorities.has(AUTHORITY_ALL)

    if (!canAdminister) {
        return {
            canAdminister,
            limitedToManagedGroups,
            manageable: [],
            blocked: [],
        }
    }

    const manageable: UserRole[] = []
    const blocked: BlockedRole[] = []
    for (const role of allRoles) {
        if (canManageRole(heldAuthorities, role)) {
            manageable.push(role)
        } else {
            blocked.push({
                role,
                missing: missingAuthorities(heldAuthorities, role),
            })
        }
    }
    return { canAdminister, limitedToManagedGroups, manageable, blocked }
}
```

Note for the implementer: roles in the subject's own selection are _not_ excluded from `manageable`. Holding a role does let you manage users who have that role, so including it is correct.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pnpm test -- src/domain/userRole.test.ts` then `pnpm run lint && pnpm exec tsc --noEmit`
Expected: all tests PASS (8 existing + 13 new), lint and tsc clean.

- [ ] **Step 8: Commit**

```bash
git add src/domain
git commit -m "feat: aggregate role authorities and report manageability"
```

---

### Task 2: Route guard, sidebar groups and routes

**Files:**

- Create: `src/components/RequireAuthority.tsx`
- Modify: `src/hooks/useCurrentUserAuthorities.ts`, `src/App.tsx`, `src/components/sidebar/Sidebar.tsx`, `src/components/sidebar/sidenav/Sidenav.tsx`, `src/components/sidebar/sidenav/Sidenav.module.css`, `src/components/sidebar/sidenav/index.ts`
- Delete: `src/components/AddRolesWarning.tsx`, `src/components/AddRolesWarning.module.css`

**Interfaces:**

- Consumes: `USERROLE_ADD_AUTHORITIES`, `AUTHORITY_USER_VIEW` from `@/domain/userRole` (Task 1).
- Produces: `<RequireAuthority anyOf={string[]}>{children}</RequireAuthority>`; `useCurrentUserAuthorities()` additionally returns `canViewUsers: boolean`; `<SidenavHeading>` from `@/components/sidebar/sidenav`. Placeholder pages `CheckRolesPage` and `CheckUserPage` are created in Tasks 4 and 5 — this task wires routes to them, so create both files as one-line stubs here and fill them in later:

```tsx
// src/pages/CheckRolesPage.tsx — stub, completed in Task 4
import React from 'react'
export const CheckRolesPage = () => <div />
```

```tsx
// src/pages/CheckUserPage.tsx — stub, completed in Task 5
import React from 'react'
export const CheckUserPage = () => <div />
```

- [ ] **Step 1: Add `canViewUsers` to the authorities hook**

In `src/hooks/useCurrentUserAuthorities.ts`, replace the derived-flags block and imports so it reads:

```ts
import { useMemo } from 'react'
import {
    AUTHORITY_USER_VIEW,
    USERROLE_ADD_AUTHORITIES,
} from '@/domain/userRole'
import { AUTHORITY_ALL } from '@/types/userRole'
import { useApiDataQuery } from '@/utils/useApiDataQuery'
```

and, after `const authorities = useMemo(...)`:

```ts
const isSuperuser = authorities.has(AUTHORITY_ALL)
const canAddUserRoles =
    isSuperuser ||
    USERROLE_ADD_AUTHORITIES.some((authority) => authorities.has(authority))
const canViewUsers = isSuperuser || authorities.has(AUTHORITY_USER_VIEW)

return {
    authorities,
    isSuperuser,
    canAddUserRoles,
    canViewUsers,
    isLoading,
    error,
}
```

- [ ] **Step 2: Create the route guard**

`src/components/RequireAuthority.tsx`:

```tsx
import i18n from '@dhis2/d2-i18n'
import { CircularLoader, NoticeBox } from '@dhis2/ui'
import React from 'react'
import { useCurrentUserAuthorities } from '@/hooks/useCurrentUserAuthorities'
import { AUTHORITY_ALL } from '@/types/userRole'

interface RequireAuthorityProps {
    /** The page renders when the user holds any of these, or ALL. */
    anyOf: string[]
    children: React.ReactNode
}

/**
 * Renders its children only for users holding one of `anyOf`. Pages behind
 * this guard need no permission checks of their own.
 */
export const RequireAuthority = ({
    anyOf,
    children,
}: RequireAuthorityProps) => {
    const { authorities, isLoading, error } = useCurrentUserAuthorities()

    if (isLoading) {
        return <CircularLoader />
    }
    if (error) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error.message}
            </NoticeBox>
        )
    }

    const allowed =
        authorities.has(AUTHORITY_ALL) ||
        anyOf.some((authority) => authorities.has(authority))

    if (!allowed) {
        return (
            <NoticeBox warning title={i18n.t('Missing permissions')}>
                {i18n.t(
                    'This page needs one of these authorities: {{authorities}}',
                    { authorities: anyOf.join(', '), nsSeparator: '###' }
                )}
            </NoticeBox>
        )
    }

    return <>{children}</>
}
```

- [ ] **Step 3: Add the sidenav heading**

Append to `src/components/sidebar/sidenav/Sidenav.tsx`:

```tsx
export const SidenavHeading = ({ children }: PropsWithChildren) => (
    <li className={styles.sidenavHeading}>{children}</li>
)
```

Export it from `src/components/sidebar/sidenav/index.ts`:

```ts
export { Sidenav, SidenavHeading, SidenavItems, SidenavLink } from './Sidenav'
```

Append to `src/components/sidebar/sidenav/Sidenav.module.css`:

```css
.sidenavHeading {
    padding: var(--spacers-dp16) 8px 4px 12px;
    color: var(--colors-grey500);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
```

- [ ] **Step 4: Rewrite the sidebar contents**

In `src/components/sidebar/Sidebar.tsx`, import the hook and heading, then replace the `<SidenavItems>` block:

```tsx
import { useCurrentUserAuthorities } from '@/hooks/useCurrentUserAuthorities'
import { Sidenav, SidenavHeading, SidenavItems, SidenavLink } from './sidenav'
```

```tsx
const { canAddUserRoles, canViewUsers } = useCurrentUserAuthorities()
```

```tsx
<SidenavItems>
    <SidenavHeading>{i18n.t('Check access')}</SidenavHeading>
    <SidebarNavLink to="/" label={i18n.t('Role combination')} end />
    {canViewUsers && (
        <SidebarNavLink to="/check-user" label={i18n.t('Look up user')} />
    )}
    {canAddUserRoles && (
        <>
            <SidenavHeading>{i18n.t('Manage roles')}</SidenavHeading>
            <SidebarNavLink to="/create" label={i18n.t('Create new role')} />
            <SidebarNavLink
                to="/update"
                label={i18n.t('Update existing role')}
            />
        </>
    )}
</SidenavItems>
```

- [ ] **Step 5: Wire the routes**

In `src/App.tsx`, add imports and replace the innermost `children` array:

```tsx
import { RequireAuthority } from '@/components/RequireAuthority'
import {
    AUTHORITY_USER_VIEW,
    USERROLE_ADD_AUTHORITIES,
} from '@/domain/userRole'
import { CheckRolesPage } from '@/pages/CheckRolesPage'
import { CheckUserPage } from '@/pages/CheckUserPage'
```

```tsx
                        children: [
                            { path: '/', element: <CheckRolesPage /> },
                            {
                                path: '/check-user',
                                element: (
                                    <RequireAuthority
                                        anyOf={[AUTHORITY_USER_VIEW]}
                                    >
                                        <CheckUserPage />
                                    </RequireAuthority>
                                ),
                            },
                            {
                                path: '/create',
                                element: (
                                    <RequireAuthority
                                        anyOf={USERROLE_ADD_AUTHORITIES}
                                    >
                                        <CreateRolePage />
                                    </RequireAuthority>
                                ),
                            },
                            {
                                path: '/update',
                                element: (
                                    <RequireAuthority
                                        anyOf={USERROLE_ADD_AUTHORITIES}
                                    >
                                        <UpdateRolePage />
                                    </RequireAuthority>
                                ),
                            },
                        ],
```

- [ ] **Step 6: Remove the obsolete warning component**

```bash
git rm src/components/AddRolesWarning.tsx src/components/AddRolesWarning.module.css
```

In both `src/pages/CreateRolePage.tsx` and `src/pages/UpdateRolePage.tsx`, delete the `AddRolesWarning` import and its `<AddRolesWarning canAddUserRoles={canAddUserRoles} />` usage. Leave the rest of those pages alone for now — Task 6 finishes them. `tsc` will flag `canAddUserRoles` as unused in Update; delete it from that destructuring now, and leave Create's usage (its button still references it until Task 6).

- [ ] **Step 7: Verify build and manual check**

Run: `pnpm run lint && pnpm exec tsc --noEmit && pnpm test`
Expected: clean, 21 tests pass.

Then start the dev server against a test instance and confirm by hand: as a superuser both sidebar groups appear; as a user without `F_USERROLE_*_ADD` the "Manage roles" group is absent and `#/create` shows the missing-permissions notice instead of a form.

```bash
pnpm start --proxy http://dhis2-<instance>:8080
```

- [ ] **Step 8: Commit**

```bash
git add -A src
git commit -m "feat: gate the write pages behind a route guard and group the sidebar"
```

---

### Task 3: The ManageabilityReport component

**Files:**

- Create: `src/components/ManageabilityReport.tsx`, `src/components/ManageabilityReport.module.css`

**Interfaces:**

- Consumes: `manageabilityReport`, `AUTHORITY_USER_ADD`, `AUTHORITY_USER_ADD_IN_GROUP` from `@/domain/userRole`; `SystemAuthority`, `UserRole`, `AUTHORITY_ALL` from `@/types/userRole`.
- Produces: `<ManageabilityReport authorities={ReadonlySet<string>} roleCount={number} allRoles={UserRole[]} systemAuthorities={SystemAuthority[]} />`. Used by Tasks 4 and 5.

- [ ] **Step 1: Write the component**

`src/components/ManageabilityReport.tsx`:

```tsx
import i18n from '@dhis2/d2-i18n'
import { Button, NoticeBox, Tag } from '@dhis2/ui'
import React, { useMemo, useState } from 'react'
import styles from './ManageabilityReport.module.css'
import {
    AUTHORITY_USER_ADD,
    AUTHORITY_USER_ADD_IN_GROUP,
    manageabilityReport,
} from '@/domain/userRole'
import { AUTHORITY_ALL, SystemAuthority, UserRole } from '@/types/userRole'

const MISSING_PREVIEW_COUNT = 5

interface ManageabilityReportProps {
    /** The subject's combined authorities. */
    authorities: ReadonlySet<string>
    /** How many roles the authorities were aggregated from. */
    roleCount: number
    allRoles: UserRole[]
    systemAuthorities: SystemAuthority[]
}

const MissingAuthorities = ({
    missing,
    nameOf,
}: {
    missing: string[]
    nameOf: (id: string) => string
}) => {
    const [expanded, setExpanded] = useState(false)
    const shown = expanded ? missing : missing.slice(0, MISSING_PREVIEW_COUNT)
    const hidden = missing.length - shown.length

    return (
        <span className={styles.missing}>
            {i18n.t('missing {{count}}', { count: missing.length })}
            {': '}
            {shown.map((id) => nameOf(id)).join(', ')}
            {hidden > 0 && !expanded && (
                <Button small secondary onClick={() => setExpanded(true)}>
                    {i18n.t('show {{count}} more', { count: hidden })}
                </Button>
            )}
        </span>
    )
}

export const ManageabilityReport = ({
    authorities,
    roleCount,
    allRoles,
    systemAuthorities,
}: ManageabilityReportProps) => {
    const report = useMemo(
        () => manageabilityReport(authorities, allRoles),
        [authorities, allRoles]
    )
    const nameOf = useMemo(() => {
        const names = new Map(systemAuthorities.map((a) => [a.id, a.name]))
        return (id: string) => names.get(id) ?? id
    }, [systemAuthorities])

    const grantedBy = authorities.has(AUTHORITY_ALL)
        ? AUTHORITY_ALL
        : authorities.has(AUTHORITY_USER_ADD)
          ? AUTHORITY_USER_ADD
          : AUTHORITY_USER_ADD_IN_GROUP

    return (
        <div className={styles.report}>
            <p className={styles.summary}>
                {i18n.t(
                    '{{roles}} roles, {{authorities}} authorities combined',
                    {
                        roles: roleCount,
                        authorities: authorities.size,
                        nsSeparator: '###',
                    }
                )}
            </p>

            {!report.canAdminister ? (
                <NoticeBox warning title={i18n.t('Cannot administer users')}>
                    {i18n.t(
                        'None of these roles grants an authority for administering users, so this combination cannot manage any users regardless of its other authorities. Add/Update User (F_USER_ADD) is the authority that grants it.',
                        { nsSeparator: '###' }
                    )}
                </NoticeBox>
            ) : (
                <>
                    <p className={styles.verdict}>
                        {i18n.t('Can administer users, via {{authority}}', {
                            authority: nameOf(grantedBy),
                            nsSeparator: '###',
                        })}
                    </p>
                    {report.limitedToManagedGroups && (
                        <NoticeBox
                            title={i18n.t('Limited to managed user groups')}
                        >
                            {i18n.t(
                                'This combination can only administer users in user groups it manages. Whether a given user falls inside those groups depends on user-group configuration, which this tool does not evaluate.',
                                { nsSeparator: '###' }
                            )}
                        </NoticeBox>
                    )}

                    <h3 className={styles.listTitle}>
                        {i18n.t('Can manage ({{count}})', {
                            count: report.manageable.length,
                        })}
                    </h3>
                    {report.manageable.length > 0 ? (
                        <ul className={styles.roleList}>
                            {report.manageable.map((role) => (
                                <li key={role.id}>{role.displayName}</li>
                            ))}
                        </ul>
                    ) : (
                        <p className={styles.emptyText}>
                            {i18n.t('No user roles can be managed.')}
                        </p>
                    )}

                    <h3 className={styles.listTitle}>
                        {i18n.t('Cannot manage ({{count}})', {
                            count: report.blocked.length,
                        })}
                    </h3>
                    {report.blocked.length > 0 ? (
                        <ul className={styles.roleList}>
                            {report.blocked.map(({ role, missing }) => (
                                <li key={role.id}>
                                    {role.displayName}{' '}
                                    <MissingAuthorities
                                        missing={missing}
                                        nameOf={nameOf}
                                    />
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className={styles.emptyText}>
                            {i18n.t('All user roles can be managed.')}
                        </p>
                    )}
                </>
            )}
        </div>
    )
}
```

`src/components/ManageabilityReport.module.css`:

```css
.report {
    margin-block-start: var(--spacers-dp16);
}

.summary {
    margin: 0;
    color: var(--colors-grey700);
    font-size: 13px;
}

.verdict {
    margin-block: var(--spacers-dp8);
    font-weight: 500;
}

.listTitle {
    margin-block: var(--spacers-dp16) var(--spacers-dp8);
    font-size: 14px;
    font-weight: 600;
}

.roleList {
    margin: 0;
    padding-inline-start: var(--spacers-dp24);
    columns: 2;
}

.roleList li {
    break-inside: avoid;
    margin-block-end: 4px;
}

.missing {
    color: var(--colors-grey700);
    font-size: 12px;
}

.emptyText {
    margin: 0;
    color: var(--colors-grey600);
    font-style: italic;
}
```

Note: `Tag` is imported for use by the pages in Tasks 4 and 5, not here — remove the import if lint flags it as unused.

Verified prop surfaces in `@dhis2/ui` 10.11 (do not assume others): `Tag` takes `positive` / `bold` / `icon` / `children`; `Button` takes `small` / `secondary` / `primary` / `onClick`; `CircularLoader` takes only `className` / `dataTest` / `invert` — it has **no** `small` prop; `TransferOption`'s `label` is `PropTypes.node`, which is why the badge can be passed as JSX while `Transfer`'s own `options[].label` stays a plain string for filtering.

- [ ] **Step 2: Verify it compiles**

Run: `pnpm run lint && pnpm exec tsc --noEmit`
Expected: clean. (The component has no consumer yet; Task 4 renders it.)

- [ ] **Step 3: Commit**

```bash
git add src/components/ManageabilityReport.tsx src/components/ManageabilityReport.module.css
git commit -m "feat: add the manageability report component"
```

---

### Task 4: Check page — role combination mode

**Files:**

- Modify: `src/pages/CheckRolesPage.tsx` (replacing the Task 2 stub), `src/pages/CheckRolesPage.module.css` (create)

**Interfaces:**

- Consumes: `<ManageabilityReport>` (Task 3); `aggregateAuthorities`, `isUserAdminRole` from `@/domain/userRole`; `useUserRoles`, `useSystemAuthorities`.
- Produces: the page at `/`, reading and writing the `roles` query parameter.

- [ ] **Step 1: Write the page**

`src/pages/CheckRolesPage.tsx`:

```tsx
import i18n from '@dhis2/d2-i18n'
import {
    CircularLoader,
    NoticeBox,
    Tag,
    Transfer,
    TransferOption,
} from '@dhis2/ui'
import React, { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import styles from './CheckRolesPage.module.css'
import { ManageabilityReport } from '@/components/ManageabilityReport'
import { aggregateAuthorities, isUserAdminRole } from '@/domain/userRole'
import { useSystemAuthorities } from '@/hooks/useSystemAuthorities'
import { useUserRoles } from '@/hooks/useUserRoles'

const ROLES_PARAM = 'roles'

export const CheckRolesPage = () => {
    const [searchParams, setSearchParams] = useSearchParams()
    const {
        userRoles,
        isLoading: isLoadingRoles,
        error: rolesError,
    } = useUserRoles()
    const {
        authorities: systemAuthorities,
        isLoading: isLoadingAuthorities,
        error: authoritiesError,
    } = useSystemAuthorities()

    const selectedIds = useMemo(() => {
        const raw = searchParams.get(ROLES_PARAM)
        const requested = raw ? raw.split(',').filter(Boolean) : []
        const known = new Set((userRoles ?? []).map((role) => role.id))
        // Ignore ids that are not roles visible to this user
        return requested.filter((id) => known.has(id))
    }, [searchParams, userRoles])

    const setSelectedIds = (ids: string[]) => {
        const next = new URLSearchParams(searchParams)
        if (ids.length > 0) {
            next.set(ROLES_PARAM, ids.join(','))
        } else {
            next.delete(ROLES_PARAM)
        }
        setSearchParams(next, { replace: true })
    }

    const sortedRoles = useMemo(() => {
        const roles = [...(userRoles ?? [])]
        // user-admin roles first, then the API's displayName order
        return roles.sort(
            (a, b) => Number(isUserAdminRole(b)) - Number(isUserAdminRole(a))
        )
    }, [userRoles])

    const adminRoleIds = useMemo(
        () =>
            new Set(
                (userRoles ?? []).filter(isUserAdminRole).map((role) => role.id)
            ),
        [userRoles]
    )

    const selectedRoles = useMemo(
        () => (userRoles ?? []).filter((role) => selectedIds.includes(role.id)),
        [userRoles, selectedIds]
    )
    const combinedAuthorities = useMemo(
        () => aggregateAuthorities(selectedRoles),
        [selectedRoles]
    )

    if (isLoadingRoles || isLoadingAuthorities) {
        return (
            <div className={styles.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    const error = rolesError || authoritiesError
    if (error || !userRoles || !systemAuthorities) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error?.message || i18n.t('An unknown error occurred')}
            </NoticeBox>
        )
    }

    return (
        <div className={styles.card}>
            <h1 className={styles.title}>
                {i18n.t('Check what a role combination can manage')}
            </h1>
            <p className={styles.description}>
                {i18n.t(
                    'Pick the roles a user holds. Their authorities are combined, because a user administers other users with everything their roles grant together, not with one role at a time.',
                    { nsSeparator: '###' }
                )}
            </p>

            <div className={styles.field}>
                <span className={styles.fieldLabel}>
                    {i18n.t('User roles held')}
                </span>
                <Transfer
                    options={sortedRoles.map((role) => ({
                        label: role.displayName,
                        value: role.id,
                    }))}
                    selected={selectedIds}
                    onChange={({ selected }) => setSelectedIds(selected)}
                    renderOption={(option) => (
                        <TransferOption
                            {...option}
                            label={
                                <span className={styles.option}>
                                    {option.label}
                                    {adminRoleIds.has(option.value) && (
                                        <Tag positive>
                                            {i18n.t('user admin')}
                                        </Tag>
                                    )}
                                </span>
                            }
                        />
                    )}
                    filterable
                    filterablePicked
                    height="280px"
                />
            </div>

            {selectedIds.length === 0 ? (
                <p className={styles.emptyText}>
                    {i18n.t(
                        'Select one or more roles to see what they can manage.'
                    )}
                </p>
            ) : (
                <ManageabilityReport
                    authorities={combinedAuthorities}
                    roleCount={selectedRoles.length}
                    allRoles={userRoles}
                    systemAuthorities={systemAuthorities}
                />
            )}
        </div>
    )
}
```

`src/pages/CheckRolesPage.module.css` — copy `src/pages/UpdateRolePage.module.css` and keep the `.card`, `.title`, `.description`, `.field`, `.fieldLabel`, `.loadingContainer`, `.emptyText` rules, then add:

```css
.option {
    display: inline-flex;
    align-items: center;
    gap: var(--spacers-dp8);
}
```

- [ ] **Step 2: Verify and check by hand**

Run: `pnpm run lint && pnpm exec tsc --noEmit && pnpm test`
Expected: clean, 21 tests pass.

Then with `pnpm start --proxy …`, on the demo database confirm: user-admin roles show the badge and sort first; selecting "Data entry clerk" alone reports "cannot administer users"; selecting a user-admin role plus another role changes the Can-manage list; the URL gains `?roles=<id>,<id>` and reloading the page keeps the selection; editing the URL to an unknown id silently ignores it.

- [ ] **Step 3: Commit**

```bash
git add src/pages/CheckRolesPage.tsx src/pages/CheckRolesPage.module.css
git commit -m "feat: check what a combination of roles can manage"
```

---

### Task 5: Check page — user lookup mode

**Files:**

- Create: `src/hooks/useDebouncedValue.ts`, `src/hooks/useUserSearch.ts`, `src/pages/CheckUserPage.module.css`
- Modify: `src/pages/CheckUserPage.tsx` (replacing the Task 2 stub)

**Interfaces:**

- Consumes: `<ManageabilityReport>` (Task 3); `aggregateAuthorities`, `isUserAdminRole`; `useUserRoles`, `useSystemAuthorities`, `useApiDataQuery`.
- Produces: `useDebouncedValue<T>(value: T, delayMs: number): T`; `useUserSearch(query: string): { users?: SearchedUser[]; isLoading: boolean; error?: Error }` where `SearchedUser = { id: string; displayName: string; username?: string; userRoles: UserRole[] }`; the page at `/check-user`.

- [ ] **Step 1: Write the debounce helper**

`src/hooks/useDebouncedValue.ts`:

```ts
import { useEffect, useState } from 'react'

/** The value as it was `delayMs` after it last changed. */
export const useDebouncedValue = <T>(value: T, delayMs: number): T => {
    const [debounced, setDebounced] = useState(value)

    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delayMs)
        return () => clearTimeout(timer)
    }, [value, delayMs])

    return debounced
}
```

- [ ] **Step 2: Write the search hook**

`src/hooks/useUserSearch.ts`:

```ts
import { UserRole } from '@/types/userRole'
import { useApiDataQuery } from '@/utils/useApiDataQuery'

export const MIN_QUERY_LENGTH = 2

export interface SearchedUser {
    id: string
    displayName: string
    username?: string
    userRoles: UserRole[]
}

interface UsersResponse {
    users: SearchedUser[]
}

/**
 * Users matching a name or username fragment, with their roles and each
 * role's authorities, so manageability can be computed without extra calls.
 */
export const useUserSearch = (query: string) => {
    const trimmed = query.trim()
    const { data, isLoading, error } = useApiDataQuery<UsersResponse>({
        queryKey: ['users', 'search', trimmed],
        query: {
            resource: 'users',
            params: {
                query: trimmed,
                fields: 'id,displayName,username,userRoles[id,displayName,authorities]',
                order: 'displayName:asc',
                pageSize: 10,
            },
        },
        enabled: trimmed.length >= MIN_QUERY_LENGTH,
        keepPreviousData: true,
    })

    return { users: data?.users, isLoading, error }
}
```

- [ ] **Step 3: Write the page**

`src/pages/CheckUserPage.tsx`:

```tsx
import i18n from '@dhis2/d2-i18n'
import { CircularLoader, InputField, NoticeBox, Tag } from '@dhis2/ui'
import React, { useMemo, useState } from 'react'
import styles from './CheckUserPage.module.css'
import { ManageabilityReport } from '@/components/ManageabilityReport'
import { aggregateAuthorities, isUserAdminRole } from '@/domain/userRole'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useSystemAuthorities } from '@/hooks/useSystemAuthorities'
import {
    MIN_QUERY_LENGTH,
    SearchedUser,
    useUserSearch,
} from '@/hooks/useUserSearch'
import { useUserRoles } from '@/hooks/useUserRoles'

export const CheckUserPage = () => {
    const [query, setQuery] = useState('')
    const [selectedUser, setSelectedUser] = useState<SearchedUser>()
    const debouncedQuery = useDebouncedValue(query, 300)

    const {
        users,
        isLoading: isSearching,
        error: searchError,
    } = useUserSearch(debouncedQuery)
    const {
        userRoles,
        isLoading: isLoadingRoles,
        error: rolesError,
    } = useUserRoles()
    const {
        authorities: systemAuthorities,
        isLoading: isLoadingAuthorities,
        error: authoritiesError,
    } = useSystemAuthorities()

    const userAuthorities = useMemo(
        () => aggregateAuthorities(selectedUser?.userRoles ?? []),
        [selectedUser]
    )

    if (isLoadingRoles || isLoadingAuthorities) {
        return (
            <div className={styles.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    const error = rolesError || authoritiesError
    if (error || !userRoles || !systemAuthorities) {
        return (
            <NoticeBox error title={i18n.t('Error loading data')}>
                {error?.message || i18n.t('An unknown error occurred')}
            </NoticeBox>
        )
    }

    return (
        <div className={styles.card}>
            <h1 className={styles.title}>{i18n.t('Look up a user')}</h1>
            <p className={styles.description}>
                {i18n.t(
                    'Search for a user to see which user roles they can manage, based on the authorities of all their roles combined.',
                    { nsSeparator: '###' }
                )}
            </p>

            <div className={styles.field}>
                <InputField
                    className={styles.search}
                    label={i18n.t('Search by name or username')}
                    value={query}
                    onChange={({ value }) => {
                        setQuery(value ?? '')
                        setSelectedUser(undefined)
                    }}
                    placeholder={i18n.t('At least {{count}} characters', {
                        count: MIN_QUERY_LENGTH,
                    })}
                />
            </div>

            {searchError && (
                <NoticeBox error title={i18n.t('Search failed')}>
                    {searchError.message}
                </NoticeBox>
            )}

            {!selectedUser && isSearching && <CircularLoader />}

            {!selectedUser && users && users.length === 0 && (
                <p className={styles.emptyText}>
                    {i18n.t('No users match that search.')}
                </p>
            )}

            {!selectedUser && users && users.length > 0 && (
                <ul className={styles.resultList}>
                    {users.map((user) => (
                        <li key={user.id}>
                            <button
                                type="button"
                                className={styles.resultButton}
                                onClick={() => setSelectedUser(user)}
                            >
                                {user.displayName}
                                {user.username && (
                                    <span className={styles.username}>
                                        {user.username}
                                    </span>
                                )}
                            </button>
                        </li>
                    ))}
                </ul>
            )}

            {selectedUser && (
                <>
                    <h2 className={styles.sectionTitle}>
                        {selectedUser.displayName}
                    </h2>
                    <ul className={styles.roleList}>
                        {selectedUser.userRoles.map((role) => (
                            <li key={role.id}>
                                {role.displayName}{' '}
                                {isUserAdminRole(role) && (
                                    <Tag positive>{i18n.t('user admin')}</Tag>
                                )}
                            </li>
                        ))}
                    </ul>
                    <ManageabilityReport
                        authorities={userAuthorities}
                        roleCount={selectedUser.userRoles.length}
                        allRoles={userRoles}
                        systemAuthorities={systemAuthorities}
                    />
                </>
            )}
        </div>
    )
}
```

`src/pages/CheckUserPage.module.css` — start from `CheckRolesPage.module.css` (same `.card`, `.title`, `.description`, `.field`, `.loadingContainer`, `.emptyText`, `.sectionTitle`) and add:

```css
.search {
    max-inline-size: 400px;
}

.resultList,
.roleList {
    margin: 0;
    padding-inline-start: 0;
    list-style: none;
}

.resultButton {
    display: flex;
    gap: var(--spacers-dp8);
    inline-size: 100%;
    padding: var(--spacers-dp8);
    border: none;
    border-block-end: 1px solid var(--colors-grey300);
    background: none;
    cursor: pointer;
    text-align: start;
    font-size: 14px;
}

.resultButton:hover {
    background: var(--colors-grey100);
}

.username {
    color: var(--colors-grey600);
}

.roleList li {
    margin-block-end: 4px;
}
```

- [ ] **Step 4: Verify and check by hand**

Run: `pnpm run lint && pnpm exec tsc --noEmit && pnpm test`
Expected: clean, 21 tests pass.

By hand on the demo database: searching "traore" lists John/Alain Traore; selecting one shows their roles and the report; a single-character query fires no request (watch the network tab); a user whose roles include a superuser role reports that everything is manageable.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useDebouncedValue.ts src/hooks/useUserSearch.ts src/pages/CheckUserPage.tsx src/pages/CheckUserPage.module.css
git commit -m "feat: look up a user and see which roles they can manage"
```

---

### Task 6: Trim the write pages

**Files:**

- Modify: `src/pages/UpdateRolePage.tsx`, `src/pages/CreateRolePage.tsx`

**Interfaces:**

- Consumes: `canAdministerUsers`, `canManageRole` from `@/domain/userRole`.
- Produces: no new exports.

- [ ] **Step 1: Remove the analysis from the Update page**

In `src/pages/UpdateRolePage.tsx`: delete `managedRoles` from the `useMemo` return (and from its destructuring), delete the "User roles that can be managed" heading, its `<ul>` and the "cannot manage any other user roles yet" fallback. Keep `candidateRoles` and `hasRolesBeyondReach` — the picker and its empty state still need them. Then add a link under the page description:

```tsx
import { Link } from 'react-router-dom'
```

```tsx
{
    selectedRole && (
        <p className={styles.checkLink}>
            <Link to={`/?roles=${selectedRole.id}`}>
                {i18n.t('Check what this role can manage')}
            </Link>
        </p>
    )
}
```

Add to `src/pages/UpdateRolePage.module.css`:

```css
.checkLink {
    margin-block: var(--spacers-dp8);
    font-size: 14px;
}
```

- [ ] **Step 2: Finish the Create page**

In `src/pages/CreateRolePage.tsx`, remove the `canAddUserRoles` prop from `CreateRoleForm` (its type, its destructuring, the `disabled={!canAddUserRoles || isCreating}` — leave `disabled={isCreating}`) and from the `<CreateRoleForm …>` call site. Then add the warning. Inside `CreateRoleForm`, after `useForm`:

```tsx
import { useForm, Controller, useWatch } from 'react-hook-form'
import { canAdministerUsers } from '@/domain/userRole'
```

```tsx
const watchedRoles = useWatch({ control, name: 'rolesToManage' })
const watchedAuthorities = useWatch({
    control,
    name: 'additionalAuthorities',
})
const resultingAuthorities = useMemo(() => {
    const fromRoles = manageableRoles
        .filter((role) => (watchedRoles ?? []).includes(role.id))
        .flatMap((role) => role.authorities ?? [])
    return new Set([...(watchedAuthorities ?? []), ...fromRoles])
}, [manageableRoles, watchedRoles, watchedAuthorities])
const willAdministerUsers = canAdministerUsers(resultingAuthorities)
```

and render just above the `<ButtonStrip>`:

```tsx
{
    resultingAuthorities.size > 0 && !willAdministerUsers && (
        <div className={styles.field}>
            <NoticeBox
                warning
                title={i18n.t('This role cannot administer users')}
            >
                {i18n.t(
                    'None of the selected roles or authorities grants Add/Update User, so members of this role will not be able to manage other users.',
                    { nsSeparator: '###' }
                )}
            </NoticeBox>
        </div>
    )
}
```

- [ ] **Step 3: Verify and check by hand**

Run: `pnpm run lint && pnpm exec tsc --noEmit && pnpm test`
Expected: clean, 21 tests pass.

By hand: on Create, deselect all four default authorities and pick a role with no user-admin authority — the warning appears; re-add Add/Update User — it disappears. On Update, the managed-roles list is gone and the Check link opens `/` with that role preselected.

- [ ] **Step 4: Commit**

```bash
git add src/pages
git commit -m "feat: move role analysis out of Update and warn on non-admin roles"
```

---

### Task 7: Strings and documentation

**Files:**

- Modify: `i18n/en.pot`, `CHANGELOG.md`, `docs/MANUAL.md`

- [ ] **Step 1: Extract the strings**

Run: `pnpm exec d2-app-scripts i18n extract`

Then re-add the two manifest entries the extractor drops (it only sees them after a build) at the end of `i18n/en.pot`:

```
msgctxt "Application title"
msgid "__MANIFEST_APP_TITLE"
msgstr "User Admin Role Aggregator"

msgctxt "Application description"
msgid "__MANIFEST_APP_DESCRIPTION"
msgstr ""
"Tool to validate and create/modify user roles for users who should manage "
"other users."
```

Verify every new string is present: `grep -c msgid i18n/en.pot` should exceed the previous count, and `grep "Check what a role combination" i18n/en.pot` should match.

- [ ] **Step 2: Update the CHANGELOG**

Add to the `### Changed` list of `## [1.0.0]`:

```markdown
- The app now has three sections: "Check access" for read-only inspection, plus "Create new role" and "Update existing role", which are shown only to users who may manage user roles.
- Access checks evaluate a combination of roles rather than one role at a time, because a user administers others with the authorities of all their roles combined. A combination that grants no user-administration authority is now reported as such instead of listing roles it cannot really manage.
- A user can be looked up by name to see which roles they can manage, and which authorities are missing for the ones they cannot.
- The landing page is now the access check; role creation moved to `#/create`.
```

- [ ] **Step 3: Update the manual**

In `docs/MANUAL.md`, replace the table of contents and Usage sections so they cover, in order: "Check access — role combination", "Check access — look up a user", "Create New User Role for User Admins", "Validate or Update Existing User Admin Role". For the two check sections, document that authorities are combined across roles, that a combination without a user-administration authority can manage nobody, and this limitation verbatim:

> The tool evaluates authorities only. If a role's user-administration authority is "Add/Update User Within Managed Group", whether a particular user can be administered also depends on user-group management, which this tool does not evaluate.

Also state that Create and Update are visible only to users holding "Add/Update Public User Role" or "Add/Update Private User Role".

- [ ] **Step 4: Verify and commit**

Run: `pnpm run lint`
Expected: clean (prettier checks markdown too — run `pnpm run format` if it complains).

```bash
git add i18n/en.pot CHANGELOG.md docs/MANUAL.md
git commit -m "docs: describe the access-check sections"
```

---

### Task 8: End-to-end coverage

**Files:**

- Modify: `tests/e2e/nonsuperuser_test.py`, `tests/e2e/suite.py`, `tests/e2e/README.md`

**Interfaces:**

- Consumes: the app as installed on a disposable instance. Existing helpers in each script (`api`, `cookie`, `app_frame`, `rec`) are reused.

- [ ] **Step 1: Add nav-gating assertions to `nonsuperuser_test.py`**

In `check_read_only_user(frame)` — the user with app access but no role-management authority — assert the write section is absent and the check section present. Add module constants beside the existing ones:

```python
NAV_CREATE = "Create new role"
NAV_CHECK = "Role combination"
```

and inside `check_read_only_user`:

```python
    create_visible = frame.get_by_text(NAV_CREATE).count() > 0
    rec("Read-only user: no create/update nav", "PASS" if not create_visible else "FAIL")
    check_visible = frame.get_by_text(NAV_CHECK).count() > 0
    rec("Read-only user: check section available", "PASS" if check_visible else "FAIL")
```

The two existing assertions in that function (the missing-permission warning and the disabled Create button) no longer apply, because that page is now guarded — replace them with a direct-navigation check:

```python
    page = frame.page
    page.goto(f"{BASE}/api/apps/{APP_KEY}/index.html#/create", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    guarded = app_frame(page).get_by_text("This page needs one of these authorities").count() > 0
    rec("Read-only user: /create is guarded", "PASS" if guarded else "FAIL")
```

- [ ] **Step 2: Add a role-combination assertion to `nonsuperuser_test.py`**

Add a function that drives the Check page as the manager-scenario user and compares the verdict against an API-computed expectation:

```python
def check_role_combination(page, frame, role_names):
    """Select roles on the Check page and compare the verdict with the API."""
    _, res = api("GET", "/api/userRoles?fields=id,displayName,authorities&paging=false")
    roles = res["userRoles"]
    by_name = {r["displayName"]: r for r in roles}
    held = set()
    for name in role_names:
        held |= set(by_name[name].get("authorities") or [])
    can_administer = bool(
        held & {"ALL", "F_USER_ADD", "F_USER_ADD_WITHIN_MANAGED_GROUP"}
    )
    expected = sorted(
        r["displayName"]
        for r in roles
        if "ALL" not in (r.get("authorities") or [])
        and all(a in held for a in (r.get("authorities") or []))
    ) if can_administer else []

    frame.locator("a", has_text=NAV_CHECK).click()
    page.wait_for_timeout(1500)
    frame = app_frame(page)
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
        rec("Check page: combination without user-admin authority", "PASS" if shown else "FAIL")
        return

    listed = sorted(
        t.strip() for t in frame.locator('[data-test="dhis2-uicore-noticebox"] ~ ul li').all_inner_texts()
    )
    rec("Check page: can-manage list matches the API", "PASS" if listed == expected else "FAIL",
        f"shown={listed[:5]} expected={expected[:5]}")
```

Call it from `run_manager_scenario` after `drive_app`, with two role names from the demo seed: `["User manager", "M and E Officer"]`. If the locator for the can-manage list proves brittle, add `data-test="can-manage-list"` to the `<ul>` in `ManageabilityReport.tsx` and select on that instead — prefer the explicit hook over CSS-sibling selectors.

- [ ] **Step 3: Point `suite.py` at the new routes**

`suite.py`'s create flow now lives at `#/create` rather than `/`. In `flow_create`, after `page.goto(launch, …)`, navigate explicitly:

```python
        page.goto(f"{launch}#/create", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
```

and in `flow_update`, replace the sidebar click with the same explicit hash navigation to `#/update`, since the link labels moved. Keep every existing assertion otherwise.

- [ ] **Step 4: Update the e2e README**

Add one paragraph describing the new assertions and noting that `suite.py` now navigates by URL hash rather than by sidebar label, so it does not break when nav labels change.

- [ ] **Step 5: Run everything against a live instance**

```bash
pnpm run build
DHIS2_ADMIN_PASSWORD=<password> python3 tests/e2e/suite.py --base http://dhis2-<instance>:8080 --label 2.42
DHIS2_BASE_URL=http://dhis2-<instance>:8080 DHIS2_ADMIN_PASSWORD=<password> python3 tests/e2e/nonsuperuser_test.py
DHIS2_BASE_URL=http://dhis2-<instance>:8080 DHIS2_ADMIN_PASSWORD=<password> python3 tests/e2e/extra_tests.py
```

Expected: `suite.py` 20 steps / 0 FAIL, `nonsuperuser_test.py` 0 FAIL, `extra_tests.py` 0 FAIL. Investigate any failure before committing — a red suite here means the app changed behaviour, not that the test is wrong.

- [ ] **Step 6: Commit**

```bash
git add tests/e2e
git commit -m "test: cover nav gating and role-combination checks"
```

---

### Task 9: Cross-version verification (2.40 – 2.43, Sierra Leone and Laos data)

Runs only after Tasks 1–8 are complete and the branch review is clean. This is a verification task: it changes no application code. If it finds a defect, that defect is fixed under the task it belongs to, not here.

**Files:**

- Modify: `docs/review-2026-08-19/UI-TEST-RESULTS.md` (create the directory and file)

**Interfaces:**

- Consumes: the built bundle and the three e2e scripts.

**Instance matrix.** Four versions, mixing the two seed families so the app is exercised against both metadata shapes. Use the seed whose `dhis2_version` matches the instance version — never a cross-version seed, which triggers a 10–25 minute Flyway migration.

| DHIS2 | Seed                               | Notes                                                               |
| ----- | ---------------------------------- | ------------------------------------------------------------------- |
| 2.40  | `dhis2-db-sierra-leone_V40.sql.gz` | declared minimum; no global shell                                   |
| 2.41  | `lao_hmis_demo_v41.sql.gz`         | Laos metadata; expect `/api/authorities` to need the legacy warm-up |
| 2.42  | `dhis2-db-sierra-leone_v42.sql.gz` | global shell present                                                |
| 2.43  | `lao_hmis_demo_v43.sql.gz`         | Laos metadata, current release                                      |

- [ ] **Step 1: Provision, test, tear down — one version at a time**

The broker caps concurrent `agent-*` instances and two booting at once starve each other, so complete each row before creating the next. Per row:

```bash
# create (see the dhis2-instances skill for the broker API and polling)
# then, once the create job reports succeeded:
curl -s -o /dev/null -u local_admin:district "$BASE/dhis-web-commons/security/login.action"   # warm the legacy layer
pnpm run build
DHIS2_ADMIN_PASSWORD=district python3 tests/e2e/suite.py --base "$BASE" --label <version>
DHIS2_BASE_URL="$BASE" DHIS2_ADMIN_PASSWORD=district python3 tests/e2e/extra_tests.py
DHIS2_BASE_URL="$BASE" DHIS2_ADMIN_PASSWORD=district python3 tests/e2e/nonsuperuser_test.py
```

Use `local_admin` / `district` for any setup that creates users or assigns roles — the demo `admin` account is not a superuser on these seeds and DHIS2 refuses to grant it a role carrying authorities it lacks.

- [ ] **Step 2: Check the Laos rows by hand as well as by script**

The Laos seeds have a different role and authority population than Sierra Leone, so also confirm by hand on each Laos instance: the role-combination picker badges at least one role as "user admin"; a combination with no user-administration authority reports that it cannot administer users; and the user lookup returns results for a name present in that database.

- [ ] **Step 3: Record the results**

Write `docs/review-2026-08-19/UI-TEST-RESULTS.md` in the same shape as `docs/review-2026-08-18/UI-TEST-RESULTS.md`: instance table with versions and seeds, one row per flow per version, console/network hygiene, and any version-specific differences. State explicitly which instances were deleted afterwards.

- [ ] **Step 4: Commit**

```bash
git add docs/review-2026-08-19
git commit -m "test: verify on 2.40-2.43 with Sierra Leone and Laos data"
```

## Self-Review

**Spec coverage**

| Spec section                                                                                  | Task                               |
| --------------------------------------------------------------------------------------------- | ---------------------------------- |
| Rules table (7 functions)                                                                     | 1                                  |
| Types-vs-rules split, five import sites                                                       | 1                                  |
| `limitedToManagedGroups` condition                                                            | 1 (rule), 3 (display)              |
| Routes table, landing page change                                                             | 2                                  |
| Sidebar groups, omitted when unable to write                                                  | 2                                  |
| `RequireAuthority`, parameterised, `ALL` passes                                               | 2                                  |
| `AddRolesWarning` and `canAddUserRoles` removal                                               | 2 (component), 6 (Create's button) |
| Role-combination mode, badges, sorting                                                        | 4                                  |
| `?roles=` deep link, unknown ids ignored                                                      | 4                                  |
| User-lookup mode, one API call, debounce, min length                                          | 5                                  |
| `ManageabilityReport` three blocks, expand toggle                                             | 3                                  |
| Reuse of `useUserRoles` / `useSystemAuthorities`; new `useUserSearch` with `keepPreviousData` | 3, 4, 5                            |
| Create keeps filtering, gains no-admin warning                                                | 6                                  |
| Update loses analysis, gains Check link                                                       | 6                                  |
| Unit tests incl. the union bug                                                                | 1                                  |
| e2e: gating, combination verdicts, no-admin case, user lookup                                 | 8                                  |
| MANUAL, CHANGELOG, i18n                                                                       | 7                                  |
| Non-goals                                                                                     | not implemented, by design         |

Two spec items deliberately not carried into tasks: the e2e "user lookup against a seeded demo user" is folded into Task 8 Step 2's pattern rather than given its own step, because it reuses the same API-comparison helper; and the spec's implementation-order list maps 1:1 onto Tasks 1–8, so it needs no separate task.

**Placeholder scan:** no TBD/TODO, no "add error handling" without code, no "similar to Task N". Every code step carries the actual code. The one judgement call left to the implementer is flagged explicitly (the brittle-locator fallback in Task 8 Step 2) with the preferred resolution stated.

**Type consistency:** `manageabilityReport(held, allRoles)` returns `{ canAdminister, limitedToManagedGroups, manageable, blocked }` in Task 1 and is consumed with exactly those names in Task 3. `ManageabilityReport` takes `authorities` / `roleCount` / `allRoles` / `systemAuthorities` in Task 3 and is called with those four props in Tasks 4 and 5. `useUserSearch` returns `{ users, isLoading, error }` in Task 5 and is destructured as such on the same page. `SearchedUser.userRoles` is `UserRole[]`, which is what `aggregateAuthorities` accepts. `useCurrentUserAuthorities` gains `canViewUsers` in Task 2 and is read in Task 2's sidebar only. Note the component and its exported type share the name `ManageabilityReport` (interface in `domain/userRole.ts`, component in `components/`); they are never imported into the same file, but if that changes, alias the type import.
