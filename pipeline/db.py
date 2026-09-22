"""
Storage Abstraction Layer - Gas Intelligence Platform
Milestone 2 / Commit 1

Purpose:
    Single backend-agnostic access point to the database so the storage
    engine can later migrate from SQLite to PostgreSQL without touching
    business logic (Decision D1: SQLite retained for now).

Environment variables:
    GIP_DB_BACKEND  : "sqlite" (default) | "postgresql" (reserved, not enabled)
    GIP_SQLITE_PATH : path to sqlite file (default: <repo_root>/gas_data.db)
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DB_BACKEND = os.environ.get("GIP_DB_BACKEND", "sqlite").strip().lower()
SQLITE_PATH = Path(os.environ.get("GIP_SQLITE_PATH", str(REPO_ROOT / "gas_data.db")))


class StorageError(Exception):
    """Raised for storage-layer problems (unsupported backend, connection failure)."""


def _connect_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect():
    """Context-managed connection with commit/rollback semantics."""
    if DB_BACKEND == "sqlite":
        conn = _connect_sqlite()
    elif DB_BACKEND == "postgresql":
        raise StorageError(
            "PostgreSQL backend is reserved for a future migration milestone "
            "(see docs/data-ai-forecast-audit.md, recommendation R10)."
        )
    else:
        raise StorageError(f"Unsupported DB backend: {DB_BACKEND!r}")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql: str, params: tuple = ()) -> list:
    """Run a SELECT and return a list of dict rows."""
    with connect() as conn:
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params: tuple = ()):
    """Run a SELECT and return the first row as dict, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    """Run INSERT/UPDATE/DELETE and return rowcount."""
    with connect() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


def execute_many(sql: str, seq) -> int:
    """Run executemany and return rowcount."""
    with connect() as conn:
        cur = conn.executemany(sql, list(seq))
        return cur.rowcount


def scalar(sql: str, params: tuple = ()):
    """Run a SELECT and return the first column of the first row."""
    with connect() as conn:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row is not None else None