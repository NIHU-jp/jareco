#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python tools/add_ddc.py "$@"
