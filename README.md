# SIH26034 — Intelligent Legal Metrology Compliance Platform

A compliance platform for Legal Metrology: officers photograph product labels, the backend extracts
declarations (MRP, net quantity, dates, …) via OCR, checks them against Legal Metrology rules, and the
frontend reviews scans, flags, and reports.

## Prerequisites

- **Docker + Docker Compose** — any recent Docker Desktop (verified with Docker 29 / Compose v5).
- **Node.js `>=20.9.0`** (see `frontend/package.json` `engines`). Easiest with nvm:
  ```bash
  cd frontend && nvm use   # installs/uses 20.11.0 from frontend/.nvmrc
  ```
- **Python 3.11** for host-based backend dev (matches `backend/Dockerfile`'s `python:3.11-slim`).

## Quick Start (Docker — recommended)

```bash
cp .env.example .env
# Generate a real secret and paste it over the changeme-... placeholder:
openssl rand -hex 32
docker compose up --build
```

Generate a real secret with `openssl rand -hex 32` and put it in place of `changeme-...` — do not
use the same secret as teammates or in production.

Then open **http://localhost:3000** — you should see the backend status = ok.

## Local development without Docker

**Backend** (runs on the host against the Dockerized Postgres at `localhost:5432`):

```bash
cd backend
cp .env.example .env
# edit .env and set a real JWT_SECRET (see below)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Generate a real secret with `openssl rand -hex 32` and put it in place of `changeme-...` — do not
use the same secret as teammates or in production.

> Windows note: the backend needs the `libzbar` system library (barcode decoding), which isn't
> installed on Windows by default — `uvicorn` will fail at `pyzbar` import. Either use the Docker
> backend, or install zbar for Windows. The test suite mocks `pyzbar`, so `pytest` works everywhere.

**Frontend**:

```bash
cd frontend && npm install && npm run dev
```

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

## Running tests

```bash
cd backend && pytest -q        # backend suite (150 tests)
```

```bash
pytest tests -q                # image-quality tests at repo root (8 tests)
```

Frontend has no test runner yet — the checks are the type checker and linter:

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

## Project structure

```
backend/          FastAPI app (app/), migrations (alembic/), helper scripts (scripts/), pytest suite (tests/)
frontend/         Next.js app (src/)
docs/             API contract (api-contract.md)
shared/           Shared TypeScript types
tests/            Root-level image-quality tests + fixtures
```

See `docs/api-contract.md` for the full endpoint reference.

## Development: production build vs dev mode

`docker compose up` loads `docker-compose.override.yml`, which runs the frontend dev server with
hot-reload and mounts your source files into the container — edit freely, no rebuild needed.

The **production** image (`docker-compose.yml` without the override, e.g.
`docker compose -f docker-compose.yml up`) builds a **frozen image** — code changes require `--build`:

```bash
docker compose -f docker-compose.yml up --build   # rebuild after every code change
```

**Never** use the production compose without `--build` when actively editing frontend code — the
container will serve stale code from the last image build.

## Contributing

New to the workflow? See [CONTRIBUTING.md](CONTRIBUTING.md) for the step-by-step: setup, branches,
checks to run, and how to open a PR.
