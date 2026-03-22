# Recommendation Engine — Build Progress

A production-grade backend system that processes user events at scale and serves real-time personalized recommendations.

---

## System Overview

```
Clients → FastAPI (Ingest) → Kafka → Processor → Postgres
                                                     ↕
Clients ← FastAPI (Rec API) ←———————————————— Redis Cache
```

Users generate events (clicks, views, purchases) → streamed through Kafka → aggregated and ranked by a processing service → stored in Postgres → cached in Redis → served back via a recommendation API. All services run in Docker containers, deployed on AWS.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| API Framework | FastAPI + Uvicorn |
| Event Streaming | Apache Kafka (KRaft mode) |
| Primary Storage | PostgreSQL (Docker service) |
| Cache | Redis |
| Containerisation | Docker + Docker Compose |
| Cloud | AWS (EC2, S3) |
| Validation | Pydantic V2 |

---

## Stage 1 — Foundation & Event Ingest API ✅

### What was built

A containerised FastAPI service that acts as the front door for all user events. It validates, logs, and accepts events before passing them downstream.

### Files created

```
recommendation-engine/
├── docker-compose.yml
├── services/
│   ├── ingest/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── models.py
│   ├── processor/
│   └── rec_api/
├── infra/
│   └── postgres/
└── scripts/
```

### API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/events` | Ingest a single user event |
| `POST` | `/events/batch` | Ingest up to 50 events at once |

### Event schema

```json
{
  "user_id": "u123",
  "item_id": "i456",
  "event_type": "click | view | purchase | like",
  "timestamp": 1711234567.0,
  "metadata": {}
}
```

### Key decisions

**Pydantic V2 validation** — all incoming events are validated at the boundary before they touch any downstream system. Bad data is rejected with a `422` response before it can pollute the pipeline.

**Partial batch acceptance** — in `/events/batch`, valid events are accepted and invalid ones are collected into a `rejected` list with their index and reason. One bad event in a batch of 50 does not discard the other 49.

**HTTP 202 Accepted** — both event endpoints return `202` not `200`. The event is queued for processing, not immediately persisted. `202` correctly signals a promise, not a confirmation.

**Non-root Docker user** — the container runs as a dedicated `appuser`, not root. A container escape does not give an attacker root on the host.

**Structured logging** — log lines use `key=value` pairs, making them grep-able and compatible with CloudWatch and Datadog without extra parsing config.

### How to run

```bash
docker compose up --build

# Test (Windows)
curl.exe http://localhost:8000/health
curl.exe -X POST http://localhost:8000/events -H "Content-Type: application/json" -d "{\"user_id\": \"u1\", \"item_id\": \"i1\", \"event_type\": \"click\"}"

# Interactive API docs
http://localhost:8000/docs
```

---

## Stage 2 — Kafka Integration ✅

### What was built

Wired Apache Kafka (KRaft mode — no ZooKeeper) into the ingest service. Every accepted event is now published to the `user-events` Kafka topic. The ingest API and the processing layer are fully decoupled.

### Files created / updated

```
recommendation-engine/
├── docker-compose.yml          ← added Kafka (KRaft), updated ingest config
└── services/
    └── ingest/
        ├── requirements.txt    ← added aiokafka
        ├── main.py             ← publishes events to Kafka on ingest
        └── kafka_producer.py   ← new: async Kafka producer wrapper
```

### Key decisions

**KRaft mode instead of ZooKeeper** — as of Kafka 4.0, KRaft is mandatory. Removes the need for a separate ZooKeeper container, simplifies operations, and improves scalability.

**`key=user_id` partitioning** — events for the same user always land on the same partition, guaranteeing ordered processing per user.

**`acks="all"` + `enable_idempotence=True`** — no message loss on broker crash, no duplicate messages on retry.

**Graceful degradation** — if Kafka is unavailable, the ingest API still returns `202` and logs a warning instead of crashing. Events are not silently dropped from the client's perspective.

**Two listeners** — `kafka:29092` for internal Docker network traffic, `localhost:9092` for external access from the host machine.

### How Kafka fits in

```
Without Kafka:                    With Kafka:

Client → API → Postgres           Client → API → Kafka → Processor → Postgres

Problems:                         Benefits:
- API blocks on DB write          - API returns in <5ms always
- DB is the bottleneck            - Events buffered if processor is slow
- Processor crash = data loss     - Replay events from any point in time
- Tight coupling                  - Add consumers without changing the API
```

### Verify

```powershell
docker compose exec kafka kafka-console-consumer `
  --bootstrap-server localhost:9092 `
  --topic user-events `
  --from-beginning `
  --property print.partition=true
```

---

## Stage 3 — Event Processing Service ✅

### What was built

A standalone Kafka consumer service that reads from `user-events`, aggregates event scores per user, and exposes recommendation and stats endpoints. This is the brain of the system.

### Files created / updated

```
recommendation-engine/
├── docker-compose.yml          ← added processor service
└── services/
    └── processor/
        ├── Dockerfile
        ├── requirements.txt
        ├── main.py             ← FastAPI app + lifespan consumer task
        ├── consumer.py         ← Kafka consumer loop
        ├── aggregator.py       ← scoring logic
        └── config.py           ← env-based config
```

### API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/stats` | Total events processed, users, pairs |
| `GET` | `/recommendations/{user_id}` | Top-N items for a user |

### Scoring algorithm

| Event type | Weight |
|---|---|
| `view` | 0.5 |
| `click` | 1.0 |
| `like` | 2.0 |
| `purchase` | 5.0 |

Score per item = sum of weights across all events for that user-item pair. Top items by score become recommendations.

### Key decisions

**Separate consumer service** — the processor runs independently from the ingest API. If it slows down or restarts, Kafka buffers events. The ingest API is never affected.

**Consumer group** — `processor-group` tracks offsets per partition. Multiple processor instances can run in parallel, each handling different partitions.

**Don't re-raise on message error** — if one message fails to process, log it and continue. A single bad message should never halt the entire consumer loop.

**Background task via `asyncio.create_task`** — the Kafka consumer loop runs as a background task inside the FastAPI lifespan, keeping the HTTP server responsive for health and stats endpoints.

### Known limitation (fixed in Stage 4)

State is in-memory only. Restarting the processor wipes all scores because Python dicts live in RAM. Postgres persistence is added in Stage 4 to survive restarts.

```
On restart without Postgres:    On restart with Postgres (Stage 4):
scores = {}  ← empty            scores loaded from DB ← preserved
```

### Verify

```powershell
curl.exe http://localhost:8001/recommendations/u1
curl.exe http://localhost:8001/stats
```

---

## Stages Ahead

| Stage | Name | Status |
|---|---|---|
| 1 | Foundation & Event Ingest API | ✅ Complete |
| 2 | Kafka Integration | ✅ Complete |
| 3 | Event Processing Service | ✅ Complete |
| 4 | Postgres Schema & Persistence | 🔲 Next |
| 5 | Redis Caching Layer | 🔲 Pending |
| 6 | Recommendation API | 🔲 Pending |
| 7 | Docker Compose — Full Stack | 🔲 Pending |
| 8 | AWS Deployment | 🔲 Pending |
| 9 | Logging & Monitoring | 🔲 Pending |
| 10 | Resilience & Production Hardening | 🔲 Pending |

---

*This document is updated at the end of each stage.*