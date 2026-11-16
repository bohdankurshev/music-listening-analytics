---
paths:
  - "**/*.sql"
---

# SQL style (PostgreSQL)
- First line of every file: a comment with its purpose and the dialect (PostgreSQL).
- Uppercase SQL keywords, snake_case names.
- CTEs with clear names instead of nested subqueries.
- Explicit column lists; no SELECT * outside quick exploration.
- Check join grain: compare row counts before and after each JOIN.
- DDL is idempotent (CREATE ... IF NOT EXISTS). DML loads are re-runnable without creating duplicates.
- Never DROP or TRUNCATE anything without asking me first.
