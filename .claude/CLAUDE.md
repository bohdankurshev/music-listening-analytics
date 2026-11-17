# Music Listening Analytics
Portfolio project: end-to-end analysis of my own music listening (Spotify + YouTube Music), from raw exports to a Power BI dashboard.

## Questions the project answers
1. Skips: which tracks I skip and why (time of day, platform, shuffle, reason_end).
2. Discovery vs comfort: artist cohorts by first-listen month and their retention.
3. Ukrainization: share of Ukrainian artists over time, as a trend from 2022 to 2026 (Spotify history starts in May 2022, so there is no "before 24 Feb 2022" baseline).
4. Platform switch: Spotify -> YouTube Music, and whether my listening changed.

## Data sources
Raw files are personal data: git-ignored, never print raw rows. Full model: docs/data_model.md.

**Spotify Extended streaming history**: `data/raw/spotify_extended/Streaming_History_Audio_*.json` (5 files, 2022-2026). Ignore `Streaming_History_Video_*.json` and the PDF.
- 25,420 music rows + 10 podcast rows. Range 2022-05-30 .. 2026-11-14.
- Keys: ts, platform, ms_played, conn_country, ip_addr, master_metadata_track_name, master_metadata_album_artist_name, master_metadata_album_album_name, spotify_track_uri, episode_name, episode_show_name, spotify_episode_uri, audiobook_title, audiobook_uri, audiobook_chapter_uri, audiobook_chapter_title, reason_start, reason_end, shuffle, skipped, offline, offline_timestamp, incognito_mode.
- No username or user_agent field; the IP field is `ip_addr`.
- `ts` = END of playback, UTC. Start = ts - ms_played.
- `platform` is the DEVICE, not the service: android, windows, "Android OS 12 API 31 (OnePlus, LE2123)", "web_player windows 10;chrome ...", unknown.
- 444 rows with ms_played = 0; 3 duplicates on (ts, spotify_track_uri) that differ in ms_played.
- offline_timestamp mixes milliseconds and seconds (dropped). conn_country is always UA, incognito_mode always False (dropped).

**YouTube Music**: `data/raw/youtube_takeout/історія переглядів.json` (Google Takeout watch history, 120k records, Ukrainian-localized). Ignore `історія пошуку.json`.
- 1,679 YouTube Music records: header == "YouTube Музика" (titleUrl host music.youtube.com), mostly Jul-Oct 2026. All other records (header "YouTube") are regular YouTube and are excluded.
- title = `Ви дивилися <track title>`, titleUrl = `https://music.youtube.com/watch?v=<video_id>`, time = START of playback, UTC (ISO 8601).
- subtitles[0].name = channel name, usually `<Artist> - Topic`. 14 records have no subtitles (removed videos).
- No duration, skip, shuffle or album.

**MusicBrainz API**: artist country (and later genre tags) for enrichment. Max 1 request per second, always send a User-Agent.

**Synthetic sample**: `data/sample/` holds 20 fake rows per staging CSV (from src/make_sample.py) for the public repo.

## Architecture
raw JSON (data/raw) -> Python in src/ (extract, validate) -> PostgreSQL database `music_analytics`:
schema `staging` (raw-shaped, one table per source) -> schema `core` (star schema) -> views -> Power BI in reports/ (saved as PBIP).
Staging CSVs: src/extract_spotify.py -> data/processed/stg_spotify_streams.csv, src/extract_ytm.py -> data/processed/stg_ytm_history.csv.
Core model: fact_streams + dim_service (Spotify / YouTube Music), dim_device (Android, Windows, Web Player, Unknown), dim_track, dim_artist, dim_date, dim_time.

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
- Build staging CSVs: `python src/extract_spotify.py`, `python src/extract_ytm.py`
- Rebuild synthetic sample: `python src/make_sample.py`
