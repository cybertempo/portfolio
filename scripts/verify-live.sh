#!/usr/bin/env bash
# [LAPTOP] bash scripts/verify-live.sh [url]
# Verify every published page/asset, exact security header values, and genuine
# 404 controls against the local build. Requires Python 3.11+ and curl.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/verify-live.py "$@"
