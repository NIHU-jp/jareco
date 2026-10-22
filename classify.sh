#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python tools/classify_resources.py "$@"
