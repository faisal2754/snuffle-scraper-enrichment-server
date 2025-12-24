from dotenv import load_dotenv
load_dotenv()  # Load .env before any other imports that read env vars

import sys
import os
import logging
from contextlib import asynccontextmanager

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI
import uvicorn

from .routes import router

# Configure Azure Monitor if connection string is available
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(console_handler)

    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry.instrumentation.requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    logger.info("Scraper API startup complete.")
    yield
    logger.info("Scraper API shutdown complete.")


app = FastAPI(
    title="Scraper API",
    description="API for scraping HR contacts and executives from companies",
    lifespan=lifespan,
)
FastAPIInstrumentor.instrument_app(app)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)

