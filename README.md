# User Role Aggregator Tool

Tool to validate and create/modify user roles for users who should manage other users.

> **WARNING**
> This tool is intended to be used by system administrators to perform specific tasks, it is not intended for end users. It is available as a DHIS2 app, but has not been through the same rigorous testing as normal core apps. It should be used with care, and always tested in a development environment.

The app is built with the [DHIS2 App Platform](https://developers.dhis2.org/docs/app-platform/getting-started) (React, TypeScript, `@dhis2/ui`). It requires DHIS2 2.40 or later.

## License

© Copyright University of Oslo 2024

## Getting started

### Install dependencies

The project uses [pnpm](https://pnpm.io):

```
pnpm install
```

### Start dev server

To start the development server against a DHIS2 instance:

```
pnpm start --proxy http://localhost:8080
```

Replace the proxy URL with the DHIS2 instance you want to develop against, then log in with the instance's credentials.

### Compile to zip

To build the app and produce a `.zip` file that can be installed in DHIS2 (written to `build/bundle/`):

```
pnpm run build
```

### Lint, format and test

```
pnpm run lint
pnpm run format
pnpm test
```

Unit tests live next to the code in `src/`. Playwright end-to-end tests (run against a disposable DHIS2 instance) live in `tests/e2e/` — see `tests/e2e/README.md`.

### Releasing

`.github/workflows/ci.yml` lints, typechecks, tests and builds every pull request. A release is cut only when a version tag is pushed:

1. Bump `version` in `package.json` and add the matching section to `CHANGELOG.md`.
2. Push a `v<version>` tag (e.g. `v1.0.0`).

`.github/workflows/release.yml` then verifies that the tag matches `package.json`, builds the app, and publishes a GitHub release with that CHANGELOG section as the notes and the bundle zip attached.

## Documentation

- `docs/MANUAL.md` — user manual (installation and usage)
- `docs/review-2026-07-09/` — findings and test results from the App Platform migration review
- `docs/review-2026-08-18/` — release-readiness test results on DHIS2 2.41 and 2.42
