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
| Event Streaming | Apache Kafka |
| Primary Storage | PostgreSQL |
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
# From the project root
docker compose up --build

# Test (Windows)
curl.exe http://localhost:8000/health
curl.exe -X POST http://localhost:8000/events -H "Content-Type: application/json" -d "{\"user_id\": \"u1\", \"item_id\": \"i1\", \"event_type\": \"click\"}"

# Interactive API docs
http://localhost:8000/docs
```

---

## Stages Ahead

| Stage | Name | Status |
|---|---|---|
| 1 | Foundation & Event Ingest API | ✅ Complete |
| 2 | Kafka Integration | 🔲 Next |
| 3 | Event Processing Service | 🔲 Pending |
| 4 | Postgres Schema & Persistence | 🔲 Pending |
| 5 | Redis Caching Layer | 🔲 Pending |
| 6 | Recommendation API | 🔲 Pending |
| 7 | Docker Compose — Full Stack | 🔲 Pending |
| 8 | AWS Deployment | 🔲 Pending |
| 9 | Logging & Monitoring | 🔲 Pending |
| 10 | Resilience & Production Hardening | 🔲 Pending |

---

*This document is updated at the end of each stage.*