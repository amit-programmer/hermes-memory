"""
memory/redis_cache.py - Tier 1: Upstash Redis (Hot Context, Current Task, Mode, Turn Locks)
Holds last 20 messages (~2 hours TTL) for instant conversational context.
"""
import json
import logging
from typing import Any, Optional

import httpx
from utils.helpers import Config, logger


class RedisCache:
    """Upstash Redis client for fast hot-context and turn-locking."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        hot_limit: int = 20,
        ttl_seconds: int = 7200,  # 2 hours
    ):
        self.url = (url or Config.UPSTASH_REDIS_REST_URL).rstrip("/")
        self.token = token or Config.UPSTASH_REDIS_REST_TOKEN
        self.hot_limit = hot_limit
        self.ttl = ttl_seconds
        self._http = httpx.AsyncClient(timeout=10.0)

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.token)

    async def _cmd(self, *parts) -> Any:
        """Execute a raw Redis command via Upstash REST endpoint."""
        if not self.is_configured:
            logger.warning("[Redis] Upstash credentials not set; skipping Redis command.")
            return None

        try:
            r = await self._http.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=list(parts),
            )
            r.raise_for_status()
            return r.json().get("result")
        except Exception as e:
            logger.error(f"[Redis] Error executing {parts[0] if parts else 'cmd'}: {e}")
            return None

    async def _pipeline(self, cmds: list[list]) -> list[Any]:
        """Execute a batch of commands via Upstash REST pipeline."""
        if not self.is_configured:
            return []

        try:
            r = await self._http.post(
                f"{self.url}/pipeline",
                headers={"Authorization": f"Bearer {self.token}"},
                json=cmds,
            )
            r.raise_for_status()
            return [x.get("result") for x in r.json()]
        except Exception as e:
            logger.error(f"[Redis] Pipeline error: {e}")
            return []

    # ---------- Turn Lock ----------
    async def acquire_lock(self, session_id: str, timeout: int = 120) -> bool:
        """Lock session so concurrent user messages don't overlap."""
        if not self.is_configured:
            return True
        key = f"lock:{session_id}"
        res = await self._cmd("SET", key, "1", "NX", "EX", timeout)
        return bool(res)

    async def release_lock(self, session_id: str):
        """Release session turn lock."""
        if not self.is_configured:
            return
        await self._cmd("DEL", f"lock:{session_id}")

    # ---------- Hot Context ----------
    async def push_message(self, session_id: str, role: str, content: str):
        """Push a message to the session's hot list and maintain limit and TTL."""
        if not self.is_configured:
            return

        key = f"hot:{session_id}"
        payload = json.dumps({"role": role, "content": content})
        await self._pipeline([
            ["LPUSH", key, payload],
            ["LTRIM", key, 0, self.hot_limit - 1],
            ["EXPIRE", key, self.ttl],
        ])

    async def get_recent_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        """Fetch last messages in chronological order (oldest -> newest)."""
        if not self.is_configured:
            return []

        key = f"hot:{session_id}"
        raw = await self._cmd("LRANGE", key, 0, limit - 1)
        if not raw or not isinstance(raw, list):
            return []

        messages = []
        for item in reversed(raw):
            try:
                messages.append(json.loads(item))
            except Exception:
                continue
        return messages

    # ---------- Mode & Task State ----------
    async def get_mode(self, session_id: str) -> str:
        """Get session modality ('text' or 'voice')."""
        if not self.is_configured:
            return "text"
        val = await self._cmd("GET", f"mode:{session_id}")
        return val if val else "text"

    async def set_mode(self, session_id: str, mode: str):
        """Set session modality."""
        if not self.is_configured:
            return
        await self._cmd("SET", f"mode:{session_id}", mode)

    async def get_current_task(self, session_id: str) -> Optional[str]:
        """Get current active task string."""
        if not self.is_configured:
            return None
        return await self._cmd("GET", f"task:{session_id}")

    async def set_current_task(self, session_id: str, task: str, ttl: int = 7200):
        """Set current active task string."""
        if not self.is_configured:
            return
        await self._cmd("SET", f"task:{session_id}", task, "EX", ttl)

    async def clear_current_task(self, session_id: str):
        """Clear current active task."""
        if not self.is_configured:
            return
        await self._cmd("DEL", f"task:{session_id}")
