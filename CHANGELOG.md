# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-08-18

### Changed

- Migrated the app from a plain-JavaScript webpack build (Materialize CSS, Choices.js) to the React-based DHIS2 App Platform (`@dhis2/cli-app-scripts`, `@dhis2/app-runtime`, `@dhis2/ui`, TypeScript).
- "Create New" and "Update" tabs are now separate pages with sidebar navigation.
- Role and authority pickers now use the DHIS2 Transfer component with filtering.
- The "Update" page validates the selected role automatically — no separate "Validate Role" button.
- User-facing strings are translatable via `@dhis2/d2-i18n`.
- The app now has three sections: "Check access" for read-only inspection, plus "Create new role" and "Update existing role", which are shown only to users who may manage user roles.
- Access checks evaluate a combination of roles rather than one role at a time, because a user administers others with the authorities of all their roles combined. A combination that grants no user-administration authority is now reported as such instead of listing roles it cannot really manage.
- A user can be looked up by name to see which roles they can manage, and which authorities are missing for the ones they cannot.
- The landing page is now the access check; role creation moved to `#/create`.

### Fixed

- Superusers (holders of the `ALL` authority) no longer see an incorrect "missing permissions" warning when their roles do not explicitly list the user-role authorities.
- Authorities are now fetched fresh from the server when a role is created or updated, so the saved role reflects concurrent edits made by other administrators instead of a stale cached list.
- Roles without any authorities are now (correctly) considered manageable by anyone, and appear in the role pickers and "can be managed" lists; the old app hid them.
- The role and authority pickers now list only the roles and authorities the signed-in user holds themselves, so the pickers cannot be used to build a role with more authorities than the user's own account. Superusers (holders of `ALL`) see everything, as before.

### Upgrade note

- The app identifier changed from `tool_user_role_aggregator` to `tool-user-role-aggregator` (hyphens instead of underscores). Installing the new version does **not** replace the old one — uninstall the old "User Admin Role Aggregator" app in App Management first.

## [0.3.1]

- fix bug blocking users with ALL from adding/editing roles

## [0.3.0]

- added support for global app shell in DHIS2 42 and above
- minor adjustments to labels

## [0.1.0]

### Added

- Initial release.
