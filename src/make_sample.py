"""Step 0: synthetic sample data -> data/sample/stg_spotify_streams.csv, stg_ytm_history.csv

Creates 20 fake rows per staging file, with the same columns and CSV format as
the real pipeline, so the public repo can be explored without personal data.
Nothing here reads data/raw: every artist, track, ID and device is invented.

The sample also contains the project's known traps on purpose: ms_played = 0,
a short (not qualified) play, plays around the DST change on 2026-03-29, a
non-Topic YouTube channel, "(Official Video)" titles and an artist spelled with
different case on the two platforms.

Run from the project root:  python src/make_sample.py
"""
import numpy as np
import pandas as pd

from common import (SAMPLE_DIR, SPOTIFY_COLUMNS, YTM_COLUMNS, check, csv_checks,
                    print_table, standard_checks, stop_if_failed, write_csv)
from extract_spotify import normalize_device
from extract_ytm import split_channel

SEED = 42      # fixed seed: the same sample every run
N_ROWS = 20

# (artist, track, album). Invented names, Latin and Cyrillic.
FAKE_SPOTIFY_TRACKS = [
    ("Fake Artist One", "Fake Track 01", "Sample Album A"),
    ("Fake Artist One", "Fake Track 02", "Sample Album A"),
    ("Фейковий Гурт", "Тестова пісня 03", "Вигаданий альбом"),
    ("Фейковий Гурт", "Тестова пісня 04", "Вигаданий альбом"),
    ("Вигаданий Виконавець", "Нічна вигадка 05", "Чернетки"),
    ("Sample Collective", "Placeholder Groove 06", "Sample Album B"),
]
FAKE_DEVICES = [
    "android",
    "windows",
    "Android OS 14 API 34 (SampleVendor, SV0001)",
    "web_player windows 10;chrome 120.0.0.0;desktop",
    "unknown",
]
# (channel, track) as YouTube Music shows them
FAKE_YTM_TRACKS = [
    ("Fake Artist One - Topic", "Fake Track 01"),
    ("Fake Artist One Official", "Fake Track 01 (Official Video)"),  # non-Topic channel
    ("Фейковий Гурт - Topic", "Тестова пісня 03"),
    ("вигаданий виконавець - Topic", "Нічна вигадка 05"),  # other case than on Spotify
    ("Sample Collective - Topic", "Placeholder Groove 06"),
    ("New Fake Artist - Topic", "Fresh Fake Track 07"),     # YouTube Music only
]


def pick_rows(rng, n_choices: int) -> np.ndarray:
    """Row picks that use every catalogue entry at least once, the rest at random."""
    return np.concatenate([np.arange(n_choices), rng.integers(0, n_choices, N_ROWS - n_choices)])


def random_times(rng, start: str, end: str, n: int) -> pd.Series:
    """n random UTC timestamps between start and end, with milliseconds."""
    t0, t1 = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    offset_ms = rng.integers(0, int((t1 - t0).total_seconds() * 1000), n)
    return pd.Series(t0 + pd.to_timedelta(offset_ms, unit="ms"))


def make_spotify(rng) -> pd.DataFrame:
    """20 fake Spotify plays in the comparison window Mar-Jun 2026."""
    pick = pick_rows(rng, len(FAKE_SPOTIFY_TRACKS))
    tracks = pd.DataFrame(FAKE_SPOTIFY_TRACKS, columns=["artist_name", "track_name", "album_name"])
    # obviously fake URIs: "SAMPLE" + 16 digits keeps the real 22-character ID length
    tracks["spotify_track_uri"] = [f"spotify:track:SAMPLE{i + 1:016d}" for i in range(len(tracks))]
    df = tracks.iloc[pick].reset_index(drop=True).astype("str")

    df["ended_at_utc"] = random_times(rng, "2026-03-01", "2026-07-01", N_ROWS)
    df["ms_played"] = rng.integers(30_000, 300_000, N_ROWS)
    df["reason_start"] = pd.Series(rng.choice(["trackdone", "clickrow", "fwdbtn", "playbtn"], N_ROWS), dtype="str")
    df["reason_end"] = pd.Series(rng.choice(["trackdone", "endplay", "fwdbtn", "backbtn"], N_ROWS), dtype="str")

    # known traps, placed on fixed rows
    df.loc[0, ["ms_played", "reason_end"]] = [0, "trackerror"]   # ms_played = 0
    df.loc[1, ["ms_played", "reason_end"]] = [12_000, "fwdbtn"]  # short play, not qualified
    # DST change in Kyiv: 2026-03-29 01:00 UTC (03:00 EET -> 04:00 EEST)
    df.loc[2, ["ended_at_utc", "ms_played"]] = [pd.Timestamp("2026-03-29T00:59:30Z"), 90_000]
    df.loc[3, ["ended_at_utc", "ms_played"]] = [pd.Timestamp("2026-03-29T01:05:00Z"), 120_000]

    df["played_at_utc"] = df["ended_at_utc"] - pd.to_timedelta(df["ms_played"], unit="ms")
    df["device_raw"] = pd.Series(np.resize(FAKE_DEVICES, N_ROWS), dtype="str")  # cycle through all
    df["device_name"] = normalize_device(df["device_raw"])
    df["is_shuffle"] = rng.random(N_ROWS) < 0.4
    df["is_skipped"] = df["reason_end"].isin(["fwdbtn", "backbtn"])
    df["is_offline"] = rng.random(N_ROWS) < 0.1
    df["source_file"] = "sample_streaming_history.json"
    return df.sort_values("played_at_utc", kind="stable").reset_index(drop=True)


def make_ytm(rng) -> pd.DataFrame:
    """20 fake YouTube Music plays in the comparison window Jul-Sep 2026."""
    pick = pick_rows(rng, len(FAKE_YTM_TRACKS))
    tracks = pd.DataFrame(FAKE_YTM_TRACKS, columns=["channel_name", "track_name"])
    # "SAMPLE" + 5 digits = 11 characters, the length of a real video ID
    tracks["video_id"] = [f"SAMPLE{i + 1:05d}" for i in range(len(tracks))]
    df = tracks.iloc[pick].reset_index(drop=True).astype("str")

    df["played_at_utc"] = random_times(rng, "2026-07-01", "2026-10-01", N_ROWS)
    df["artist_name"], df["is_topic_channel"] = split_channel(df["channel_name"])
    df["source_file"] = "sample_watch_history.json"
    return df.sort_values("played_at_utc", kind="stable").reset_index(drop=True)


def validate_and_write(df: pd.DataFrame, name: str, columns: list[str], key_columns: list[str],
                       dedup_key: list[str]) -> None:
    """Run the same checks as the real pipeline, write the CSV and print the table."""
    path = SAMPLE_DIR / name
    title = f"Validation: sample/{name}"
    rows = [check("Rows generated (synthetic)", f"{len(df):,}", len(df) == N_ROWS)]
    rows += standard_checks(df, key_columns, [(f"({', '.join(dedup_key)})", dedup_key, True)])
    rows.append(check("Distinct tracks / artists",
                      f"{df['track_name'].nunique()} / {df['artist_name'].nunique()}"))
    stop_if_failed(title, rows)
    write_csv(df, path, columns)
    rows += csv_checks(df, path, columns)
    stop_if_failed(title, rows)
    print_table(title, rows)


def main() -> None:
    rng = np.random.default_rng(SEED)
    validate_and_write(make_spotify(rng), "stg_spotify_streams.csv", SPOTIFY_COLUMNS,
                       ["played_at_utc", "ended_at_utc", "track_name", "artist_name", "ms_played"],
                       ["ended_at_utc", "spotify_track_uri"])
    validate_and_write(make_ytm(rng), "stg_ytm_history.csv", YTM_COLUMNS,
                       ["played_at_utc", "track_name", "artist_name", "video_id"],
                       ["played_at_utc", "video_id"])
    print(f"\nWritten to: {SAMPLE_DIR.relative_to(SAMPLE_DIR.parents[1])}")


if __name__ == "__main__":
    main()
