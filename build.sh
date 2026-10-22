#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python -m jpcoar_ssg "$@"
