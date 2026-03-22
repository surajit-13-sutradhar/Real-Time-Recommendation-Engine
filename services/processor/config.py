import os

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "user-events")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "processor-group")
KAFKA_AUTO_OFFSET_RESET = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")

# Scoring weights per event type
EVENT_WEIGHTS: dict[str, float] = {
    "click": 1.0,
    "view": 0.5,
    "like": 2.0,
    "purchase": 5.0,
}

# How many top items to track per user
TOP_N = int(os.getenv("TOP_N", "20"))