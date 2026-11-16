---
name: profile-data
description: Profile a new data file or table - shape, columns, types, NULLs, distinct values, date ranges and suspicious values. Use when a new export arrives or when meeting an unfamiliar dataset.
argument-hint: "[file path or schema.table]"
---

Profile $ARGUMENTS and report in Ukrainian:
1. Rows, columns, and file or table size
2. Per column: type, % NULL, distinct count, 3 example values
3. Date columns: min, max, gaps
4. Numeric columns: min, max, median, outliers
5. Suspicious values: empty strings, zeros, duplicates, broken encoding

End with what needs cleaning before loading, and which columns form the natural key.
Read-only: never modify the data.
