import logging
import os
import re
from pathlib import Path

import app.config as config

logger = logging.getLogger("incognipwn")

HEX_LINE_RE = re.compile(r"^[0-9A-Fa-f]{35}:\d+$")


def validate_prefix(prefix: str) -> bool:
    return bool(re.fullmatch(r"[0-9A-Fa-f]{5}", prefix))


def _hash_file_path(prefix: str) -> Path:
    return Path(config.DATA_DIR) / f"{prefix.upper()}.txt"


def _parse_hash_file(content: str) -> tuple[list[str], int]:
    lines = []
    ignored = 0
    for line in content.splitlines():
        line = line.strip()
        if line and HEX_LINE_RE.match(line):
            lines.append(line.upper())
        elif line:
            ignored += 1
    if ignored > 0:
        logger.warning("Ignored %d malformed lines in hash file", ignored)
    return lines, ignored


def _generate_padding_entry() -> str:
    suffix = os.urandom(20).hex().upper()[:35]
    return f"{suffix}:0"


def lookup_range(prefix: str, with_padding: bool = False) -> tuple[list[str], bool, int]:
    if not validate_prefix(prefix):
        return [], False, 0

    path = _hash_file_path(prefix)
    if not path.exists():
        return [], False, 0

    content = path.read_text()
    results, ignored = _parse_hash_file(content)

    if with_padding:
        while len(results) < config.MIN_PADDING_RESULTS:
            results.append(_generate_padding_entry())
        if len(results) > config.MAX_PADDING_RESULTS:
            results = results[: config.MAX_PADDING_RESULTS]

    return results, True, ignored
