# [Input] os.environ
# [Output] Parsed integer environment variable values.
# [Pos] utility node in backend/libs/utils
# [Sync] 2026-05-23: extracted from infrastructure/persistence/_base.py
import os


def read_int_env(key: str, default: int = 0) -> int:
    """Read an integer from environment variables, returning *default* on missing or invalid values."""
    try:
        return int(os.environ.get(key, str(default)) or str(default))
    except (ValueError, TypeError):
        return default
