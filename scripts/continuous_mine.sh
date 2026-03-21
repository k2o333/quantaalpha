#!/bin/bash
#
# QuantaAlpha continuous mining scheduler
#
# Usage:
#   ./continuous_mine.sh "initial direction"               # infinite loop
#   ./continuous_mine.sh "initial direction" 3           # 3 iterations then exit
#   INTERVAL_SECONDS=3600 ./continuous_mine.sh "direction"
#
# Environment variables:
#   INTERVAL_SECONDS   Pause between iterations (default: 1800 = 30 min)
#   MAX_ITERATIONS     Stop after N iterations (default: unlimited)
#   CONFIG_PATH        Path to experiment config (default: configs/experiment.yaml)
#   LIBRARY_SUFFIX     Factor library suffix (optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Load .env
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
elif [ -f "${SCRIPT_DIR}/.env" ]; then
    set -a
    source "${SCRIPT_DIR}/.env"
    set +a
else
    echo "continuous_mine: .env not found" >&2
    exit 1
fi

# Defaults
INTERVAL_SECONDS="${INTERVAL_SECONDS:-1800}"
MAX_ITERATIONS="${MAX_ITERATIONS:-}"
LOG_DIR="${SCRIPT_DIR}/log"
LOG_FILE="${LOG_DIR}/continuous_mine_$(date +%Y%m%d).log"
PYTHON_BIN="${PYTHON_BIN:-python}"

mkdir -p "${LOG_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

log "=========================================="
log "QuantaAlpha Continuous Mining Started"
log "Direction: $1"
log "Interval: ${INTERVAL_SECONDS}s"
log "=========================================="

ITER=0
DIRECTION="$1"

while true; do
    ITER=$((ITER + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    log "[ITER ${ITER}] Starting mining cycle at ${TIMESTAMP}"

    EXPERIMENT_ID="cm_$(date +%Y%m%d_%H%M%S)"
    export EXPERIMENT_ID

    STEP_N="${STEP_N:-}"
    CONFIG_PATH="${CONFIG_PATH:-${PROJECT_ROOT}/configs/experiment.yaml}"
    LIBRARY_SUFFIX="${LIBRARY_SUFFIX:-${FACTOR_LIBRARY_SUFFIX:-}}"
    if [ -n "${LIBRARY_SUFFIX}" ]; then
        LIBRARY_PATH="${LIBRARY_PATH:-${PROJECT_ROOT}/data/factorlib/all_factors_library_${LIBRARY_SUFFIX}.json}"
    else
        LIBRARY_PATH="${LIBRARY_PATH:-${PROJECT_ROOT}/data/factorlib/all_factors_library.json}"
    fi

    set +e
    if [ -n "${STEP_N}" ]; then
        quantaalpha mine --direction "${DIRECTION}" --step_n "${STEP_N}" --config_path "${CONFIG_PATH}" 2>&1 | tee -a "${LOG_FILE}"
    else
        quantaalpha mine --direction "${DIRECTION}" --config_path "${CONFIG_PATH}" 2>&1 | tee -a "${LOG_FILE}"
    fi
    MINE_EXIT=${PIPESTATUS[0]}
    set -e
    if [ ${MINE_EXIT} -ne 0 ]; then
        log "[ITER ${ITER}] Mining exited with code ${MINE_EXIT}"
        exit "${MINE_EXIT}"
    else
        log "[ITER ${ITER}] Mining cycle completed successfully"
    fi

    set +e
    quantaalpha revalidate "${LIBRARY_PATH}" --dry_run True --no_write True 2>&1 | tee -a "${LOG_FILE}"
    REVALIDATE_EXIT=${PIPESTATUS[0]}
    set -e
    if [ ${REVALIDATE_EXIT} -ne 0 ]; then
        log "[ITER ${ITER}] Revalidate exited with code ${REVALIDATE_EXIT}"
        exit "${REVALIDATE_EXIT}"
    fi

    "${PYTHON_BIN}" - <<PY | tee -a "${LOG_FILE}"
from quantaalpha.factors.library import FactorLibraryManager
summary = FactorLibraryManager(r"${LIBRARY_PATH}").get_summary()
print("SUMMARY total_factors={total} active={active} degraded={degraded} stale={stale}".format(
    total=summary.get("total_factors", 0),
    active=summary.get("active_count", 0),
    degraded=summary.get("degraded_count", 0),
    stale=summary.get("stale_count", 0),
))
print("SUMMARY status_distribution={}".format(summary.get("status_distribution", {})))
PY

    if [ -n "${MAX_ITERATIONS}" ] && [ ${ITER} -ge "${MAX_ITERATIONS}" ]; then
        log "Max iterations (${MAX_ITERATIONS}) reached, stopping"
        break
    fi

    log "Sleeping ${INTERVAL_SECONDS}s before next cycle..."
    sleep "${INTERVAL_SECONDS}"
done

log "Continuous mining finished after ${ITER} iterations"
