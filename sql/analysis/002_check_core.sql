-- Purpose: validate core load against staging
SELECT 'spotify' as src,
        (SELECT COUNT(*) FROM staging.stg_spotify_streams) AS staging_rows,
        (SELECT COUNT(*) FROM core.fact_streams WHERE service_key = 1) AS fact_rows
UNION ALL
SELECT 'youtube_music' as src,
        (SELECT COUNT(*) FROM staging.stg_ytm_history) AS staging_rows,
        (SELECT COUNT(*) FROM core.fact_streams WHERE service_key = 2) AS fact_rows;



-- Check 2: dimension sizes
SELECT 'dim_service' AS tbl, COUNT(*) AS row_count FROM core.dim_service
UNION ALL SELECT 'dim_device', COUNT(*) FROM core.dim_device
UNION ALL SELECT 'dim_time',   COUNT(*) FROM core.dim_time
UNION ALL SELECT 'dim_date',   COUNT(*) FROM core.dim_date
UNION ALL SELECT 'dim_artist', COUNT(*) FROM core.dim_artist
UNION ALL SELECT 'dim_track',  COUNT(*) FROM core.dim_track;


-- Check 3: why rows could be missing (only matters if Check 1 differs)
SELECT 'spotify_empty_names' AS reason, COUNT(*) AS row_count
FROM staging.stg_spotify_streams
WHERE artist_name IS NULL OR trim(artist_name) = ''
   OR track_name  IS NULL OR trim(track_name)  = ''
UNION ALL
SELECT 'spotify_duplicates', COUNT(*) - COUNT(DISTINCT (played_at_utc, COALESCE(spotify_track_uri, 'no_uri')))
FROM staging.stg_spotify_streams
UNION ALL
SELECT 'ytm_empty_names', COUNT(*)
FROM staging.stg_ytm_history
WHERE artist_name IS NULL OR trim(artist_name) = ''
   OR track_name  IS NULL OR trim(track_name)  = ''
UNION ALL
SELECT 'ytm_duplicates', COUNT(*) - COUNT(DISTINCT (played_at_utc, COALESCE(video_id, 'no_id')))
FROM staging.stg_ytm_history;