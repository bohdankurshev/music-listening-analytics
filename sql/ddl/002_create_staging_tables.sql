CREATE TABLE IF NOT EXISTS staging.stg_spotify_streams (
    played_at_utc      TIMESTAMPTZ,
    ended_at_utc       TIMESTAMPTZ,
    ms_played          INTEGER,
    track_name         TEXT,
    artist_name        TEXT,
    album_name         TEXT,
    spotify_track_uri  TEXT,
    device_raw         TEXT,
    device_name        TEXT,
    reason_start       TEXT,
    reason_end         TEXT,
    is_shuffle         BOOLEAN,
    is_skipped         BOOLEAN,
    is_offline         BOOLEAN,
    source_file        TEXT,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.stg_ytm_history (
    played_at_utc      TIMESTAMPTZ,
    track_name         TEXT,
    artist_name        TEXT,
    channel_name       TEXT,
    is_topic_channel   BOOLEAN,
    video_id           TEXT,
    source_file        TEXT,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);