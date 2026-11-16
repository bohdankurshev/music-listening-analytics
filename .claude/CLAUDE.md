# Music Listening Analytics
Portfolio project: end-to-end analysis of my own music listening (Spotify + YouTube Music), from raw exports to a Power BI dashboard.

## Questions the project answers
1. Skips: which tracks I skip and why (time of day, platform, shuffle, reason_end).
2. Discovery vs comfort: artist cohorts by first-listen month and their retention.
3. Ukrainization: share of Ukrainian artists over time, before/after 24 Feb 2022.
4. Platform switch: Spotify -> YouTube Music, and whether my listening changed.

## Data sources
- Spotify Account data: StreamingHistory*.json, last 12 months (end time, artist, track, ms played).
- Spotify Extended streaming history: full history (ts, ms_played, track/artist/album names, spotify_track_uri, reason_start, reason_end, shuffle, skipped, platform).
- YouTube Music: Google Takeout watch history JSON (time, title, artist). No duration, no skip flag.
- MusicBrainz API: artist country for enrichment. Max 1 request per second, always send a User-Agent.
- Until the real exports arrive, use synthetic data in data/sample/ that mimics the real formats.

## Architecture
raw JSON (data/raw) -> Python in src/ (extract, validate) -> PostgreSQL database `music_analytics`:
schema `staging` (raw-shaped, one table per source) -> schema `core` (star schema) -> views -> Power BI in reports/ (saved as PBIP).
Core model: fact_streams + dim_track, dim_artist, dim_date, dim_time, dim_platform.

## Privacy (hard rules)
- Drop ip_addr, user_agent and username fields before loading anything into staging.
- Never commit raw exports, .env, or the Power BI data cache. Only synthetic samples, code, SQL and aggregated results go to GitHub.

## Conventions
- Timestamps: store UTC as timestamptz; convert to Europe/Kyiv only in views.
- Naming: snake_case; `stg_*` tables in staging, `fact_*` / `dim_*` in core.
- SQL files: sql/ddl (structure), sql/dml (loads and transforms), sql/analysis (questions). Numbered: 001_create_schemas.sql.
- Dedup key for streams: (played_at_utc, track name, artist name, source).
- Python: virtual env in .venv, dependencies in requirements.txt, config from .env (see .env.example).

## Commands
- Create venv: `python -m venv .venv`
- Activate venv: `.venv\Scripts\Activate.ps1`
- Install dependencies: `pip install -r requirements.txt`
