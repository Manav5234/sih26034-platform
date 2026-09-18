# Contributing to SIH26034

Step-by-step for opening a pull request, assuming you have never done one before.

## 1. One-time setup

This guide assumes you already have the code cloned (see the README's "Getting the code" section
for the clone-vs-fork decision) and are pushing directly to branches on this repo. If you're
working from a fork instead, push to your fork's `origin` and open the PR from there against this
repo's `main` — GitHub's "Compare & pull request" banner handles this automatically either way.

1. Clone the repo and follow the [README](README.md) to install everything.
2. Confirm the app works **before touching any code**:
   ```bash
   cp .env.example .env
   # put a real `openssl rand -hex 32` secret in JWT_SECRET
   docker compose up --build
   ```
   Open http://localhost:3000 (backend status = ok) and run
   `curl http://localhost:8000/health` (expect `{"status":"ok",...}`).
   If this doesn't work, fix your setup first — don't start changing code yet.

## 2. Before you start changing anything

```bash
git checkout main
git pull origin main
git checkout -b your-name/short-description-of-change
```

Branch naming isn't strictly enforced, but keep it descriptive: who you are and what the change
is, e.g. `priya/fix-mrp-decimal-parse`.

## 3. While working

Run the backend/frontend in dev mode as described in the [README](README.md) (don't duplicate
that setup here — just follow it).

Before committing **backend** changes:

```bash
cd backend && pytest -q && ruff check app
```

Before committing **frontend** changes:

```bash
cd frontend && npm run lint && npx tsc --noEmit
```

All four commands must pass. If `pytest` fails on a test you didn't touch, tell the team instead
of working around it.

## 4. Committing

```bash
git add <files>
git commit -m "short, clear description of what changed and why"
```

Stage only the files you actually changed — check with `git status` first.

## 5. Pushing and opening the PR

```bash
git push origin your-name/short-description-of-change
```

Then go to the repo on GitHub — you'll see a yellow banner inviting you to **Compare & pull
request**. Click it, write a short description of what changed and why, and open the PR against
`main`.

## 6. After opening a PR

- Someone will review it. CI/tests should pass if any exist.
- Address review comments by pushing more commits to the **same branch** — they show up on the
  same PR automatically. Don't open a second PR for fixes.
- After approval, the PR gets merged into `main`. Then update your local copy:
  `git checkout main && git pull origin main`.

## 7. Don'ts (lessons from real incidents on this project)

- **Don't commit `.env` files.** They're already gitignored — keep it that way. Only
  `.env.example` files belong in git. If you accidentally stage one, `git reset HEAD <file>`.
- **Don't report a task as done without confirming your commits are visible on
  `github.com/<org>/<repo>/commits/main` after pushing.** Local commits that are never pushed
  have caused real confusion on this project already. Run
  `git fetch origin && git log origin/main --oneline -5` and check your commit is listed.
- **Don't assume `docker compose up` picks up your code changes automatically.** The production
  image is frozen — rebuild with `--build` (plain `docker compose up` uses the dev override with
  hot-reload, so prefer that while iterating on the frontend).
