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

**For active frontend development**, use `docker compose watch` which auto-rebuilds on file changes:

```bash
docker compose watch
```

This runs Next.js dev server with hot-reload and mounts your source files directly into the container.

**For backend development**, run directly on host (no Docker):

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

**For local frontend development** (without Docker):

```bash
cd frontend && npm install && npm run dev
```

## Important: Production Build vs Dev Mode

- `docker compose up` builds a **frozen production image** — code changes require `--build`:
  ```bash
  docker compose up --build   # rebuild after every code change
  ```

- `docker compose watch` runs **dev mode** with hot-reload — no rebuild needed for frontend changes.

- **Never** use `docker compose up` (without `--build`) when actively editing frontend code — the container will serve stale code from the last image build.
