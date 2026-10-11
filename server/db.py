"""SQLite persistence for the web UI (jobs + discovered outputs).

WAL mode, stdlib sqlite3 only. Every access goes through a module-level lock:
the event loop thread and the threadpool indexer both write here, and each
individual operation is tiny.
"""

import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from server import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    workflow    TEXT NOT NULL,
    prompt      TEXT,
    params_json TEXT NOT NULL,
    argv_json   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    heavy       INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL,
    started_at  REAL,
    ended_at    REAL,
    exit_code   INTEGER,
    error       TEXT,
    progress    REAL NOT NULL DEFAULT 0,
    log_path    TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS outputs (
    path     TEXT PRIMARY KEY,
    job_id   TEXT,
    workflow TEXT,
    kind     TEXT NOT NULL,
    mtime    REAL NOT NULL,
    size     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outputs_job ON outputs(job_id);
CREATE INDEX IF NOT EXISTS idx_outputs_mtime ON outputs(mtime DESC);
"""

# Mutable statuses the worker acts on; terminal statuses are final (except
# retry, which re-queues from blocked/error/canceled/interrupted).
ACTIVE_STATUSES = ("pending", "running")
TERMINAL_STATUSES = ("complete", "error", "canceled", "interrupted", "blocked_load")

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def init() -> None:
    global _conn
    paths.ensure_dirs()
    _conn = sqlite3.connect(paths.DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA synchronous=NORMAL")
    _conn.executescript(_SCHEMA)
    _conn.commit()


def _connection() -> sqlite3.Connection:
    if _conn is None:
        init()
    assert _conn is not None
    return _conn


def _execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        conn = _connection()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def _query(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    with _lock:
        return _connection().execute(sql, params).fetchall()


def reset_for_tests(db_path) -> None:
    """Point the module connection at an isolated database (tests only)."""
    global _conn
    if _conn is not None:
        _conn.close()
    paths.DB_PATH = db_path
    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(_SCHEMA)
    _conn.commit()


def close_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


# ------------------------------------------------------------------ jobs ----

def insert_job(job: Dict[str, Any]) -> None:
    _execute(
        """INSERT INTO jobs (id, workflow, prompt, params_json, argv_json, status, heavy, created_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (
            job["id"], job["workflow"], job["prompt"],
            json.dumps(job["params"]), json.dumps(job["argv"]),
            1 if job.get("heavy", True) else 0, time.time(),
        ),
    )


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    rows = _query("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return dict(rows[0]) if rows else None


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    _execute(f"UPDATE jobs SET {columns} WHERE id = ?", (*fields.values(), job_id))


def set_job_status(job_id: str, status: str, **extra: Any) -> None:
    update_job(job_id, status=status, **extra)


def list_jobs(statuses: Optional[tuple] = None, limit: int = 30) -> List[Dict[str, Any]]:
    if statuses:
        marks = ",".join("?" for _ in statuses)
        rows = _query(
            f"SELECT * FROM jobs WHERE status IN ({marks}) ORDER BY created_at DESC LIMIT ?",
            (*statuses, limit),
        )
    else:
        rows = _query("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    return [dict(row) for row in rows]


def pending_jobs() -> List[Dict[str, Any]]:
    return list_jobs(("pending",), limit=1000)


def mark_orphans_interrupted() -> int:
    """On startup: any 'running' row belongs to a dead process."""
    cur = _execute("UPDATE jobs SET status = 'interrupted', ended_at = ? WHERE status = 'running'", (time.time(),))
    return cur.rowcount


def job_params(job: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(job["params_json"])


def job_argv(job: Dict[str, Any]) -> List[str]:
    return json.loads(job["argv_json"])


# --------------------------------------------------------------- outputs ----

def upsert_output(path: str, kind: str, mtime: float, size: int,
                  job_id: Optional[str] = None, workflow: Optional[str] = None) -> None:
    _execute(
        """INSERT INTO outputs (path, kind, mtime, size, job_id, workflow)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(path) DO UPDATE SET kind = excluded.kind,
                                           mtime = excluded.mtime,
                                           size = excluded.size,
                                           job_id = COALESCE(excluded.job_id, outputs.job_id),
                                           workflow = COALESCE(excluded.workflow, outputs.workflow)""",
        (path, kind, mtime, size, job_id, workflow),
    )


def upsert_many(rows: List[tuple]) -> None:
    """Batch upsert [(path, kind, mtime, size), ...] in ONE transaction."""
    if not rows:
        return
    with _lock:
        conn = _connection()
        try:
            conn.executemany(
                """INSERT INTO outputs (path, kind, mtime, size)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET kind = excluded.kind,
                                                   mtime = excluded.mtime,
                                                   size = excluded.size""",
                rows,
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise


def outputs_missing_media(limit: int) -> List[str]:
    """Indexed paths whose thumbnail/waveform cache entry is absent.

    Waveforms are generated for PCM .wav only (stdlib `wave` limitation) —
    mp3/ogg/flac intentionally keep the player+icon fallback.
    """
    from server import assets as media_assets

    rows = _query(
        "SELECT path, kind FROM outputs WHERE kind IN ('image', 'audio') ORDER BY mtime DESC",
    )
    missing: List[str] = []
    for row in rows:
        if limit and len(missing) >= limit:
            break
        path = paths.REPO_ROOT / row["path"]
        if row["kind"] == "image":
            if media_assets.thumbnail(path, create=False) is None:
                missing.append(row["path"])
        elif path.suffix.lower() == ".wav":
            if media_assets.waveform(path, create=False) is None:
                missing.append(row["path"])
    return missing


def prune_outputs(existing: set) -> None:
    """Remove rows whose file disappeared (existing = set of live paths)."""
    rows = _query("SELECT path FROM outputs")
    dead = [row["path"] for row in rows if row["path"] not in existing]
    for path in dead:
        _execute("DELETE FROM outputs WHERE path = ?", (path,))


def link_recent_outputs(job_id: str, workflow: str, since: float) -> int:
    """Attach unlinked outputs created after `since` to the finished job."""
    cur = _execute(
        """UPDATE outputs SET job_id = ?, workflow = ?
           WHERE mtime >= ? AND (job_id IS NULL OR job_id = ?)""",
        (job_id, workflow, since - 1.0, job_id),
    )
    return cur.rowcount


def search_outputs(kind: Optional[str] = None, workflow: Optional[str] = None,
                   query: str = "", limit: int = 60, offset: int = 0) -> List[Dict[str, Any]]:
    clauses, params = ["1 = 1"], []
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if workflow:
        clauses.append("workflow = ? OR path LIKE ?")
        params.extend([workflow, f"%/{workflow}/%"])
    if query:
        clauses.append("path LIKE ?")
        params.append(f"%{query}%")
    where = " AND ".join(clauses)
    rows = _query(
        f"SELECT * FROM outputs WHERE {where} ORDER BY mtime DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return [dict(row) for row in rows]


def count_outputs(kind: Optional[str] = None, query: str = "") -> int:
    clauses, params = ["1 = 1"], []
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if query:
        clauses.append("path LIKE ?")
        params.append(f"%{query}%")
    rows = _query(f"SELECT COUNT(*) AS n FROM outputs WHERE {' AND '.join(clauses)}", tuple(params))
    return int(rows[0]["n"])


def outputs_for_job(job_id: str) -> List[Dict[str, Any]]:
    rows = _query("SELECT * FROM outputs WHERE job_id = ? ORDER BY mtime ASC", (job_id,))
    return [dict(row) for row in rows]
