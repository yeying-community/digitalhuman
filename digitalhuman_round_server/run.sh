#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
exec uvicorn app.app:app --host 0.0.0.0 --port "${PORT:-8011}"
