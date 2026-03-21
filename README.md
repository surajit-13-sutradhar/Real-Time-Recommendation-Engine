# Project Structure
# recommendation-engine/

- **docker-compose.yml**
- **.env**
- **services/**
  - **ingest/**
    - `Dockerfile`
    - `requirements.txt`
    - `main.py`
    - `models.py`
    - `config.py`
  - **processor/**  *(Stage 3)*
  - **rec_api/**  *(Stage 4)*
- **infra/**
  - **postgres/**
    - `init.sql`
  - **monitoring/**
- **scripts/**
  - `seed_events.py`