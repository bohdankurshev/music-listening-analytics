---
name: validate-data
description: Run data-quality checks after a load or transform and produce a PASS/FAIL table. Use before building visuals or committing SQL changes.
argument-hint: "[schema.table or pipeline step]"
---

Validate $ARGUMENTS and report a table: Check | Result | Status.
1. Row count vs source
2. NULLs in key columns
3. Duplicates by the dedup key
4. Data types of key columns
5. Date range, including future dates
6. Referential integrity: every fact row has matching dimension keys
7. Totals: sum of ms_played vs source

Mark each check PASS or FAIL. On FAIL, show the query that found it and stop.
Never change data during validation.
