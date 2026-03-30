import json
import logging
import time
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram

import app.config as config

logger = logging.getLogger("incognipwn")

REQUEST_COUNT = Counter(
    "incognipwn_range_requests_total",
    "Total /range requests",
    labelnames=["status"],
)

REQUEST_DURATION = Histogram(
    "incognipwn_range_request_duration_seconds",
    "Request duration for /range endpoint",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

PREFIX_NOT_FOUND = Counter(
    "incognipwn_prefix_not_found_total",
    "Prefix not found in dataset",
)

PREFIX_INVALID = Counter(
    "incognipwn_prefix_invalid_total",
    "Invalid prefix format",
)

PADDING_REQUESTS = Counter(
    "incognipwn_padding_requests_total",
    "Requests with Add-Padding header",
)

MALFORMED_LINES = Counter(
    "incognipwn_malformed_lines_total",
    "Malformed lines skipped during hash file parsing",
)

RESPONSE_SIZE = Gauge(
    "incognipwn_response_size_bytes",
    "Response size in bytes",
)

ACTIVE_DATA = Gauge(
    "incognipwn_active_hash_files",
    "Number of hash files in data directory",
)

LAST_UPDATE_TIMESTAMP = Gauge(
    "incognipwn_last_update_timestamp_seconds",
    "Unix timestamp of last successful dataset update",
)

LAST_UPDATE_SUCCESS = Gauge(
    "incognipwn_last_update_success",
    "1 if last update succeeded, 0 if failed",
)

LAST_UPDATE_DURATION = Gauge(
    "incognipwn_last_update_duration_seconds",
    "Duration of last download in seconds",
)

DATASET_AGE = Gauge(
    "incognipwn_dataset_age_seconds",
    "Seconds since last dataset update",
)

EXPECTED_FILES = Gauge(
    "incognipwn_hash_files_expected_total",
    "Expected number of hash files",
)


def update_dataset_metrics() -> None:
    status_path = Path(config.DATA_DIR) / ".update_status.json"

    if status_path.exists():
        try:
            data = json.loads(status_path.read_text())
            ACTIVE_DATA.set(data.get("file_count", 0))
            EXPECTED_FILES.set(data.get("expected_files", 0))
            LAST_UPDATE_DURATION.set(data.get("duration_seconds", 0))
            LAST_UPDATE_SUCCESS.set(1 if data.get("success") else 0)

            ts = data.get("timestamp", 0)
            LAST_UPDATE_TIMESTAMP.set(ts)
            DATASET_AGE.set(time.time() - ts if ts > 0 else 0)

            logger.debug(
                "Dataset metrics updated: %d files, age %.0fs",
                data.get("file_count", 0),
                time.time() - ts if ts > 0 else 0,
            )
            return
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.exception("Failed to parse %s", status_path)

    data_path = Path(config.DATA_DIR)
    if data_path.exists():
        count = len(list(data_path.glob("*.txt")))
        ACTIVE_DATA.set(count)
        logger.debug("Active hash files (fallback count): %d", count)
