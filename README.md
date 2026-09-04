# SIH26034 — Intelligent Legal Metrology Compliance Platform

## Quick Start

```bash
cp .env.example .env
docker compose up
```

Then open **http://localhost:3000** — you should see the backend status = ok.

## Services

| Service  | URL                 |
|----------|---------------------|
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:8000 |
| Postgres | localhost:5432       |

## Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"sih26034-backend"}
```

## Development

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```
