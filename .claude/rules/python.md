---
paths:
  - "**/*.py"
---

# Python conventions
- Manage dependencies with `uv add`, never `pip install`.
- Read config from env vars via `python-dotenv`; add new keys to `.env.example`.
- Keep the app in `main.py` until it outgrows a single file.
