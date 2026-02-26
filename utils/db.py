"""
db.py — MySQL connection helper for FinPort-AI.

Planned implementation:
  - Read DB_HOST, DB_USER, DB_PASSWORD, DB_NAME from environment (.env)
  - Provide a get_connection() helper that returns a mysql-connector-python connection
  - Optionally provide a context manager for safe connection handling

This file is a placeholder. Logic will be implemented in a future phase.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# TODO: Implement get_connection() using mysql.connector
