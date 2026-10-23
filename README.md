# User Admin Role Aggregator

> ![Maturity: Validated](https://img.shields.io/badge/maturity-Validated-yellow)  
> Intended use: check which user roles a user administrator can manage, and create or extend roles for user administrators.  
> Maintainers: HISP Centre implementation team.

> [!WARNING]
> This tool is for system administrators. It is a DHIS2 app, but it has not been through the testing of the core apps. Use it with care, and try it on a copy of your database first.

The tool checks which user roles a combination of roles, or a user, can manage, and creates or extends user roles for user administrators. The user documentation is in [`docs/user/`](docs/user/tool-user-role-aggregator.md).

## Supported DHIS2 versions

DHIS2 2.40 and later (`minDHIS2Version` in `d2.config.js`). The e2e suite runs on the last three DHIS2 majors.

## Prerequisites

- Node.js 22 and [pnpm](https://pnpm.io). The pnpm version is pinned in `packageManager` in `package.json`; `corepack enable` picks it up.
- A DHIS2 instance to run against, for example a local one on port 8080. [DHIS2 in Docker](https://developers.dhis2.org/docs/tutorials/dhis2-docker/) describes how to start one.

## Develop

Install the dependencies:

```bash
pnpm install
```

Start the app against a local instance, then log in with that instance's credentials:

```bash
pnpm start --proxy http://localhost:8080
```

The app is built with the [DHIS2 App Platform](https://developers.dhis2.org/docs/app-platform/getting-started) (React, TypeScript, `@dhis2/ui`).

## Test, lint and build

```bash
pnpm test          # unit tests, next to the code as src/**/*.test.ts
pnpm run lint      # Ultracite: Oxlint and Oxfmt
pnpm run format    # format with Oxfmt
pnpm exec tsc --noEmit
pnpm run build     # writes build/bundle/tool-user-role-aggregator-<version>.zip
```

Linting and formatting follow [LINTING.md](https://github.com/dhis2-utils/reference-tool-conventions/blob/main/LINTING.md) in reference-tool-conventions. `AGENTS.md` has the same rules for coding agents.

The end-to-end suite in `e2e/` drives the built app on a throwaway DHIS2 instance. It deletes data, so read [`e2e/README.md`](e2e/README.md) before you run it.

## Release

CI (`.github/workflows/ci.yml`) lints, typechecks, tests and builds every pull request. A release is made by pushing a version tag:

1. Bump `version` in `package.json`, and add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`.
2. Merge to `main` and wait for CI to pass.
3. On an up-to-date `main`, run `git tag vx.y.z && git push origin vx.y.z`.

`.github/workflows/release.yml` then builds the app and publishes a GitHub release with the changelog section as notes and the bundle attached. The full procedure is in [RELEASE-WORKFLOW.md](https://github.com/dhis2-utils/reference-tool-conventions/blob/main/RELEASE-WORKFLOW.md) in reference-tool-conventions.

## License

BSD-3-Clause, © University of Oslo. See [LICENSE](LICENSE).
