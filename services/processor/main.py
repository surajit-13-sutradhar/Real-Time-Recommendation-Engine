import asyncio
import logging
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from consumer import EventProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

processor = EventProcessor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start consumer in background task
    task = asyncio.create_task(run_processor())
    logger.info("Processor service started")
    yield
    task.cancel()
    await processor.stop()
    logger.info("Processor service stopped")


async def run_processor():
    await processor.start()
    await processor.run()


app = FastAPI(title="Event Processor", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    return processor.aggregator.get_stats()


@app.get("/recommendations/{user_id}")
async def recommendations(user_id: str, n: int = 10):
    items = processor.aggregator.get_top_items(user_id, n=n)
    return {
        "user_id": user_id,
        "recommendations": [
            {"item_id": item.item_id, "score": item.score, "event_count": item.event_count}
            for item in items
        ],
    }
