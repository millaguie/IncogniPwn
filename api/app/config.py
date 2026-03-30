import os

DATA_DIR: str = os.getenv("DATA_DIR", "/data/hashes")
MIN_PADDING_RESULTS: int = int(os.getenv("MIN_PADDING_RESULTS", "800"))
MAX_PADDING_RESULTS: int = int(os.getenv("MAX_PADDING_RESULTS", "1000"))
METRICS_REFRESH_INTERVAL: int = int(os.getenv("METRICS_REFRESH_INTERVAL", "30"))
