"""
test_connections.py - Level 1 Connection Test ("Kya Taar Judi Hai?")
Tests all 4 external service connections without running the full Hermes bot:
  1. Upstash Redis (Tier 1)
  2. Turso Database (Tier 2)
  3. Supabase + pgvector (Tier 3)
  4. Hugging Face Embeddings (384-d vector)
  5. LLM Provider (Groq / OpenAI / Hermes)
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from utils.helpers import Config, logger
from memory.redis_cache import RedisCache
from memory.turso_db import TursoDB
from memory.supabase_db import SupabaseDB
from memory.embeddings import EmbeddingsService


async def run_connection_tests():
    print("=" * 60)
    print("🔌 HERMES LEVEL 1: CONNECTION TEST")
    print("=" * 60)

    all_passed = True

    # 1. Upstash Redis Test
    print("\n[1/5] Testing Tier 1: Upstash Redis...")
    redis = RedisCache()
    if not redis.is_configured:
        print("  ⚠️ UPSTASH credentials missing in .env (UPSTASH_REDIS_REST_URL / TOKEN)")
        all_passed = False
    else:
        try:
            # Set and read a temporary test key
            await redis._cmd("SET", "test_conn_ping", "pong", "EX", 10)
            res = await redis._cmd("GET", "test_conn_ping")
            if res == "pong":
                print("  ✅ Upstash Redis Connection: PASSED (Read/Write OK)")
            else:
                print(f"  ❌ Upstash Redis: Unexpected response ({res})")
                all_passed = False
        except Exception as e:
            print(f"  ❌ Upstash Redis Error: {e}")
            all_passed = False

    # 2. Turso Test
    print("\n[2/5] Testing Tier 2: Turso libSQL Database...")
    turso = TursoDB()
    if not turso.is_configured:
        print("  ⚠️ TURSO credentials missing in .env (TURSO_DATABASE_URL / TOKEN)")
        all_passed = False
    else:
        try:
            rows = await turso.q("SELECT 1 AS alive")
            if rows and len(rows) > 0 and rows[0][0] == 1:
                print("  ✅ Turso Database Connection: PASSED (HTTP Pipeline OK)")
            else:
                print(f"  ❌ Turso: Unexpected query result ({rows})")
                all_passed = False
        except Exception as e:
            print(f"  ❌ Turso Database Error: {e}")
            all_passed = False

    # 3. Supabase Test
    print("\n[3/5] Testing Tier 3: Supabase (Permanent Brain)...")
    supabase = SupabaseDB()
    if not supabase.is_configured:
        print("  ⚠️ SUPABASE credentials missing in .env (SUPABASE_URL / KEY)")
        all_passed = False
    else:
        try:
            if supabase.client:
                # Query table or rules
                rules = await supabase.get_active_rules()
                print(f"  ✅ Supabase Connection: PASSED ({len(rules)} rules active)")
            else:
                print("  ❌ Supabase client initialization failed")
                all_passed = False
        except Exception as e:
            print(f"  ❌ Supabase Error: {e}")
            all_passed = False

    # 4. Hugging Face Embeddings Test
    print("\n[4/5] Testing Hugging Face Embeddings (BAAI/bge-small-en-v1.5)...")
    embedder = EmbeddingsService()
    if not embedder.is_configured:
        print("  ⚠️ HF_TOKEN missing in .env")
        all_passed = False
    else:
        try:
            sample_text = "Hermes Co-Founder testing connection vector"
            vec = await embedder.get_embedding(sample_text)
            if len(vec) == 384 and any(x != 0.0 for x in vec):
                print(f"  ✅ HF Embeddings: PASSED (Returned 384-dimensional vector)")
            else:
                print(f"  ⚠️ HF Embeddings returned vector length: {len(vec)} (zeros: {all(x == 0.0 for x in vec)})")
                all_passed = False
        except Exception as e:
            print(f"  ❌ HF Embeddings Error: {e}")
            all_passed = False

    # 5. LLM Provider Test
    print("\n[5/5] Testing LLM Provider (Groq / OpenAI / Hermes)...")
    from core.brain import brain
    try:
        reply = await brain.llm_completion([
            {"role": "user", "content": "Reply with only the word: ONLINE"}
        ])
        if reply and "ONLINE" in reply.upper():
            print(f"  ✅ LLM Provider: PASSED (Received '{reply}')")
        else:
            print(f"  ℹ️ LLM response: {reply}")
    except Exception as e:
        print(f"  ❌ LLM Provider Error: {e}")

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL CONNECTIONS VERIFIED! Hermes is ready to run.")
    else:
        print("⚠️ Some connections are unconfigured or failing.")
        print("Fill your actual keys in .env to connect to live cloud services.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_connection_tests())
