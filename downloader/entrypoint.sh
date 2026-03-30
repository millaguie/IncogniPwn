#!/bin/bash
set -euo pipefail

HASH_OUTPUT_DIR="${HASH_OUTPUT_DIR:-/data/hashes}"
HASH_TEMP_DIR="${HASH_TEMP_DIR:-/data/hashes-new}"
PARALLELISM="${PARALLELISM:-64}"
OVERWRITE="${OVERWRITE:-true}"
SKIP_AGE_DAYS="${SKIP_AGE_DAYS:-7}"
EXPECTED_FILES=1048576
STATUS_FILE="${HASH_OUTPUT_DIR}/.update_status.json"

mkdir -p "${HASH_OUTPUT_DIR}" "${HASH_TEMP_DIR}"

write_status() {
    local success="$1"
    local duration="$2"
    local file_count="$3"
    local now
    now=$(date +%s)
    cat > "${STATUS_FILE}" <<EOF
{"timestamp": ${now}, "success": ${success}, "duration_seconds": ${duration}, "file_count": ${file_count}, "expected_files": ${EXPECTED_FILES}}
EOF
}

START_TIME=$(date +%s)

sync_temp_to_output() {
    local file_count
    file_count=$(find "${HASH_TEMP_DIR}" -name "*.txt" | wc -l)
    echo "[$(date -Iseconds)] Found ${file_count} files in ${HASH_TEMP_DIR}"

    if [ "${file_count}" -lt "${EXPECTED_FILES}" ]; then
        END_TIME=$(date +%s)
        write_status 0 $((END_TIME - START_TIME)) "${file_count}"
        echo "[ERROR] Expected ${EXPECTED_FILES} files, got ${file_count}. Aborting."
        exit 1
    fi

    echo "[$(date -Iseconds)] Syncing ${HASH_TEMP_DIR}/ -> ${HASH_OUTPUT_DIR}/"
    rsync -a --remove-source-files "${HASH_TEMP_DIR}/" "${HASH_OUTPUT_DIR}/"
    find "${HASH_TEMP_DIR}" -mindepth 1 -type d -empty -delete
    echo "[$(date -Iseconds)] Sync complete"
}

OUTPUT_MARKER="${HASH_OUTPUT_DIR}/.last_sync"
if [ -f "${OUTPUT_MARKER}" ]; then
    LAST_SYNC=$(date -d "$(cat "${OUTPUT_MARKER}")" +%s 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE_DAYS=$(( (NOW - LAST_SYNC) / 86400 ))
    if [ "${AGE_DAYS}" -lt "${SKIP_AGE_DAYS}" ]; then
        echo "[$(date -Iseconds)] Output data is ${AGE_DAYS} days old (threshold: ${SKIP_AGE_DAYS}). Skipping."
        exit 0
    fi
fi

TEMP_FILES=$(find "${HASH_TEMP_DIR}" -name "*.txt" 2>/dev/null | wc -l)
if [ "${TEMP_FILES}" -ge "${EXPECTED_FILES}" ]; then
    echo "[$(date -Iseconds)] Found ${TEMP_FILES} files in temp dir. Syncing."
    sync_temp_to_output
    END_TIME=$(date +%s)
    date -Iseconds > "${OUTPUT_MARKER}"
    OUTPUT_FILES=$(find "${HASH_OUTPUT_DIR}" -name "*.txt" 2>/dev/null | wc -l)
    write_status 1 $((END_TIME - START_TIME)) "${OUTPUT_FILES}"
    exit 0
fi

OUTPUT_FILES=$(find "${HASH_OUTPUT_DIR}" -name "*.txt" 2>/dev/null | wc -l)

OVERWRITE_FLAG=""
if [ "${OVERWRITE}" = "true" ]; then
    OVERWRITE_FLAG="-o"
fi

if [ "${OUTPUT_FILES}" -ge "${EXPECTED_FILES}" ]; then
    echo "[$(date -Iseconds)] Updating existing files in ${HASH_OUTPUT_DIR}"
    haveibeenpwned-downloader "${HASH_OUTPUT_DIR}" -s false -p "${PARALLELISM}" ${OVERWRITE_FLAG}
    END_TIME=$(date +%s)
    date -Iseconds > "${OUTPUT_MARKER}"
    OUTPUT_FILES=$(find "${HASH_OUTPUT_DIR}" -name "*.txt" 2>/dev/null | wc -l)
    write_status 1 $((END_TIME - START_TIME)) "${OUTPUT_FILES}"
    echo "[$(date -Iseconds)] Update complete"
else
    echo "[$(date -Iseconds)] Initial download to ${HASH_TEMP_DIR}"
    haveibeenpwned-downloader "${HASH_TEMP_DIR}" -s false -p "${PARALLELISM}" ${OVERWRITE_FLAG}
    sync_temp_to_output
    END_TIME=$(date +%s)
    date -Iseconds > "${OUTPUT_MARKER}"
    OUTPUT_FILES=$(find "${HASH_OUTPUT_DIR}" -name "*.txt" 2>/dev/null | wc -l)
    write_status 1 $((END_TIME - START_TIME)) "${OUTPUT_FILES}"
    echo "[$(date -Iseconds)] Initial download complete. Files synced to ${HASH_OUTPUT_DIR}"
fi
