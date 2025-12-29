from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import datetime as dt
from typing import Optional, Dict, Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  count_total INTEGER DEFAULT 0,
  count_success INTEGER DEFAULT 0,
  count_fallback INTEGER DEFAULT 0,
  count_failed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  input_path TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  file_fingerprint TEXT,
  naming_template TEXT,
  file_size_bytes INTEGER,
  file_created_at TEXT,
  pdf_meta_created_at TEXT,
  chosen_date_prefix TEXT,
  date_source TEXT,
  extraction_method TEXT,
  pages_processed INTEGER,
  extracted_char_count INTEGER,
  final_sender_canonical TEXT,
  final_confidence REAL,
  final_document_type TEXT,
  final_filename_label TEXT,
  final_evidence TEXT,
  final_notes TEXT,
  final_final_filename TEXT,
  final_target_folder TEXT,
  final_target_path TEXT,
  routed_to_fallback INTEGER,
  stage_used INTEGER,
  llm_model_stage1 TEXT,
  llm_model_stage2 TEXT,
  llm_target_folder TEXT,
  llm_is_private INTEGER,
  llm_folder_reason TEXT,
  llm_raw_json_stage1 TEXT,
  llm_raw_json_stage2 TEXT,
  llm_raw_json_final TEXT,
  error TEXT,
  processed_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_run_id ON documents(run_id);
CREATE INDEX IF NOT EXISTS idx_documents_sender ON documents(final_sender_canonical);
CREATE INDEX IF NOT EXISTS idx_documents_fingerprint ON documents(file_fingerprint);

"""


class Database:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._ensure_column("documents", "final_filename_label", "TEXT")
        self._ensure_column("documents", "final_evidence", "TEXT")
        self._ensure_column("documents", "final_notes", "TEXT")
        self._ensure_column("documents", "final_final_filename", "TEXT")
        self._ensure_column("documents", "file_fingerprint", "TEXT")
        self._ensure_column("documents", "llm_target_folder", "TEXT")
        self._ensure_column("documents", "llm_is_private", "INTEGER")
        self._ensure_column("documents", "llm_folder_reason", "TEXT")
        self._ensure_column("documents", "naming_template", "TEXT")
        # Create index after ensuring the column exists (important for old DBs)
        try:
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_fingerprint ON documents(file_fingerprint)"
            )
            self.conn.commit()
        except Exception:
            # Non-fatal: cache lookups still work, just slower
            pass

    def close(self):
        try:
            self.conn.commit()
        finally:
            self.conn.close()

    def _ensure_column(self, table: str, column: str, col_type: str):
        cols = [
            r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        if column not in cols:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            self.conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return dt.datetime.now().isoformat(timespec="seconds")

    def start_run(self, run_id: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, started_at) VALUES (?, ?)",
            (run_id, self._now_iso()),
        )
        self.conn.commit()

    def end_run(self, run_id: str, counts: Dict[str, int]):
        self.conn.execute(
            "UPDATE runs SET ended_at=?, count_total=?, count_success=?, count_fallback=?, count_failed=? WHERE run_id=?",
            (
                self._now_iso(),
                int(counts.get("total", 0)),
                int(counts.get("success", 0)),
                int(counts.get("fallback", 0)),
                int(counts.get("failed", 0)),
                run_id,
            ),
        )
        self.conn.commit()

    def insert_document(self, row: Dict[str, Any]):
        cols = list(row.keys())
        vals = [row[c] for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO documents({','.join(cols)}) VALUES ({placeholders})"
        self.conn.execute(sql, vals)
        self.conn.commit()

    def get_latest_by_fingerprint(self, fp: str) -> Optional[Dict[str, Any]]:
        fp = (fp or "").strip()
        if not fp:
            return None

        row = self.conn.execute(
            """
            SELECT *
            FROM documents
            WHERE file_fingerprint = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (fp,),
        ).fetchone()

        if not row:
            return None

        return dict(row)
