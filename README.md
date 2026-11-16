# Music Listening Analytics

End-to-end analysis of my own music listening history across Spotify and YouTube Music: from raw data exports to a PostgreSQL star schema and a Power BI dashboard.

> Status: in progress

## Questions
1. Which tracks do I skip, and why?
2. Do I discover new artists or return to familiar ones? (artist cohorts and retention)
3. How has the share of Ukrainian artists in my listening changed since 2022?
4. Did my listening change after switching from Spotify to YouTube Music?

## Architecture
Raw JSON exports -> Python (extract, validate) -> PostgreSQL (`staging` -> `core` star schema -> views) -> Power BI

## Stack
Python (Pandas, SQLAlchemy), PostgreSQL, Power BI, Git

## Data and privacy
Raw exports contain personal data and are not published. The repository contains code, SQL, synthetic sample data and aggregated results only.
