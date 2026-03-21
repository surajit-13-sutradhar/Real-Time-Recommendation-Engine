from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
import time


class UserEvent(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    item_id: str = Field(..., min_length=1, max_length=128)
    event_type: Literal["click", "view", "purchase", "like"]
    timestamp: float = Field(default_factory=time.time)
    metadata: Optional[dict] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_not_future(cls, v: float) -> float:
        if v > time.time() + 5:
            raise ValueError("Timestamp cannot be in the future")
        return v


class EventResponse(BaseModel):
    status: str
    event_id: str


class BatchEventRequest(BaseModel):
    events: list[UserEvent] = Field(..., min_length=1, max_length=50)


class BatchEventResponse(BaseModel):
    accepted: list[EventResponse]
    rejected: list[dict]