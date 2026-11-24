"""
memory/turso_db.py - Tier 2: Turso (libSQL HTTP Pipeline)
Acts as the detailed Diary:
  1. chat_logs - Every single message sent/received
  2. call_logs - Omnidim / voice call transcripts & summaries
  3. summaries - Periodic compressed conversation summaries
"""
import logging
from typing import Any, Optional

import httpx
from utils.helpers import Config, logger

TURSO_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        modality TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",
    "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_logs(session_id, id);",
    """CREATE TABLE IF NOT EXISTS call_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT UNIQUE,
        transcript TEXT NOT NULL,
        summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",
    """CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        summary_text TEXT NOT NULL,
        message_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",
    "CREATE INDEX IF NOT EXISTS idx_summaries_session ON summaries(session_id, id);",
]


class TursoDB:
    """Turso libSQL HTTP client for persistent logs and summaries."""

    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        self.url = (url or Config.TURSO_DATABASE_URL).replace("libsql://", "https://").rstrip("/")
        self.token = token or Config.TURSO_AUTH_TOKEN
        self._http = httpx.AsyncClient(timeout=25.0)

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.token)

    @staticmethod
    def _arg(v: Any) -> dict:
        if v is None:
            return {"type": "null"}
        if isinstance(v, bool):
            return {"type": "integer", "value": str(int(v))}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": str(v)}

    async def execute_pipeline(self, statements: list[tuple[str, list]]) -> list[list]:
        """Execute multiple SQL statements in a single atomic HTTP pipeline."""
        if not self.is_configured:
            logger.warning("[Turso] Database credentials not set; skipping SQL execution.")
            return []

        reqs = [
            {"type": "execute", "stmt": {"sql": s, "args": [self._arg(a) for a in (args or [])]}}
            for s, args in statements
        ]
        reqs.append({"type": "close"})

        try:
            r = await self._http.post(
                f"{self.url}/v2/pipeline",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"requests": reqs},
            )
            r.raise_for_status()
            out = []
            for res in r.json().get("results", []):
                if res.get("type") == "error":
                    raise RuntimeError(res.get("error", {}).get("message", "Unknown SQL error"))
                if res.get("type") == "ok" and res.get("response", {}).get("type") == "execute":
                    result = res["response"]["result"]
                    out.append([[c.get("value") for c in row] for row in result.get("rows", [])])
            return out
        except Exception as e:
            logger.error(f"[Turso] Pipeline error: {e}")
            raise

    async def q(self, sql: str, args: Optional[list] = None) -> list[list]:
        """Execute a single SQL statement and return rows."""
        res = await self.execute_pipeline([(sql, args or [])])
        return res[0] if res else []

    async def init_schema(self):
        """Create tables if they do not exist."""
        if not self.is_configured:
            return
        logger.info("[Turso] Initializing database schema...")
        await self.execute_pipeline([(s, []) for s in TURSO_SCHEMA])
        logger.info("[Turso] Schema ready (chat_logs, call_logs, summaries).")

    # ---------- Chat Logs ----------
    async def log_chat(self, session_id: str, role: str, content: str, modality: str = "text") -> int:
        """Insert a chat message into chat_logs."""
        rows = await self.q(
            "INSERT INTO chat_logs(session_id, role, content, modality) VALUES(?,?,?,?) RETURNING id",
            [session_id, role, content, modality],
        )
        return int(rows[0][0]) if rows else 0

    async def get_recent_logs(self, session_id: str, limit: int = 50) -> list[dict]:
        """Fetch chat logs for session in ascending order."""
        rows = await self.q(
            "SELECT id, role, content, modality, created_at FROM chat_logs WHERE session_id=? "
            "ORDER BY id DESC LIMIT ?",
            [session_id, limit],
        )
        # Reverse to chronological order
        return [
            {"id": r[0], "role": r[1], "content": r[2], "modality": r[3], "created_at": r[4]}
            for r in reversed(rows)
        ]

    async def get_message_count(self, session_id: str) -> int:
        """Count total messages for a session."""
        rows = await self.q(
            "SELECT COUNT(*) FROM chat_logs WHERE session_id=?",
            [session_id],
        )
        return int(rows[0][0]) if rows else 0

    # ---------- Call Logs ----------
    async def log_call(self, call_id: str, transcript: str, summary: Optional[str] = None) -> int:
        """Save a voice/call transcript."""
        rows = await self.q(
            "INSERT INTO call_logs(call_id, transcript, summary) VALUES(?,?,?) RETURNING id",
            [call_id, transcript, summary or ""],
        )
        return int(rows[0][0]) if rows else 0

    # ---------- Summaries ----------
    async def save_summary(self, session_id: str, summary_text: str, message_count: int) -> int:
        """Store compressed summary of older messages."""
        rows = await self.q(
            "INSERT INTO summaries(session_id, summary_text, message_count) VALUES(?,?,?) RETURNING id",
            [session_id, summary_text, message_count],
        )
        return int(rows[0][0]) if rows else 0

    async def get_latest_summary(self, session_id: str) -> Optional[str]:
        """Get the most recent summary for a session."""
        rows = await self.q(
            "SELECT summary_text FROM summaries WHERE session_id=? ORDER BY id DESC LIMIT 1",
            [session_id],
        )
        return rows[0][0] if rows else None
