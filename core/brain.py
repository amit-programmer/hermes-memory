"""
core/brain.py - Central Decision Engine ("Dimaag Ka Logic")
Orchestrates:
  1. Hot Context (Redis)
  2. Permanent Facts, Rules & Fixes (Supabase + pgvector via HF embeddings)
  3. Diary & Summaries (Turso)
  4. Tool Execution (Sandbox, Bounty, Email, GitHub)
  5. LLM Reasoning (Groq / OpenAI / Hermes)
  6. Background Extraction & Summarization
"""
import asyncio
import json
import os
import re
from typing import Any, Optional

import httpx
from core.prompts import BASE_HERMES_SYSTEM_PROMPT, format_context_prompt
from memory.embeddings import EmbeddingsService
from memory.extractor import MemoryExtractor
from memory.redis_cache import RedisCache
from memory.summarizer import ConversationSummarizer
from memory.supabase_db import SupabaseDB
from memory.turso_db import TursoDB
from tools.bounty import bounty_hunter
from tools.email import email_tool
from tools.github import github_tool
from tools.sandbox import sandbox
from utils.helpers import Config, logger


class HermesBrain:
    """The central intelligence coordinating memory tiers, tools, and LLM responses."""

    def __init__(self):
        # Memory Components
        self.redis = RedisCache()
        self.turso = TursoDB()
        self.supabase = SupabaseDB()
        self.embeddings = EmbeddingsService()

        # Background Workers
        self.extractor = MemoryExtractor(
            supabase=self.supabase,
            embeddings=self.embeddings,
            turso=self.turso,
            llm_fn=self.llm_completion,
        )
        self.summarizer = ConversationSummarizer(
            turso=self.turso,
            llm_fn=self.llm_completion,
            interval=50,
        )

        self._http = httpx.AsyncClient(timeout=90.0)

    async def initialize(self):
        """Run startup tasks across all tiers and pre-seed safety rules."""
        logger.info("[Brain] Initializing memory tiers...")
        try:
            await self.turso.init_schema()
        except Exception as e:
            logger.warning(f"[Brain] Turso initialization error: {e}")

        try:
            await self.supabase.init_schema_and_rules(embedder=self.embeddings)
        except Exception as e:
            logger.warning(f"[Brain] Supabase initialization warning: {e}")

        logger.info("[Brain] All systems online.")

    # ---------- LLM Completion Engine ----------
    async def llm_completion(self, messages: list[dict], temperature: float = 0.6) -> str:
        """Universal completion caller supporting Groq, OpenAI, and Hermes/OpenAI-compatible APIs."""
        # 1. Try Groq if configured
        if Config.GROQ_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 1500,
                }
                r = await self._http.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
                logger.warning(f"[Brain] Groq returned status {r.status_code}: {r.text}")
            except Exception as e:
                logger.error(f"[Brain] Groq error: {e}")

        # 2. Try Hermes / Custom OpenAI-compatible endpoint
        if Config.HERMES_URL:
            try:
                endpoint = f"{Config.HERMES_URL}/chat/completions"
                headers = {"Content-Type": "application/json"}
                if Config.OPENAI_API_KEY:
                    headers["Authorization"] = f"Bearer {Config.OPENAI_API_KEY}"

                payload = {
                    "model": Config.HERMES_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 1500,
                }
                r = await self._http.post(endpoint, headers=headers, json=payload)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"[Brain] Hermes URL {Config.HERMES_URL} error: {e}")

        # Fallback response if no LLM responded
        return "Bhai, LLM API connect nahi ho paayi. Kripya .env me GROQ_API_KEY ya HERMES_URL verify karein."

    # ---------- Tool Detection & Execution ----------
    async def _handle_tool_intent(self, user_msg: str) -> Optional[str]:
        """Check if message matches a direct tool trigger."""
        msg_lower = user_msg.lower().strip()

        # 1. Bounty hunter trigger
        if "bounty" in msg_lower or "bounties" in msg_lower:
            query = "python"
            if "react" in msg_lower:
                query = "react"
            elif "node" in msg_lower:
                query = "node"
            elif "rust" in msg_lower:
                query = "rust"
            logger.info(f"[Brain] Triggering Bounty Hunter for '{query}'...")
            return await bounty_hunter.get_summary_formatted(query=query)

        # 2. Email drafting intent
        if ("email" in msg_lower and ("draft" in msg_lower or "likh" in msg_lower or "bhej" in msg_lower)) or msg_lower.startswith("/email"):
            draft = email_tool.draft_email(
                to="recipient@example.com",
                subject="Follow-up from Hermes Co-Founder",
                body=f"Draft based on request: {user_msg}",
            )
            return (
                f"📝 **Email Draft Prepared** (Safety Lock Active):\n\n"
                f"**To:** `{draft['to']}`\n"
                f"**Subject:** {draft['subject']}\n\n"
                f"**Body:**\n{draft['body']}\n\n"
                f"⚠️ *{draft['instructions']}*"
            )

        return None

    # ---------- Core Message Processing Pipeline ----------
    async def process_message(self, session_id: str, user_msg: str, modality: str = "text") -> str:
        """Full cognitive lifecycle:
        Lock -> Hot Context -> Vector Recall -> Tool Check -> Generation -> Bg Logging/Extraction
        """
        # Step 1: Turn lock to prevent race conditions
        if not await self.redis.acquire_lock(session_id, timeout=120):
            return "⏳ Pichla reply abhi process ho raha hai, ek second rukna..."

        try:
            # Step 2: Direct tool shortcuts (e.g. bounty summary or email draft)
            tool_direct_res = await self._handle_tool_intent(user_msg)
            if tool_direct_res:
                reply = f"Pehle step me maine tool execute kiya:\n\n{tool_direct_res}"
                asyncio.create_task(self._after_reply(session_id, user_msg, reply, modality))
                return reply

            # Step 3: Recall Memory across Tiers
            # A) Redis Hot Context
            hot_messages = await self.redis.get_recent_messages(session_id, limit=15)

            # B) Vector Embeddings for User Query
            query_embedding = await self.embeddings.get_embedding(user_msg)

            # C) Supabase Permanent Rules & Facts
            rules, facts = await asyncio.gather(
                self.supabase.get_active_rules(),
                self.supabase.search_facts(query_embedding=query_embedding, query_text=user_msg, limit=4),
            )

            # D) Latest Summary from Turso
            latest_summary = await self.turso.get_latest_summary(session_id) or ""
            current_task = await self.redis.get_current_task(session_id) or ""

            # Step 4: Construct Enriched Prompt
            memory_section = format_context_prompt(
                rules=rules,
                facts=facts,
                summary=latest_summary,
                current_task=current_task,
            )
            system_prompt = BASE_HERMES_SYSTEM_PROMPT + memory_section

            dialogue = [{"role": "system", "content": system_prompt}]
            dialogue.extend(hot_messages)
            dialogue.append({"role": "user", "content": user_msg})

            # Step 5: Call LLM
            logger.info(f"[Brain] Querying LLM with {len(dialogue)} messages (injected {len(rules)} rules, {len(facts)} facts)...")
            reply = await self.llm_completion(dialogue)

            # Step 6: Code sandbox verification rule:
            # "Code dene se pehle sandbox me test karna hi hai"
            python_code_blocks = re.findall(r"```python\s*(.+?)```", reply, re.DOTALL)
            if python_code_blocks:
                logger.info("[Brain] Code detected in reply; testing in isolated sandbox...")
                test_code = python_code_blocks[0]
                sandbox_res = await sandbox.run_python(test_code, timeout=8)
                if sandbox_res["success"]:
                    reply += f"\n\n*(✅ Sandbox verified: executed cleanly in {sandbox_res['duration_sec']}s)*"
                else:
                    reply += f"\n\n*(⚠️ Sandbox warning: {sandbox_res['error'][:200]})*"

            # Step 7: Background Logging, Hot Push, and Learning
            asyncio.create_task(self._after_reply(session_id, user_msg, reply, modality))
            return reply

        finally:
            await self.redis.release_lock(session_id)

    # ---------- Background Persistence & Extraction ----------
    async def _after_reply(self, session_id: str, user_msg: str, reply: str, modality: str):
        """Asynchronously update Redis hot cache, log to Turso, and trigger learning workers."""
        try:
            # 1. Update hot cache
            await self.redis.push_message(session_id, "user", user_msg)
            await self.redis.push_message(session_id, "assistant", reply)

            # 2. Log to Turso Diary
            await self.turso.log_chat(session_id, "user", user_msg, modality)
            msg_id = await self.turso.log_chat(session_id, "assistant", reply, modality)

            # 3. Check message counts for triggers
            total_count = await self.turso.get_message_count(session_id)

            # 4. Extractor: learn facts / rules from this turn
            await self.extractor.extract_from_turn(user_msg, reply)

            # 5. Batch extraction every 10 messages
            await self.extractor.maybe_run_batch_extract(session_id, total_count)

            # 6. Summarizer every 50 messages
            await self.summarizer.maybe_summarize(session_id, total_count)

        except Exception as e:
            logger.error(f"[Brain] Background persistence error: {e}")


# Singleton instance
brain = HermesBrain()
