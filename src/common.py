"""Shared helpers for the extract and sample scripts.

One place for the staging column lists, the CSV format and the validation
table, so every script writes the same shape of output.
"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]  # project root, so scripts run from any folder
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SAMPLE_DIR = ROOT / "data" / "sample"

# Staging columns in their exact output order (see docs/data_model.md).
SPOTIFY_COLUMNS = [
    "played_at_utc", "ended_at_utc", "ms_played", "track_name", "artist_name",
    "album_name", "spotify_track_uri", "device_raw", "device_name", "reason_start",
    "reason_end", "is_shuffle", "is_skipped", "is_offline", "source_file",
]
YTM_COLUMNS = [
    "played_at_utc", "track_name", "artist_name", "channel_name",
    "is_topic_channel", "video_id", "source_file",
]

CYRILLIC = r"[Ѐ-ӿ]"
UTF8_BOM = b"\xef\xbb\xbf"
ISO_UTC_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


# ---------- cleaning ----------

def clean_text(df: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int, int]:
    """Trim whitespace in text columns; empty strings become NULL.

    Returns the cleaned frame plus how many values were trimmed and how many
    became NULL, so the change is reported instead of happening silently.
    """
    df = df.copy()
    trimmed = emptied = 0
    for col in columns:
        original = df[col]
        stripped = original.str.strip()
        # NaN != NaN is True, so only compare values that exist
        trimmed += int((original.notna() & (stripped != original)).sum())
        emptied += int((stripped == "").sum())
        df[col] = stripped.mask(stripped == "")  # mask() puts NULL where the condition is True
    return df, trimmed, emptied


def to_iso_utc(ts: pd.Series) -> pd.Series:
    """Format UTC timestamps as ISO 8601 with milliseconds: 2026-03-01T08:15:30.123Z."""
    # %f gives microseconds (6 digits); cut the last 3 to keep milliseconds
    return ts.dt.strftime("%Y-%m-%dT%H:%M:%S.%f").str[:-3] + "Z"


def to_kyiv(ts: pd.Series) -> pd.Series:
    """Convert UTC timestamps to Europe/Kyiv (handles daylight saving time)."""
    return ts.dt.tz_convert("Europe/Kyiv")


# ---------- CSV ----------

def write_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    """Write a staging CSV: UTF-8 without BOM, comma, header row,
    NULL as an empty field, booleans as true/false, timestamps as ISO 8601 UTC."""
    out = df[columns].copy()
    for col in columns:
        if isinstance(out[col].dtype, pd.DatetimeTZDtype):
            out[col] = to_iso_utc(out[col])
        elif pd.api.types.is_bool_dtype(out[col]):
            out[col] = out[col].map({True: "true", False: "false"})
    path.parent.mkdir(parents=True, exist_ok=True)
    # encoding="utf-8" has no BOM ("utf-8-sig" would add one); "\n" line ends suit PostgreSQL COPY
    out.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def csv_checks(df: pd.DataFrame, path: Path, columns: list[str]) -> list[tuple]:
    """Read the written CSV back and confirm the format rules survived the round trip."""
    with open(path, "rb") as fh:
        has_bom = fh.read(3) == UTF8_BOM
    # dtype=str + keep_default_na=False: read every field as raw text, empty stays ""
    back = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")

    text_cols = [c for c in columns if pd.api.types.is_string_dtype(df[c])]
    cyr_before = int(df[text_cols].apply(lambda s: s.str.contains(CYRILLIC, na=False)).sum().sum())
    cyr_after = int(back[text_cols].apply(lambda s: s.str.contains(CYRILLIC)).sum().sum())
    # every text value must come back exactly as it was (NULL comes back as "")
    # .to_numpy() compares by position, so index labels do not matter
    text_diff = int(sum((back[c].to_numpy() != df[c].fillna("").to_numpy()).sum() for c in text_cols))

    nulls_before = int(df[columns].isna().sum().sum())
    empty_after = int((back == "").sum().sum())

    bool_cols = [c for c in columns if pd.api.types.is_bool_dtype(df[c])]
    bool_values = set(back[bool_cols].stack().unique()) if bool_cols else set()

    ts_cols = [c for c in columns if isinstance(df[c].dtype, pd.DatetimeTZDtype)]
    bad_ts = int(sum((~back[c].str.match(ISO_UTC_MS)).sum() for c in ts_cols))

    return [
        check("CSV: rows written", f"{len(back):,}", len(back) == len(df)),
        check("CSV: header = expected columns", "yes" if list(back.columns) == columns else "no",
              list(back.columns) == columns),
        check("CSV: UTF-8 without BOM", "BOM found" if has_bom else "no BOM", not has_bom),
        check("CSV: text cells with Cyrillic (before / after)", f"{cyr_before:,} / {cyr_after:,}",
              cyr_before == cyr_after),
        check("CSV: text values changed by round trip", f"{text_diff:,}", text_diff == 0),
        check("CSV: NULLs written as empty fields", f"{nulls_before:,} / {empty_after:,}",
              nulls_before == empty_after),
        check("CSV: boolean values", ", ".join(sorted(bool_values)) or "-",
              bool_values <= {"true", "false", ""}),
        check("CSV: timestamps in ISO 8601 UTC format", f"{bad_ts} bad", bad_ts == 0),
    ]


# ---------- validation table ----------

def check(name: str, result, ok: bool | None = None) -> tuple:
    """One row of the validation table. ok=None means info only (no PASS/FAIL)."""
    status = "" if ok is None else ("PASS" if ok else "FAIL")
    return (name, str(result), status)


def sql_type(dtype) -> str:
    """Planned PostgreSQL staging type for a pandas dtype."""
    if isinstance(dtype, pd.DatetimeTZDtype):
        return "timestamptz"
    if pd.api.types.is_bool_dtype(dtype):
        return "boolean"
    if pd.api.types.is_integer_dtype(dtype):
        return "integer"
    return "text"


def standard_checks(df: pd.DataFrame, key_columns: list[str],
                    dedup_keys: list[tuple[str, list[str], bool]]) -> list[tuple]:
    """Checks every staging table needs: NULLs, duplicates, data types, date range.

    dedup_keys: (label, columns, must_be_zero). must_be_zero=False reports the
    count as info only.
    """
    rows = []
    for col in key_columns:
        n = int(df[col].isna().sum())
        rows.append(check(f"NULLs in {col}", f"{n:,}", n == 0))
    for label, cols, must_be_zero in dedup_keys:
        n = int(df.duplicated(subset=cols).sum())
        rows.append(check(f"Duplicates on {label}", f"{n:,}", (n == 0) if must_be_zero else None))
    for col in key_columns:
        rows.append(check(f"Type of {col}", f"{df[col].dtype} -> {sql_type(df[col].dtype)}"))
    played = df["played_at_utc"]
    first, last = to_iso_utc(pd.Series([played.min(), played.max()]))
    rows.append(check("played_at_utc min", first))
    rows.append(check("played_at_utc max", last))
    n_future = int((played > datetime.now(timezone.utc)).sum())
    rows.append(check("Future played_at_utc", f"{n_future:,}", n_future == 0))
    return rows


def print_table(title: str, rows: list[tuple]) -> None:
    """Print the validation table: Check | Result | Status."""
    w1 = max(len("Check"), *(len(r[0]) for r in rows))
    w2 = max(len("Result"), *(len(r[1]) for r in rows))
    print(f"\n=== {title} ===")
    print(f"{'Check':<{w1}}  {'Result':<{w2}}  Status")
    print(f"{'-' * w1}  {'-' * w2}  ------")
    for name, result, status in rows:
        print(f"{name:<{w1}}  {result:<{w2}}  {status}")


def stop_if_failed(title: str, rows: list[tuple]) -> None:
    """Print the table and exit with an error if any check failed."""
    failed = [r[0] for r in rows if r[2] == "FAIL"]
    if failed:
        print_table(title, rows)
        print(f"\nSTOPPED: {len(failed)} check(s) failed: {', '.join(failed)}")
        sys.exit(1)
