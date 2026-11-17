"""Step 1b: YouTube Music (Google Takeout) -> data/processed/stg_ytm_history.csv

Reads data/raw/youtube_takeout/історія переглядів.json (Ukrainian-localized watch
history), keeps YouTube Music records only, parses track, channel, artist and
video_id, drops removed videos and duplicates, writes a staging CSV and prints
the validation table. Search history (історія пошуку.json) is ignored.

Run from the project root:  python src/extract_ytm.py
"""
import json
from pathlib import Path

import pandas as pd

from common import (PROCESSED_DIR, RAW_DIR, YTM_COLUMNS, check, clean_text, csv_checks,
                    print_table, standard_checks, stop_if_failed, to_kyiv, write_csv)

SOURCE_PATH = RAW_DIR / "youtube_takeout" / "історія переглядів.json"
OUTPUT_PATH = PROCESSED_DIR / "stg_ytm_history.csv"

RAW_FIELDS = ["header", "title", "titleUrl", "time", "subtitles"]  # nothing else is loaded
YTM_HEADER = "YouTube Музика"
YTM_HOST = "music.youtube.com"
TITLE_PREFIX = "Ви дивилися "  # "You watched " in the Ukrainian export
TOPIC_SUFFIX = " - Topic"      # auto-generated artist channels: "<Artist> - Topic"
DEDUP_KEY = ["played_at_utc", "video_id"]


def read_raw(path: Path) -> pd.DataFrame:
    """Load the watch history JSON, keeping only RAW_FIELDS."""
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)
    df = pd.DataFrame(records, columns=RAW_FIELDS)
    df["source_file"] = path.name
    return df


def keep_youtube_music(df: pd.DataFrame) -> pd.DataFrame:
    """Keep records with the YouTube Music header or a music.youtube.com link."""
    host = df["titleUrl"].str.extract(r"^https?://([^/?#]+)", expand=False)
    return df[(df["header"] == YTM_HEADER) | (host == YTM_HOST)].copy()


def split_channel(channel: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Artist name = channel without a trailing ' - Topic'; flag whether it had it."""
    is_topic = channel.str.endswith(TOPIC_SUFFIX)
    artist = channel.str.removesuffix(TOPIC_SUFFIX).str.strip()
    return artist, is_topic


def parse_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Build the staging columns from the raw Takeout fields."""
    df = df.copy()
    df["played_at_utc"] = pd.to_datetime(df["time"], utc=True, format="ISO8601")  # START of playback
    df["has_prefix"] = df["title"].str.startswith(TITLE_PREFIX)
    df["track_name"] = df["title"].str.removeprefix(TITLE_PREFIX)
    # subtitles is a list of {name, url}; .str[0] takes the first item, .str.get reads its "name"
    df["channel_name"] = df["subtitles"].str[0].str.get("name").astype("str")
    df["video_id"] = df["titleUrl"].str.extract(r"[?&]v=([^&#]+)", expand=False)
    return df


def build_checks(df, n_read, n_not_ytm, n_no_subtitles, removed, n_no_prefix,
                 trimmed, emptied) -> list[tuple]:
    """Rows of the validation table required by .claude/rules/data-validation.md."""
    n_dropped = n_not_ytm + n_no_subtitles + len(removed)
    rows = [
        check(f"Rows read ({SOURCE_PATH.name})", f"{n_read:,}"),
        check("Dropped: not YouTube Music (regular YouTube)", f"{n_not_ytm:,}"),
        check("YouTube Music records", f"{n_read - n_not_ytm:,}"),
        check("Dropped: no subtitles (removed videos)", f"{n_no_subtitles:,}"),
        check("Dropped: duplicates (played_at_utc, video_id)", f"{len(removed):,}"),
        check("Rows kept (target)", f"{len(df):,}"),
        check("Difference read - kept", f"{n_read - len(df):,}", n_read - n_dropped == len(df)),
        check(f"Titles without '{TITLE_PREFIX.strip()}' prefix", f"{n_no_prefix:,}", n_no_prefix == 0),
    ]
    rows += standard_checks(
        df,
        key_columns=["played_at_utc", "track_name", "artist_name", "channel_name", "video_id"],
        dedup_keys=[("(played_at_utc, video_id)", DEDUP_KEY, True),
                    ("(played_at_utc, track_name, artist_name)",
                     ["played_at_utc", "track_name", "artist_name"], False)],
    )
    n_bad_id = int((df["video_id"].str.len() != 11).sum())  # YouTube video IDs are 11 characters
    rows.append(check("video_id not 11 characters", f"{n_bad_id:,}", n_bad_id == 0))
    rows.append(check("Topic channels (is_topic_channel = true)",
                      f"{int(df['is_topic_channel'].sum()):,} of {len(df):,}"))
    rows.append(check("Distinct tracks (video_id)", f"{df['video_id'].nunique():,}"))
    rows.append(check("Distinct tracks (artist + track name)",
                      f"{len(df[['artist_name', 'track_name']].drop_duplicates()):,}"))
    rows.append(check("Distinct artists", f"{df['artist_name'].nunique():,}"))

    kyiv_month = to_kyiv(df["played_at_utc"]).dt.strftime("%Y-%m")
    rows.append(check("Rows in comparison window Jul-Sep 2026 (Kyiv)",
                      f"{int(kyiv_month.between('2026-07', '2026-09').sum()):,}"))
    rows.append(check("Rows before Jul 2026 (Kyiv)", f"{int((kyiv_month < '2026-07').sum()):,}"))
    rows.append(check("Text values trimmed / empty -> NULL", f"{trimmed:,} / {emptied:,}"))
    return rows


def main() -> None:
    title = f"Validation: {OUTPUT_PATH.name}"
    raw = read_raw(SOURCE_PATH)
    ytm = parse_fields(keep_youtube_music(raw))
    n_not_ytm = len(raw) - len(ytm)
    n_no_prefix = int((~ytm["has_prefix"]).sum())
    ytm, trimmed, emptied = clean_text(ytm, ["track_name", "channel_name", "video_id"])

    # records without subtitles are removed videos: no channel, so no artist
    has_channel = ytm["channel_name"].notna()
    n_no_subtitles = int((~has_channel).sum())
    ytm = ytm[has_channel].copy()
    ytm["artist_name"], ytm["is_topic_channel"] = split_channel(ytm["channel_name"])

    is_dup = ytm.duplicated(subset=DEDUP_KEY, keep="first")
    removed = ytm[is_dup]
    history = ytm[~is_dup].sort_values("played_at_utc", kind="stable").reset_index(drop=True)

    rows = build_checks(history, len(raw), n_not_ytm, n_no_subtitles, removed, n_no_prefix,
                        trimmed, emptied)
    stop_if_failed(title, rows)  # data checks first: nothing is written if one fails

    write_csv(history, OUTPUT_PATH, YTM_COLUMNS)
    rows += csv_checks(history, OUTPUT_PATH, YTM_COLUMNS)
    stop_if_failed(title, rows)
    print_table(title, rows)
    print(f"\nWritten: {OUTPUT_PATH.relative_to(OUTPUT_PATH.parents[2])}")


if __name__ == "__main__":
    main()
