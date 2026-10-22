#!/bin/sh
set -eu
cd "$(dirname "$0")"
sh build.sh
exec python -m http.server "${JPCOAR_PREVIEW_PORT:-8894}" --bind 127.0.0.1 --directory dist
