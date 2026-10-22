#!/bin/sh
set -eu
cd "$(dirname "$0")"
# Compatibility entry point: edit CSV/JSON, never patch generated XML.
exec sh prepare.sh "$@"
