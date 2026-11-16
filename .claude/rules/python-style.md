---
paths:
  - "**/*.py"
---

# Python style
- Pandas with vectorized operations; no row-by-row loops.
- Read config and secrets from .env with python-dotenv; never hardcode credentials.
- Load to PostgreSQL with SQLAlchemy + psycopg.
- One script per step (extract, validate, load); small functions with docstrings.
- Every load script ends with a printed validation summary.
- I'm learning: add short comments to non-obvious code.
