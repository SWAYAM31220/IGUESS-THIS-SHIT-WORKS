# govd (Python port)

This is a Python **deploy-ready** port of the Go project you uploaded (**govd**), keeping the same core logic:

- Telegram bot that accepts supported links and downloads media
- Settings stored per-chat in Postgres (`/settings` + inline buttons)
- Extractor list + per-chat disabling
- Error logging (`/derr <id>` for admins)
- Basic stats (`/stats` for admins)
- Optional Prometheus metrics endpoint (`METRICS_PORT`)

> Implementation note: instead of Go extractors, this port uses **yt-dlp** (with ffmpeg) which supports all the same target platforms and handles most edge cases in a single, reliable downloader.

## Quick start (Docker)

1) Copy env:

```bash
cp .env.example .env
```

2) Put your bot token in `.env`.

3) Run:

```bash
docker compose up --build
```

The bot will start polling.

## Local run (no Docker)

Requires `ffmpeg` + Postgres.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Settings

- `/settings` opens an interactive settings panel.
- Captions, silent mode, nsfw, delete-links, language, media-album limit, and disabling extractors are supported.

## Database

Migrations are auto-applied at startup from `migrations/*.sql` (ported directly from the Go repo).

