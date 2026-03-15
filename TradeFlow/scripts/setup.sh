#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip || true
if ! pip install -r requirements.txt; then
  echo "Dependency install failed. Verify internet access and try again." >&2
  exit 1
fi

echo "Environment ready."
echo "Next: cp .env.example .env && edit credentials/settings"
