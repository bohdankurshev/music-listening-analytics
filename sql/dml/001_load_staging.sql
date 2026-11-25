BEGIN;

TRUNCATE staging.stg_spotify_streams, staging.stg_ytm_history;

COPY staging.stg_spotify_streams (
    played_at_utc, ended_at_utc, ms_played, track_name, artist_name, album_name,
    spotify_track_uri, device_raw, device_name, reason_start, reason_end,
    is_shuffle, is_skipped, is_offline, source_file
)
FROM 'G:/music-listening-analytics/data/processed/stg_spotify_streams.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

COPY staging.stg_ytm_history (
    played_at_utc, track_name, artist_name, channel_name,
    is_topic_channel, video_id, source_file
)
FROM 'G:/music-listening-analytics/data/processed/stg_ytm_history.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

COMMIT;