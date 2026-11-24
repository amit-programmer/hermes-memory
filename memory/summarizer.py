"""
memory/summarizer.py - Background Conversation Summarizer
Runs every ~50 messages to compress conversation history and save into Turso summaries.
Prevents token overflow while preserving critical project context.
"""
import logging
from typing import Awaitable, Callable, Optional

from memory.turso_db import TursoDB
from utils.helpers import logger

SUMMARIZER_PROMPT = """You are a technical context summarizer.
Summarize the following recent conversation history between the user and Hermes.
Focus on:
1. Current active project or task being built
2. Key technical decisions, stack choices, or bugs discussed
3. Pending action items or next steps

Keep the summary concise (under 200 words), direct, and factual.
"""


class ConversationSummarizer:
    """Summarizes chat batches (every 50 messages) and stores in Turso."""

    def __init__(
        self,
        turso: TursoDB,
        llm_fn: Optional[Callable[[list[dict]], Awaitable[str]]] = None,
        interval: int = 50,
    ):
        self.turso = turso
        self.llm = llm_fn
        self.interval = interval

    async def maybe_summarize(self, session_id: str, message_count: int) -> Optional[str]:
        """Triggered when message count reaches a multiple of interval (e.g. 50, 100, 150...)."""
        if not self.llm or not self.turso:
            return None

        if message_count == 0 or message_count % self.interval != 0:
            return None

        logger.info(f"[Summarizer] Triggering summary for session {session_id} at {message_count} messages...")
        try:
            logs = await self.turso.get_recent_logs(session_id, limit=self.interval)
            if not logs:
                return None

            dialogue = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in logs])
            resp = await self.llm([
                {"role": "system", "content": SUMMARIZER_PROMPT},
                {"role": "user", "content": f"CONVERSATION HISTORY:\n\n{dialogue[:8000]}"},
            ])

            summary_text = resp.strip()
            if summary_text:
                await self.turso.save_summary(
                    session_id=session_id,
                    summary_text=summary_text,
                    message_count=message_count,
                )
                logger.info(f"[Summarizer] Successfully saved summary for {session_id}")
                return summary_text
        except Exception as e:
            logger.error(f"[Summarizer] Error generating summary: {e}")

        return None
