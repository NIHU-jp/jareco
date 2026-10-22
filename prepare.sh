#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python -m catalogue_source --csv data/resources.csv --output data/resources.xml "$@"
