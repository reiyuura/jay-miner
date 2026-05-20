#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${JAY_ENV_FILE:-$ROOT_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

WALLET="${JAY_WALLET:-}"
THREADS="${JAY_THREADS:-4}"
LOG_DIR="${JAY_LOG_DIR:-$ROOT_DIR/logs}"
RESTART_DELAY="${JAY_RESTART_DELAY:-15}"
MAX_RESTARTS="${JAY_MAX_RESTARTS:-0}"
EXTRA_ARGS="${JAY_EXTRA_ARGS:-}"

if [[ -z "$WALLET" ]]; then
  echo "Missing JAY_WALLET. Put it in .env or export JAY_WALLET=yjay1..." >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/jay-miner-watchdog.log"
RESTARTS=0

printf '[%s] Watchdog started wallet=%s threads=%s max_restarts=%s\n' "$(date -Is)" "$WALLET" "$THREADS" "$MAX_RESTARTS" | tee -a "$LOG_FILE"

while true; do
  printf '[%s] Starting miner...\n' "$(date -Is)" | tee -a "$LOG_FILE"

  # Intentional word-splitting for optional CLI flags in JAY_EXTRA_ARGS.
  # shellcheck disable=SC2086
  python3 jay-miner.py --wallet "$WALLET" --threads "$THREADS" $EXTRA_ARGS 2>&1 | tee -a "$LOG_FILE"
  EXIT_CODE=${PIPESTATUS[0]}

  RESTARTS=$((RESTARTS + 1))
  printf '[%s] Miner exited with code %s. Restart #%s in %ss.\n' "$(date -Is)" "$EXIT_CODE" "$RESTARTS" "$RESTART_DELAY" | tee -a "$LOG_FILE"

  if [[ "$MAX_RESTARTS" != "0" && "$RESTARTS" -ge "$MAX_RESTARTS" ]]; then
    printf '[%s] Max restarts reached; watchdog exiting.\n' "$(date -Is)" | tee -a "$LOG_FILE"
    exit "$EXIT_CODE"
  fi

  sleep "$RESTART_DELAY"
done
