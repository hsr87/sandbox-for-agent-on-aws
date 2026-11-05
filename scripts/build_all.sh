#!/bin/zsh
# Rebuilds every generated file from results/raw. Anything under output/ is local and git ignores it.
set -e
cd "$(dirname "$0")/.."
python3 analysis/analyze.py >/dev/null
python3 analysis/cost_model.py >/dev/null
python3 analysis/facts.py
python3 analysis/verify_claims.py | grep -vE "^PASS" || true
python3 analysis/make_readme.py
[ -f output/build_local.sh ] && zsh output/build_local.sh
