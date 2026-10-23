# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-10-23

### Changed

- **Update existing role** lists only user admin roles, that is roles with Add/Update User or Add/Update User Within Managed Group. Before, it also offered roles whose members cannot manage users, where adding managed roles has no effect.
- The list of user roles is refreshed when you return to a page or the window, at most once a minute, so roles changed in another app show up without a full reload.
- A failed create or update shows the server's reason, such as a role name that is already taken, instead of a generic message.
- The user search says when more users match than it shows, and no longer lets you pick a user from the previous search while a new one is loading.
- The sidebar's collapse button has an accessible name.
- The user documentation moved to `docs/user/`, and the end-to-end suite to `e2e/`, following the shared conventions for DHIS2 tools.
- Linting and formatting moved from ESLint and Prettier to Ultracite (Oxlint and Oxfmt).

### Security

- Creating or updating a role re-checks, when you submit, that you hold every authority it would grant. Before, a role that gained an authority after the page loaded could pass that authority on to the new role.

## [1.0.0] - 2026-08-18

### Upgrading

- The app identifier changed from `tool_user_role_aggregator` to `tool-user-role-aggregator` (hyphens instead of underscores). Installing the new version does not replace the old one. Install it, then uninstall the old "User Admin Role Aggregator" app in App Management, or two entries remain in the menu.
- Add the new app to every user role that gave access to the old one. Until then, users without the ALL authority cannot open it.
- Bookmarks to the old app URL stop working.

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

## [0.3.1]

### Fixed

- Users with ALL can add and edit roles again.

## [0.3.0]

### Added

- Support for the global app shell in DHIS2 2.42 and later.

### Changed

- Minor adjustments to labels.

## [0.1.0]

### Added

- Initial release.
