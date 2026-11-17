"""Step 1a: Spotify Extended streaming history -> data/processed/stg_spotify_streams.csv

Reads data/raw/spotify_extended/Streaming_History_Audio_*.json (video files and
the PDF are ignored), keeps music only, drops private and unused fields, derives
start/end timestamps and a normalized device, removes duplicate plays, writes a
staging CSV and prints the validation table.

Run from the project root:  python src/extract_spotify.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from common import (PROCESSED_DIR, RAW_DIR, SPOTIFY_COLUMNS, check, clean_text,
                    csv_checks, print_table, standard_checks, stop_if_failed, to_kyiv,
                    write_csv)

SOURCE_DIR = RAW_DIR / "spotify_extended"
SOURCE_PATTERN = "Streaming_History_Audio_*.json"
OUTPUT_PATH = PROCESSED_DIR / "stg_spotify_streams.csv"

# Only these raw fields are loaded. ip_addr, offline_timestamp, conn_country,
# incognito_mode and the episode/audiobook names never enter the DataFrame.
RAW_FIELDS = [
    "ts", "ms_played", "master_metadata_track_name", "master_metadata_album_artist_name",
    "master_metadata_album_album_name", "spotify_track_uri", "platform",
    "reason_start", "reason_end", "shuffle", "skipped", "offline",
    "spotify_episode_uri", "audiobook_uri",  # only to explain dropped rows; not written
]
RENAME = {
    "master_metadata_track_name": "track_name",
    "master_metadata_album_artist_name": "artist_name",
    "master_metadata_album_album_name": "album_name",
    "platform": "device_raw",
    "shuffle": "is_shuffle",
    "skipped": "is_skipped",
    "offline": "is_offline",
}
TEXT_COLUMNS = ["track_name", "artist_name", "album_name", "spotify_track_uri",
                "device_raw", "reason_start", "reason_end"]
DEDUP_KEY = ["ended_at_utc", "spotify_track_uri"]
QUALIFIED_MS = 30_000  # a play counts as qualified from 30 seconds


def read_raw(source_dir: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Load all audio history files into one DataFrame, keeping only RAW_FIELDS."""
    paths = sorted(source_dir.glob(SOURCE_PATTERN))
    if not paths:
        raise FileNotFoundError(f"No {SOURCE_PATTERN} files in {source_dir}")
    frames, counts = [], {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            records = json.load(fh)
        # columns= picks only the listed keys, so ip_addr is never copied in
        frame = pd.DataFrame(records, columns=RAW_FIELDS)
        frame["source_file"] = path.name
        frames.append(frame)
        counts[path.name] = len(frame)
    return pd.concat(frames, ignore_index=True).rename(columns=RENAME), counts


def keep_music(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Keep rows with a spotify_track_uri; count dropped rows by reason."""
    is_music = df["spotify_track_uri"].notna()
    dropped = df[~is_music]
    n_podcast = int(dropped["spotify_episode_uri"].notna().sum())
    n_audiobook = int(dropped["audiobook_uri"].notna().sum())
    reasons = {
        "podcast episodes": n_podcast,
        "audiobooks": n_audiobook,
        "other rows without track URI": len(dropped) - n_podcast - n_audiobook,
    }
    music = df[is_music].drop(columns=["spotify_episode_uri", "audiobook_uri"])
    return music, reasons


def add_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """ts is the END of playback (UTC); the start is ts minus ms_played."""
    df = df.copy()
    df["ended_at_utc"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    df["played_at_utc"] = df["ended_at_utc"] - pd.to_timedelta(df["ms_played"], unit="ms")
    return df.drop(columns=["ts"])


def normalize_device(raw: pd.Series) -> pd.Series:
    """Map raw platform strings to Android / Windows / Web Player / Unknown."""
    low = raw.str.lower()
    conditions = [
        low.str.startswith("android", na=False),     # "android", "Android OS 12 API 31 (...)"
        low.str.startswith("windows", na=False),
        low.str.startswith("web_player", na=False),  # "web_player windows 10;chrome ..."
    ]
    # np.select picks the first matching choice per row, else the default
    return pd.Series(np.select(conditions, ["Android", "Windows", "Web Player"], default="Unknown"),
                     index=raw.index, dtype="str")


def drop_duplicate_plays(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove repeated plays on (ended_at_utc, spotify_track_uri).

    If the repeats differ in ms_played, keep the longest one (the most complete
    record of that play). Returns kept rows and removed rows.
    """
    ordered = df.sort_values("ms_played", ascending=False, kind="stable")
    is_dup = ordered.duplicated(subset=DEDUP_KEY, keep="first")
    kept = ordered[~is_dup].sort_values(["played_at_utc", "ended_at_utc"], kind="stable")
    return kept.reset_index(drop=True), ordered[is_dup]


def build_checks(df, read_counts, drop_reasons, removed, n_dup_groups_diff,
                 trimmed, emptied) -> list[tuple]:
    """Rows of the validation table required by .claude/rules/data-validation.md."""
    n_read = sum(read_counts.values())
    n_dropped = sum(drop_reasons.values()) + len(removed)
    rows = [check(f"Rows read ({len(read_counts)} files)", f"{n_read:,}")]
    rows += [check(f"  {name}", f"{n:,}") for name, n in read_counts.items()]
    rows += [check(f"Dropped: {reason}", f"{n:,}") for reason, n in drop_reasons.items()]
    rows.append(check("Dropped: duplicate plays (ended_at_utc, uri)", f"{len(removed):,}"))
    rows.append(check("  dup groups with different ms_played (kept longest)",
                      f"{n_dup_groups_diff:,}"))
    rows.append(check("  ms_played in removed duplicates", f"{removed['ms_played'].sum() / 1000:,.1f} s"))
    rows.append(check("Rows kept (target)", f"{len(df):,}"))
    rows.append(check("Difference read - kept", f"{n_read - len(df):,}", n_read - n_dropped == len(df)))

    rows += standard_checks(
        df,
        key_columns=["played_at_utc", "ended_at_utc", "track_name", "artist_name",
                     "spotify_track_uri", "ms_played"],
        dedup_keys=[("(ended_at_utc, spotify_track_uri)", DEDUP_KEY, True),
                    ("(played_at_utc, track_name, artist_name)",
                     ["played_at_utc", "track_name", "artist_name"], False)],
    )

    n_negative = int((df["ms_played"] < 0).sum())
    rows.append(check("ms_played < 0", f"{n_negative:,}", n_negative == 0))
    rows.append(check("ms_played = 0 (kept, filtered later in SQL)", f"{(df['ms_played'] == 0).sum():,}"))
    rows.append(check(f"ms_played < {QUALIFIED_MS:,} (not qualified)",
                      f"{(df['ms_played'] < QUALIFIED_MS).sum():,}"))
    rows.append(check("Total hours played", f"{df['ms_played'].sum() / 3_600_000:,.1f}"))
    rows.append(check("Distinct tracks (spotify_track_uri)", f"{df['spotify_track_uri'].nunique():,}"))
    rows.append(check("Distinct tracks (artist + track name)",
                      f"{len(df[['artist_name', 'track_name']].drop_duplicates()):,}"))
    rows.append(check("Distinct artists", f"{df['artist_name'].nunique():,}"))

    for device, n in df["device_name"].value_counts().items():
        rows.append(check(f"device_name = {device}", f"{n:,}"))
    # a raw value that is not literally "unknown" but fell into Unknown means the mapping needs a new rule
    unmapped = (df["device_name"] == "Unknown") & (df["device_raw"].str.lower() != "unknown")
    rows.append(check("Unmapped device_raw values", f"{int(unmapped.sum()):,}", not unmapped.any()))

    kyiv_month = to_kyiv(df["played_at_utc"]).dt.strftime("%Y-%m")
    in_window = kyiv_month.between("2026-03", "2026-06")
    rows.append(check("Rows in comparison window Mar-Jun 2026 (Kyiv)", f"{int(in_window.sum()):,}"))
    rows.append(check("Text values trimmed / empty -> NULL", f"{trimmed:,} / {emptied:,}"))
    return rows


def main() -> None:
    title = f"Validation: {OUTPUT_PATH.name}"
    raw, read_counts = read_raw(SOURCE_DIR)
    raw, trimmed, emptied = clean_text(raw, TEXT_COLUMNS)
    music, drop_reasons = keep_music(raw)
    music = add_timestamps(music)
    music["device_name"] = normalize_device(music["device_raw"])

    # how many duplicate groups are not identical in ms_played (reported, not hidden)
    dup_rows = music[music.duplicated(subset=DEDUP_KEY, keep=False)]
    n_dup_groups_diff = int(dup_rows.groupby(DEDUP_KEY)["ms_played"].nunique().gt(1).sum())
    streams, removed = drop_duplicate_plays(music)

    rows = build_checks(streams, read_counts, drop_reasons, removed, n_dup_groups_diff,
                        trimmed, emptied)
    stop_if_failed(title, rows)  # data checks first: nothing is written if one fails

    write_csv(streams, OUTPUT_PATH, SPOTIFY_COLUMNS)
    rows += csv_checks(streams, OUTPUT_PATH, SPOTIFY_COLUMNS)
    stop_if_failed(title, rows)
    print_table(title, rows)
    print(f"\nWritten: {OUTPUT_PATH.relative_to(OUTPUT_PATH.parents[2])}")


if __name__ == "__main__":
    main()
