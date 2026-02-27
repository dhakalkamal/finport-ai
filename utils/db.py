"""
db.py — MySQL connection helper for FinPort-AI.

Reads connection config from .env and provides:
  - get_connection()  — returns a plain mysql.connector connection
  - managed_conn()    — context manager that auto-closes the connection
"""

import os
from contextlib import contextmanager

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

_DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "finport"),
    "ssl_disabled": True,
}


def get_connection() -> mysql.connector.MySQLConnection:
    """Return an open MySQL connection using credentials from .env."""
    return mysql.connector.connect(**_DB_CONFIG)


@contextmanager
def managed_conn():
    """Context manager that yields a connection and closes it on exit.

    Usage:
        with managed_conn() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT ...")
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
