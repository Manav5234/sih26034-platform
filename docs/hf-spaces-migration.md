# HF Spaces migration (trial)

Branch: `manav/hf-spaces-migration` — deployment/config plumbing only. No pipeline,
extraction, OCR, fusion, or rule-engine logic changed.

## Why

The Render free tier (512MB RAM) runs the backend out of memory during scans: RapidOCR /
onnxruntime load several models per process and peak well past 512MB once a scan is in
flight. Hugging Face Spaces' free `cpu-basic` hardware gives 16GB RAM, which is enough
headroom to prove the backend works under real scan load before deciding anything about
production.

## What changed

| File | Change |
| --- | --- |
| `backend/Dockerfile` | `CMD` now runs uvicorn on `${PORT:-7860}` instead of hardcoded `8000`, so the app binds the port HF Spaces (or Render) injects via `PORT`. |
| `backend/app/config.py` | Default `ALLOWED_ORIGINS` now also contains `https://REPLACE-WITH-HF-SPACE-URL.hf.space`. Existing origins are untouched — production origins live in Render's `ALLOWED_ORIGINS` env var, not in git. |
| `docker-compose.yml` | Backend service pins `PORT: 8000` so local `docker compose up` keeps serving on 8000 after the Dockerfile change. |

## Manual steps (can't be done from the CLI)

1. **Create the Space**: on <https://huggingface.co> → New Space → SDK **Docker**,
   hardware **cpu-basic**, then connect the repo (or push the `backend/` Dockerfile
   context) so Spaces builds the image.
2. **Set secrets/vars** in the Space's *Settings → Variables and secrets*:
   `DATABASE_URL`, `JWT_SECRET`, and any others you normally keep in `.env`
   (see `backend/.env.example`).
   - CORS note: if you also set `ALLOWED_ORIGINS` as a Space variable, the code default
     is overridden — include
     `https://REPLACE-WITH-HF-SPACE-URL.hf.space` in it, or omit the variable entirely
     and rely on the default in `config.py`.
3. **Fill in the real Space URL**: replace `REPLACE-WITH-HF-SPACE-URL` in
   `backend/app/config.py` with the actual Space hostname (and the matching value in the
   `ALLOWED_ORIGINS` variable if you set one).
4. **Vercel preview**: set the API base URL env var for the preview deployment to
   `https://<your-space>.hf.space` so a preview build talks to the new backend instead
   of Render.

## Rollback

If the trial doesn't work out: delete this branch and delete the Hugging Face Space.
`main` and the Render/Vercel production deployment were never touched — production
continues to run exactly as it does today.

## Render note

`main`'s Dockerfile hardcodes port 8000. After this merges, Render must supply
`PORT=8000` (or already inject `PORT` matching its configured port) or the service
will fall back to 7860. Check Render's environment variables before merging.
