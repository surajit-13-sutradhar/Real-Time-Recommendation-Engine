import uuid
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from models import UserEvent, EventResponse, BatchEventRequest, BatchEventResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ingest service starting up")
    yield
    logger.info("Ingest service shutting down")


app = FastAPI(title="Event Ingest API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/events", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: UserEvent):
    event_id = str(uuid.uuid4())
    logger.info("event_received user_id=%s item_id=%s type=%s event_id=%s",
                event.user_id, event.item_id, event.event_type, event_id)
    # Kafka publish goes here in Stage 2
    return EventResponse(status="accepted", event_id=event_id)


@app.post("/events/batch", response_model=BatchEventResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(batch: BatchEventRequest):
    accepted = []
    rejected = []

    for i, event in enumerate(batch.events):
        try:
            event_id = str(uuid.uuid4())
            logger.info("batch_event_received index=%d user_id=%s event_id=%s",
                        i, event.user_id, event_id)
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