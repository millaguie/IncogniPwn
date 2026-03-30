import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import METRICS_REFRESH_INTERVAL
from app.routes.range import router as range_router
from app.services.metrics import update_dataset_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("incognipwn")


async def _metrics_loop() -> None:
    while True:
        try:
            update_dataset_metrics()
        except Exception:
            logger.exception("Failed to update dataset metrics")
        await asyncio.sleep(METRICS_REFRESH_INTERVAL)


@asynccontextmanager
async def lifespan(application: FastAPI):
    update_dataset_metrics()
    task = asyncio.create_task(_metrics_loop())
    yield
    task.cancel()


app = FastAPI(
    title="IncogniPwn",
    description="Privacy-preserving self-hosted HIBP Pwned Passwords k-anonymity API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(range_router)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
