-- Purpose: Compare source row counts and date ranges (PostgreSQL).
SELECT 'spotify' AS src, COUNT(*) AS rows, MIN(played_at_utc), MAX(played_at_utc), ROUND(SUM(ms_played) / 3600000.0, 1) AS hours
FROM staging.stg_spotify_streams
UNION ALL
SELECT 'ytm', COUNT(*) AS rows, MIN(played_at_utc), MAX(played_at_utc), NULL
FROM staging.stg_ytm_history;