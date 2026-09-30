# Review findings: User Admin Role Aggregator v1.0.0

Reviewed: 2026-07-09 · Scope: code review + functional test (post-migration) · Reviewer: agent (Claude Fable 5, Claude Code)
DHIS2 versions tested: 2.40.12, 2.43.0.1 (Sierra Leone demo seeds)

## Summary

The app was migrated in this same session from a vanilla-JS webpack tool to the DHIS2 App Platform (React, TypeScript, `@dhis2/app-runtime`, `@dhis2/ui`, TanStack Query v4), then reviewed: independent adversarial static review, plus a 20-step functional suite (UI-driven, API-verified) run against live 2.40 and 2.43 instances. All functional flows pass on both versions, including global-shell URL sync on 2.43. The review surfaced one MEDIUM correctness regression and several LOW issues; the MEDIUM and two LOWs were **fixed during the review** and the suite re-run green. The app is in releasable shape; remaining items below are documentation-level.

## Findings

### HIGH

None.

### MEDIUM

#### M1. Authorities were aggregated from an infinitely-stale cache — FIXED during review

- **Where**: `src/hooks/useCreateUserRole.ts`, `src/hooks/useAddAuthoritiesToRole.ts` (previously aggregated from the `useUserRoles` list cached with `staleTime: Infinity`)
- **What**: The old vanilla app fetched each selected source role fresh (`GET /api/userRoles/{id}?fields=:owner`) at submit time. The first migration pass aggregated from the role list cached at page load. If another admin added or revoked an authority on a source role mid-session, the created/updated admin role would silently persist wrong authorities (missing a new one, or leaking a deliberately revoked one).
- **Fix applied**: added `src/hooks/fetchRoleAuthorities.ts`; both mutations now fetch the source roles' current authorities (`filter=id:in:[...]&fields=id,authorities`) at submit time before aggregating, restoring the old app's freshness guarantee with a single request. Functional suite re-run: green on 2.40 and 2.43.

### LOW

#### L1. Zod validation messages translated at module-import time — FIXED during review

- **Where**: `src/pages/CreateRolePage.tsx`
- **What**: `i18n.t()` calls in a module-scope schema ran before the platform set the user's locale, so validation messages would always render in English.
- **Fix applied**: schema is now built inside the component (`buildSchema` + `useMemo`).

#### L2. Create-page intro missing from `i18n/en.pot` — FIXED during review

- **Where**: `src/pages/CreateRolePage.tsx`, `i18n/en.pot`
- **What**: The string contains a colon; without an `nsSeparator` override the i18next scanner treated the text before the colon as a namespace and dropped the string from extraction (runtime display was unaffected because `@dhis2/d2-i18n` disables `nsSeparator`).
- **Fix applied**: added `{ nsSeparator: '###' }` to the call and regenerated `i18n/en.pot` with `d2-app-scripts i18n extract` (31 strings, all UI text now extracted).

#### L3. App identifier change means old installs are not upgraded — documented

- **Where**: `d2.config.js:4` (`name: 'user-role-aggregator'`) vs old `package.json` (`tool_user_role_aggregator`)
- **What**: DHIS2 keys installed apps by app key. Instances with the old tool installed will get a _second_ app when installing the new zip; the old one must be uninstalled manually.
- **Disposition**: an "Upgrade note" was added to `CHANGELOG.md`. If a seamless in-place upgrade matters more than the cleaner key, set `name` back to `tool_user_role_aggregator` before releasing — decide before the first 1.0.0 install.

#### L4. Deliberate behavior changes vs the old app — documented, confirm intent

- **Where**: `src/types/userRole.ts` (`canManageRole`), `src/hooks/useCurrentUserAuthorities.ts`
- **What**: Two intentional changes, both arguably bug fixes, now noted in `CHANGELOG.md`:
    1. Roles with **no authorities** are now considered manageable (empty set ⊆ anything); the old app hid them from the pickers and managed-roles lists.
    2. Superusers holding `ALL` are no longer shown the "missing permissions" warning (the old app only checked for the two `F_USERROLE_*` authorities literally).
- **Fix**: none needed if intended — revert `canManageRole`'s empty-set branch if the old behavior was deliberate.

#### L5. Users without app access cannot reach the in-app permission warning

- **Where**: observed in functional testing (limited user on 2.43); not a code defect
- **What**: A user lacking the app's access authority gets a blank/blocked app from the platform itself, so the friendly in-app "missing permissions" NoticeBox is only seen by users who can open the app but lack `F_USERROLE_*` authorities. Same as the old app; worth a line in `MANUAL.md` if support questions arise.

#### L6. Main bundle is 649 kB minified (Vite chunk-size warning)

- **Where**: build output (`build/assets/main-*.js`)
- **What**: Fine for an admin tool, but route-level `React.lazy` code-splitting would silence the warning and speed first load if the app grows.

## Claims investigated and rejected

- **"`type: 'update'` sends PATCH and the whole update flow is broken"** (raised by the independent static-review pass as HIGH): incorrect. `@dhis2/app-service-data`'s `getMutationFetchType` maps a non-partial `'update'` mutation to `'replace'`, which is sent as **PUT**. Confirmed empirically: the update flow passed on live 2.40 and 2.43 instances with API-verified merged authorities and preserved `description`/owner fields.

## Verified during review (not findings)

- `tsc --noEmit`, ESLint, Prettier, `pnpm test` (5 unit tests for `canManageRole`, added during review), and `d2-app-scripts build` all pass.
- `staleTime: Infinity` + `invalidateQueries` correctly refetches after mutations — the update page's managed-roles list refreshes without reload (tested).
- PUT payload preserves owner fields (`description` kept after update — API-verified).
- The `description` sent on create always exceeds DHIS2's 2-character minimum.
- Hash router + `SyncUrlWithGlobalShell`: browser URL tracks in-app navigation inside the 2.43 global shell (`#/update` ↔ `#/`), no page errors.
- Release workflow zip path matches the actual bundle name (`build/bundle/user-role-aggregator-1.0.0.zip`).
- CHANGELOG upgrade note, README (pnpm/App Platform instructions), and MANUAL usage sections updated to match the new UI.

## Environment gaps

- 2.41/2.42 not tested (seeds available; 2.40 = declared minimum and 2.43 = latest were chosen). The APIs used are stable across the range per dhis2-core source inspection of tags 2.40.0/2.41.0/2.42.0.
- The dev-server (`d2-app-scripts start --proxy`) path was not exercised; testing used the production bundle installed via `/api/apps` on both instances, which also covers manifest/global-shell integration.
