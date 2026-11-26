-- Purpose: core fact table (one row = one play) and indexes
CREATE TABLE IF NOT EXISTS core.fact_streams (
    stream_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    
    service_key SMALLINT NOT NULL,
    track_key INTEGER NOT NULL,
    artist_key INTEGER NOT NULL,
    device_key SMALLINT NOT NULL,
    date_key INTEGER NOT NULL,
    hour_key SMALLINT NOT NULL,

    played_at_utc TIMESTAMPTZ NOT NULL,
    ms_played INTEGER CHECK (ms_played >= 0), -- NULL for YouTube Music
    is_skipped BOOLEAN,
    is_shuffle BOOLEAN,
    reason_start TEXT,
    reason_end TEXT,
    source_item_id TEXT NOT NULL, -- Spotify URI or YouTube video_id

    CONSTRAINT fk_fact_service FOREIGN KEY (service_key) REFERENCES core.dim_service (service_key),
    CONSTRAINT fk_fact_track   FOREIGN KEY (track_key)   REFERENCES core.dim_track   (track_key),
    CONSTRAINT fk_fact_artist  FOREIGN KEY (artist_key)  REFERENCES core.dim_artist  (artist_key),
    CONSTRAINT fk_fact_device  FOREIGN KEY (device_key)  REFERENCES core.dim_device  (device_key),
    CONSTRAINT fk_fact_date    FOREIGN KEY (date_key)    REFERENCES core.dim_date    (date_key),
    CONSTRAINT fk_fact_time    FOREIGN KEY (hour_key)    REFERENCES core.dim_time    (hour_key),
    CONSTRAINT uq_fact_stream  UNIQUE (service_key, played_at_utc, source_item_id)
);
CREATE INDEX IF NOT EXISTS idx_fact_date   ON core.fact_streams (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_track  ON core.fact_streams (track_key);
CREATE INDEX IF NOT EXISTS idx_fact_artist ON core.fact_streams (artist_key);