import logging
import time
from pathlib import Path

from fastapi import APIRouter, Header, Response
from fastapi.responses import JSONResponse

import app.config as config
from app.services.hash_lookup import lookup_range, validate_prefix
from app.services.metrics import (
    MALFORMED_LINES,
    PADDING_REQUESTS,
    PREFIX_INVALID,
    PREFIX_NOT_FOUND,
    REQUEST_COUNT,
    REQUEST_DURATION,
    RESPONSE_SIZE,
)

logger = logging.getLogger("incognipwn")

router = APIRouter()


@router.get("/range/{prefix}")
async def get_range(
    prefix: str,
    add_padding: str | None = Header(None, alias="Add-Padding"),
) -> Response:
    start = time.perf_counter()
    with_padding = add_padding is not None and add_padding.lower() == "true"

    if not validate_prefix(prefix):
        PREFIX_INVALID.inc()
        REQUEST_COUNT.labels(status="400").inc()
        return Response(
            content=f'The hash prefix "{prefix}" is not valid. Must be exactly 5 hex characters.\n',
            status_code=400,
            media_type="text/plain",
        )

    if with_padding:
        PADDING_REQUESTS.inc()

    results, found, ignored = lookup_range(prefix, with_padding=with_padding)

    if ignored > 0:
        MALFORMED_LINES.inc(ignored)

    duration = time.perf_counter() - start
    REQUEST_DURATION.observe(duration)

    if not found:
        PREFIX_NOT_FOUND.inc()
        REQUEST_COUNT.labels(status="404").inc()
        return Response(
            content=f'The hash prefix "{prefix}" was not found in the data set.\n',
            status_code=404,
            media_type="text/plain",
        )

    body = "\n".join(results) + "\n" if results else ""
    RESPONSE_SIZE.set(len(body.encode()))
    REQUEST_COUNT.labels(status="200").inc()
    logger.debug("range %s: %d results in %.3fs", prefix, len(results), duration)
    return Response(
        content=body,
        status_code=200,
        media_type="text/plain",
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> Response:
    data_path = Path(config.DATA_DIR)
    if data_path.exists() and any(data_path.glob("*.txt")):
        return JSONResponse(content={"status": "ready"})

    logger.warning("Readiness check failed: no hash data found")
    return JSONResponse(
        status_code=503,
        content={"status": "not ready", "reason": "no hash data found"},
    )
