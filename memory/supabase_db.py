"""
memory/supabase_db.py - Tier 3: Supabase + pgvector (Permanent Brain)
Stores:
  1. facts - User preferences, technical constraints, facts (status: 'pending' | 'confirmed')
  2. rules - Golden rules & behavioral constraints (pre-seeded with 3 safety rules)
  3. fixes - Lessons learned from past bugs and errors
"""
import logging
from typing import Any, Optional

from supabase import Client, create_client
from utils.helpers import Config, logger

# SQL template provided for user convenience in Supabase SQL editor
SUPABASE_SETUP_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Facts table (status: 'pending' or 'confirmed')
CREATE TABLE IF NOT EXISTS facts (
    id BIGSERIAL PRIMARY KEY,
    fact_text TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    status TEXT DEFAULT 'pending',
    embedding vector(384),
    importance FLOAT DEFAULT 0.7,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Rules table (Safety and operating guidelines)
CREATE TABLE IF NOT EXISTS rules (
    id BIGSERIAL PRIMARY KEY,
    rule_text TEXT UNIQUE NOT NULL,
    embedding vector(384),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fixes table (Solutions to past bugs and errors)
CREATE TABLE IF NOT EXISTS fixes (
    id BIGSERIAL PRIMARY KEY,
    issue TEXT NOT NULL,
    fix_solution TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RPC for vector match on confirmed facts
CREATE OR REPLACE FUNCTION match_facts (
  query_embedding vector(384),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id bigint,
  fact_text text,
  category text,
  importance float,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    facts.id,
    facts.fact_text,
    facts.category,
    facts.importance,
    1 - (facts.embedding <=> query_embedding) AS similarity
  FROM facts
  WHERE facts.status = 'confirmed'
    AND 1 - (facts.embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;
"""

GOLDEN_RULES = [
    "Bina approval ke email SEND mat karna",
    "Code dene se pehle sandbox me test karna hi hai",
    "Har jawab me pehle step me kya kar raha hu ye batana hai",
]


class SupabaseDB:
    """Supabase client for vector-searchable permanent memory with approval workflow."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = (url or Config.SUPABASE_URL).rstrip("/")
        self.key = key or Config.SUPABASE_KEY
        self.client: Optional[Client] = None

        if self.is_configured:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                logger.error(f"[Supabase] Initialization failed: {e}")

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    async def init_schema_and_rules(self, embedder=None):
        """Pre-seed the 3 golden safety rules if not already present."""
        if not self.client:
            logger.warning("[Supabase] Not configured; skipping rule seeding.")
            return

        try:
            for rule_text in GOLDEN_RULES:
                existing = self.client.table("rules").select("id").eq("rule_text", rule_text).execute()
                if not existing.data:
                    emb = None
                    if embedder:
                        emb = await embedder.get_embedding(rule_text)
                    data = {"rule_text": rule_text, "is_active": True}
                    if emb:
                        data["embedding"] = emb
                    self.client.table("rules").insert(data).execute()
                    logger.info(f"[Supabase] Pre-seeded safety rule: '{rule_text}'")
        except Exception as e:
            logger.warning(f"[Supabase] Could not verify/seed rules table: {e}")

    # ---------- Rules ----------
    async def get_active_rules(self) -> list[str]:
        """Fetch all active safety and behavior rules."""
        if not self.client:
            return GOLDEN_RULES.copy()

        try:
            res = self.client.table("rules").select("rule_text").eq("is_active", True).execute()
            if res.data:
                return [r["rule_text"] for r in res.data]
        except Exception as e:
            logger.error(f"[Supabase] Error fetching rules: {e}")

        return GOLDEN_RULES.copy()

    async def add_rule(self, rule_text: str, embedding: Optional[list[float]] = None) -> bool:
        """Add a permanent rule."""
        if not self.client:
            return False
        try:
            data = {"rule_text": rule_text, "is_active": True}
            if embedding:
                data["embedding"] = embedding
            self.client.table("rules").upsert(data, on_conflict="rule_text").execute()
            return True
        except Exception as e:
            logger.error(f"[Supabase] Error adding rule: {e}")
            return False

    # ---------- Facts (with pending/confirmed workflow) ----------
    async def save_fact(
        self,
        fact_text: str,
        category: str = "general",
        status: str = "pending",
        importance: float = 0.7,
        embedding: Optional[list[float]] = None,
    ) -> Optional[int]:
        """Save a new fact. Defaults to 'pending' until approved by user."""
        if not self.client:
            return None

        try:
            data = {
                "fact_text": fact_text,
                "category": category,
                "status": status,
                "importance": importance,
            }
            if embedding:
                data["embedding"] = embedding

            res = self.client.table("facts").insert(data).execute()
            if res.data and len(res.data) > 0:
                return res.data[0].get("id")
        except Exception as e:
            logger.error(f"[Supabase] Error saving fact: {e}")
        return None

    async def confirm_fact(self, fact_id: int) -> bool:
        """Approve/confirm a pending memory so it enters active recall."""
        if not self.client:
            return False
        try:
            res = self.client.table("facts").update({"status": "confirmed"}).eq("id", fact_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"[Supabase] Error confirming fact #{fact_id}: {e}")
            return False

    async def get_pending_facts(self) -> list[dict]:
        """Get all memories currently in pending status awaiting confirmation."""
        if not self.client:
            return []
        try:
            res = self.client.table("facts").select("id, fact_text, category, created_at").eq("status", "pending").order("id", desc=True).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"[Supabase] Error getting pending facts: {e}")
            return []

    async def search_facts(
        self, query_embedding: list[float], query_text: str = "", limit: int = 5, threshold: float = 0.5
    ) -> list[str]:
        """Recall relevant confirmed facts using pgvector RPC or fallback query."""
        if not self.client:
            return []

        # 1. Try pgvector RPC
        if query_embedding and any(query_embedding):
            try:
                rpc_res = self.client.rpc(
                    "match_facts",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": threshold,
                        "match_count": limit,
                    },
                ).execute()
                if rpc_res.data:
                    return [f"[{r.get('category', 'fact')}] {r['fact_text']}" for r in rpc_res.data]
            except Exception as e:
                logger.debug(f"[Supabase] RPC match_facts notice: {e}")

        # 2. Fallback: select confirmed facts
        try:
            res = self.client.table("facts").select("id, fact_text, category, status").eq("status", "confirmed").order("id", desc=True).limit(limit).execute()
            if res.data:
                return [f"[{r.get('category', 'fact')}] {r['fact_text']}" for r in res.data]
        except Exception as e:
            # If status column does not exist yet in existing table, query without status filter
            try:
                res = self.client.table("facts").select("id, fact_text, category").order("id", desc=True).limit(limit).execute()
                if res.data:
                    return [f"[{r.get('category', 'fact')}] {r['fact_text']}" for r in res.data]
            except Exception as ex:
                logger.error(f"[Supabase] Fallback query failed: {ex}")

        return []

    # ---------- Fixes (Lessons Learned) ----------
    async def save_fix(
        self, issue: str, fix_solution: str, embedding: Optional[list[float]] = None
    ) -> Optional[int]:
        """Save a bug fix / mistake lesson learned."""
        if not self.client:
            return None
        try:
            data = {"issue": issue, "fix_solution": fix_solution}
            if embedding:
                data["embedding"] = embedding
            res = self.client.table("fixes").insert(data).execute()
            return res.data[0].get("id") if res.data else None
        except Exception as e:
            logger.error(f"[Supabase] Error saving fix: {e}")
            return None

    async def get_all_memories(self, limit: int = 30) -> list[dict]:
        """Retrieve facts and rules for Telegram /memory command."""
        items = []
        if not self.client:
            for r in GOLDEN_RULES:
                items.append({"type": "rule", "status": "active", "text": r})
            return items

        try:
            rules_res = self.client.table("rules").select("id, rule_text").eq("is_active", True).execute()
            for r in rules_res.data or []:
                items.append({"id": r["id"], "type": "rule", "status": "active", "text": r["rule_text"]})

            facts_res = self.client.table("facts").select("id, fact_text, category, status").order("id", desc=True).limit(limit).execute()
            for f in facts_res.data or []:
                items.append({
                    "id": f["id"],
                    "type": f.get("category", "fact"),
                    "status": f.get("status", "pending"),
                    "text": f["fact_text"],
                })
        except Exception as e:
            logger.error(f"[Supabase] Error listing memories: {e}")

        return items

    async def delete_memory(self, table: str, record_id: int) -> bool:
        """Delete a record by ID."""
        if not self.client:
            return False
        try:
            self.client.table(table).delete().eq("id", record_id).execute()
            return True
        except Exception as e:
            logger.error(f"[Supabase] Error deleting from {table} #{record_id}: {e}")
            return False
