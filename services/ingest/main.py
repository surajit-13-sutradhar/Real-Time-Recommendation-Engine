import uuid
import logging
import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from models import UserEvent, EventResponse, BatchEventRequest, BatchEventResponse
from kafka_producer import start_producer, stop_producer, publish_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "user-events")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_producer(KAFKA_BOOTSTRAP_SERVERS)
    logger.info("Ingest service ready")
    yield
    await stop_producer()
    logger.info("Ingest service shut down")


app = FastAPI(title="Event Ingest API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/events", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: UserEvent):
    event_id = str(uuid.uuid4())
    payload = {**event.model_dump(), "event_id": event_id}

    published = await publish_event(
        topic=KAFKA_TOPIC,
        event=payload,
        key=event.user_id,   # same user always goes to same partition
    )

    if not published:
        logger.warning("kafka_unavailable event_id=%s falling back to log only", event_id)

    logger.info("event_received user_id=%s event_id=%s published=%s",
                event.user_id, event_id, published)

    return EventResponse(status="accepted", event_id=event_id)


@app.post("/events/batch", response_model=BatchEventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(batch: BatchEventRequest):
    accepted = []
    rejected = []

    for i, event in enumerate(batch.events):
        try:
            event_id = str(uuid.uuid4())
            payload = {**event.model_dump(), "event_id": event_id}
            await publish_event(topic=KAFKA_TOPIC, event=payload, key=event.user_id)
            accepted.append(EventResponse(status="accepted", event_id=event_id))
        except Exception as e:
            logger.warning("batch_event_rejected index=%d reason=%s", i, str(e))
            rejected.append({"index": i, "reason": str(e)})

    return BatchEventResponse(accepted=accepted, rejected=rejected)


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )