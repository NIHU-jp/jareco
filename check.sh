#!/bin/sh
set -eu
cd "$(dirname "$0")"
python -m unittest discover -s tests -v
if command -v node >/dev/null 2>&1; then
  node --check assets/search.js
  node --test tests/search.test.cjs
fi
