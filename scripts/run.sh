#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src:${PYTHONPATH:-}
python -m tg_notifier.app --config config.yaml 