# Data validation (every data task)
Before saying a load or transform is done, report in a short table:
- Row count: source vs target, and the difference
- NULLs in key columns (played_at, track name, artist name)
- Duplicates by the dedup key
- Data types of key columns
- Date range (min and max played_at)

If a check fails, stop and explain. Never fix data silently.

Known traps in this project:
- UTC vs Europe/Kyiv, including daylight saving time changes
- Podcasts mixed with music (track name is NULL)
- ms_played = 0 or very small values
- The same artist or track spelled differently across platforms ("Artist - Topic", "(Official Video)")
