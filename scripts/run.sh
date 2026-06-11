#!/usr/bin/env bash
# Convenience wrapper around the ViralAgent CLI.
#
#   ./scripts/run.sh once      # one dry-run cycle (no keys needed)
#   ./scripts/run.sh live      # one real cycle (needs ANTHROPIC_API_KEY)
#   ./scripts/run.sh daemon    # autonomous loop
#   ./scripts/run.sh scout     # just print the topic queue
set -euo pipefail
cd "$(dirname "$0")/.."

# Load .env if present so secrets are available to the process.
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

case "${1:-once}" in
  once)   python -m viralagent run-once --dry-run ;;
  live)   python -m viralagent run-once ;;
  daemon) python -m viralagent daemon ;;
  scout)  python -m viralagent scout ;;
  *)      python -m viralagent "$@" ;;
esac
