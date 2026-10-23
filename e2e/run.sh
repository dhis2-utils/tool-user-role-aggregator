#!/usr/bin/env bash
# Entry point of the e2e suite (contract version 1, see e2e/README.md).
#
#   DHIS2_URL=http://localhost:8080 DHIS2_USER=admin DHIS2_PASS=district \
#   LABEL=2.42 RESULTS_DIR=/tmp/out APP_ZIP=$PWD/build/bundle/tool-user-role-aggregator-1.1.0.zip \
#     e2e/run.sh
#
# Exit codes: 0 all tests passed, 1 a test failed, 2 the suite could not run.
# Throwaway instances only: the suite creates and deletes users and roles.
set -uo pipefail

missing=()
for var in DHIS2_URL DHIS2_USER DHIS2_PASS APP_ZIP RESULTS_DIR; do
    [ -n "${!var:-}" ] || missing+=("$var")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "run.sh: missing required variables: ${missing[*]} (see e2e/README.md)" >&2
    exit 2
fi
export DHIS2_URL="${DHIS2_URL%/}"
# The suite runs from e2e/, so a relative RESULTS_DIR must be resolved first.
RESULTS_DIR="$(cd "$RESULTS_DIR" 2>/dev/null && pwd)" || {
    echo "run.sh: RESULTS_DIR must be an existing directory" >&2
    exit 2
}
export RESULTS_DIR
# A stale results.json would make a crash below read as a test failure.
rm -f "$RESULTS_DIR/results.json"

if ! python3 -c 'import playwright' 2>/dev/null; then
    echo "run.sh: Playwright for Python is not installed (pip install -r e2e/requirements.txt)" >&2
    exit 2
fi

cd "$(dirname "$0")" || exit 2
python3 suite.py
status=$?
# Python exits 1 on an uncaught exception, which would read as a test failure.
if [ "$status" -gt 2 ] || { [ "$status" -eq 1 ] && [ ! -s "$RESULTS_DIR/results.json" ]; }; then
    exit 2
fi
exit "$status"
