"""
memory/extractor.py - Background Extractor Worker
Analyzes chat turns to extract permanent facts, rules, and fixes, then saves them to Supabase.
"""
import logging
import re
from typing import Awaitable, Callable, Optional

from memory.embeddings import EmbeddingsService
from memory.supabase_db import SupabaseDB
from memory.turso_db import TursoDB
from utils.helpers import logger

EXTRACTOR_SYSTEM_PROMPT = """Analyze this conversation turn. Did the user state a NEW permanent preference, \
technical constraint, project detail, rule, or bug fix?
Ignore chit-chat, simple questions, acknowledgements, and one-off requests.
If YES, reply with ONE concise statement prefixed by its category in brackets, one of:
[preference] - User's tech/workflow preference (e.g., "[preference] Prefers TypeScript over JavaScript")
[rule] - Operating rule (e.g., "[rule] Never send emails without explicit approval")
[fix] - Bug solution or lesson learned (e.g., "[fix] When port 7860 is blocked, verify Docker CMD")
[fact] - Permanent project fact (e.g., "[fact] Hermes runs on Hugging Face Spaces")

If NO new rule, preference, or fact was stated, reply exactly: NONE
"""


class MemoryExtractor:
    """Extracts long-term facts, rules, and fixes from dialogue and saves them in Supabase."""

    def __init__(
        self,
        supabase: SupabaseDB,
        embeddings: EmbeddingsService,
        turso: Optional[TursoDB] = None,
        llm_fn: Optional[Callable[[list[dict]], Awaitable[str]]] = None,
    ):
        self.supabase = supabase
        self.embeddings = embeddings
        self.turso = turso
        self.llm = llm_fn

    async def extract_from_turn(self, user_msg: str, assistant_reply: str) -> Optional[dict]:
        """Check a single conversation turn and extract memory if present."""
        if not self.llm or len(user_msg.strip()) < 12:
            return None

        prompt = f"USER: {user_msg[:1200]}\nASSISTANT: {assistant_reply[:1200]}"
        try:
            resp = await self.llm([
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            text = resp.strip()
            if not text or text.upper().startswith("NONE"):
                return None

            match = re.match(r"^\[(\w+)\]\s*(.+)", text, re.DOTALL)
            if match:
                category, fact_text = match.group(1).lower(), match.group(2).strip()
            else:
                category, fact_text = "fact", text

            # Generate embedding
            emb = await self.embeddings.get_embedding(fact_text)

            # Route to appropriate Supabase table
            if category == "rule":
                await self.supabase.add_rule(fact_text, embedding=emb)
                logger.info(f"[Extractor] Saved new rule: '{fact_text}'")
            elif category == "fix":
                await self.supabase.save_fix(issue=user_msg[:200], fix_solution=fact_text, embedding=emb)
                logger.info(f"[Extractor] Saved new fix: '{fact_text}'")
            else:
                fact_id = await self.supabase.save_fact(
                    fact_text=fact_text, category=category, status="pending", embedding=emb
                )
                logger.info(f"[Extractor] Saved new pending fact #{fact_id} [{category}]: '{fact_text}'")

            return {"category": category, "fact": fact_text, "status": "pending"}
        except Exception as e:
            logger.error(f"[Extractor] Extraction error: {e}")
            return None

    async def maybe_run_batch_extract(self, session_id: str, current_count: int):
        """Called every 10 messages to inspect recent conversation turns from Turso."""
        if not self.turso or current_count % 10 != 0:
            return

        try:
            recent_logs = await self.turso.get_recent_logs(session_id, limit=10)
            if len(recent_logs) < 2:
                return

            logger.info(f"[Extractor] Running 10-message batch check for session {session_id}...")
            # Pair consecutive user and assistant messages
            for i in range(len(recent_logs) - 1):
                if recent_logs[i]["role"] == "user" and recent_logs[i + 1]["role"] == "assistant":
                    await self.extract_from_turn(recent_logs[i]["content"], recent_logs[i + 1]["content"])
        except Exception as e:
            logger.error(f"[Extractor] Batch extraction error: {e}")
