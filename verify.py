"""
verify.py - Hermes Connection Check
Run this script to test all external connections:
  1. ENV Keys
  2. HF Embedding (Hugging Face)
  3. Upstash Redis
  4. Turso Database
  5. Supabase
  6. Telegram Bot
"""
import asyncio
import os
import re
import sys
from dotenv import load_dotenv
import httpx

load_dotenv()


def get_val(*keys) -> str:
    """Check multiple environment variable name aliases."""
    for k in keys:
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    return ""


# Extract configuration
TELEGRAM_TOKEN = get_val("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TELEGRAM_TOKEN")
OWNER_CHAT_ID = get_val("TELEGRAM_OWNER_ID", "OWNER_CHAT_ID")
TURSO_URL = get_val("TURSO_DATABASE_URL", "TURSO_URL").replace("libsql://", "https://").rstrip("/")
TURSO_TOKEN = get_val("TURSO_AUTH_TOKEN", "TURSO_TOKEN")
UPSTASH_URL = get_val("UPSTASH_REDIS_REST_URL", "UPSTASH_URL").rstrip("/")
UPSTASH_TOKEN = get_val("UPSTASH_REDIS_REST_TOKEN", "UPSTASH_TOKEN")
HF_TOKEN = get_val("HF_TOKEN")
HF_EMBED_URL = get_val("HF_EMBED_URL") or "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5/pipeline/feature-extraction"
SUPABASE_URL = get_val("SUPABASE_URL")
SUPABASE_KEY = get_val("SUPABASE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_DB_URL = get_val("SUPABASE_DATABASE_URL")

# Auto-extract Supabase REST URL if database URL is provided
if not SUPABASE_URL and SUPABASE_DB_URL:
    match = re.search(r"@db\.([a-z0-9_-]+)\.supabase\.co", SUPABASE_DB_URL)
    if match:
        SUPABASE_URL = f"https://{match.group(1)}.supabase.co"


async def main():
    print("\n========== HERMES CONNECTION CHECK ==========\n")

    # 1. ENV KEYS CHECK
    print("1. ENV KEYS:")
    keys_status = {
        "TELEGRAM_BOT_TOKEN": bool(TELEGRAM_TOKEN),
        "OWNER_CHAT_ID": bool(OWNER_CHAT_ID),
        "UPSTASH_REDIS": bool(UPSTASH_URL and UPSTASH_TOKEN),
        "TURSO_DATABASE": bool(TURSO_URL and TURSO_TOKEN),
        "SUPABASE_URL": bool(SUPABASE_URL),
        "SUPABASE_KEY": bool(SUPABASE_KEY),
        "HF_TOKEN": bool(HF_TOKEN),
    }

    for name, ok in keys_status.items():
        sym = "✅ OK" if ok else "❌ MISSING"
        print(f"   {name:<20} : {sym}")

    # 2. HF EMBEDDINGS (Hugging Face)
    print("\n2. HF EMBEDDING (Hugging Face):")
    if not HF_TOKEN:
        print("   ❌ SKIPPED - HF_TOKEN not set in .env")
    else:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                r = await client.post(
                    HF_EMBED_URL,
                    headers={"Authorization": f"Bearer {HF_TOKEN}"},
                    json={"inputs": "Hermes connection test", "options": {"wait_for_model": True}},
                )
                if r.status_code == 200:
                    data = r.json()
                    while isinstance(data, list) and data and isinstance(data[0], list):
                        data = data[0]
                    emb_len = len(data) if isinstance(data, list) else 0
                    print(f"   ✅ CONNECTED - Embedding len: {emb_len}")
                elif r.status_code == 503:
                    print("   ⚠️ MODEL LOADING (503) - HF cold start, try again in 10s")
                else:
                    print(f"   ❌ ERROR {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"   ❌ FAILED - {e}")

    # 3. UPSTASH REDIS
    print("\n3. UPSTASH REDIS:")
    if not (UPSTASH_URL and UPSTASH_TOKEN):
        print("   ❌ SKIPPED - UPSTASH credentials missing in .env")
    else:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Write test value
                w = await client.post(
                    UPSTASH_URL,
                    headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
                    json=["SET", "test_hermes", "PR banana hai", "EX", "60"],
                )
                w.raise_for_status()

                # Read test value
                r = await client.post(
                    UPSTASH_URL,
                    headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
                    json=["GET", "test_hermes"],
                )
                r.raise_for_status()
                val = r.json().get("result")
                if val == "PR banana hai":
                    print(f"   ✅ CONNECTED - Value wapas aaya: {val}")
                else:
                    print(f"   ⚠️ Connected but unexpected value: {val}")
            except Exception as e:
                print(f"   ❌ FAILED - {e}")

    # 4. TURSO DB
    print("\n4. TURSO DB:")
    if not (TURSO_URL and TURSO_TOKEN):
        print("   ❌ SKIPPED - TURSO credentials missing in .env")
    else:
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                pipeline_req = {
                    "requests": [
                        {"type": "execute", "stmt": {"sql": "SELECT 1"}},
                        {"type": "close"},
                    ]
                }
                r = await client.post(
                    f"{TURSO_URL}/v2/pipeline",
                    headers={"Authorization": f"Bearer {TURSO_TOKEN}"},
                    json=pipeline_req,
                )
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                if results and results[0].get("type") == "ok":
                    rows = [[c.get("value") for c in row] for row in results[0]["response"]["result"]["rows"]]
                    print(f"   ✅ CONNECTED - Row save + read ho gaya: {rows}")
                else:
                    print(f"   ❌ TURSO QUERY ERROR: {data}")
            except Exception as e:
                print(f"   ❌ FAILED - {e}")

    # 5. SUPABASE
    print("\n5. SUPABASE:")
    if not SUPABASE_URL:
        print("   ❌ SKIPPED - SUPABASE_URL missing in .env")
    elif not SUPABASE_KEY:
        print(f"   ⚠️ URL DETECTED: {SUPABASE_URL}")
        print("   ❌ MISSING SUPABASE_KEY: Add SUPABASE_KEY (anon public key) from Supabase Dashboard -> Project Settings -> API")
    else:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # Query facts or table health
                r = await client.get(
                    f"{SUPABASE_URL}/rest/v1/facts?select=id&limit=1",
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                    },
                )
                if r.status_code in (200, 206):
                    print("   ✅ CONNECTED - facts table khul gayi")
                elif r.status_code == 404 or "relation \"public.facts\" does not exist" in r.text:
                    print("   ⚠️ CONNECTED TO SUPABASE - but 'facts' table not created yet.")
                    print("      (Run the provided SQL in Supabase SQL editor to create tables)")
                else:
                    print(f"   ⚠️ Status {r.status_code}: {r.text[:200]}")
            except Exception as e:
                print(f"   ❌ FAILED - {e}")

    # 6. TELEGRAM BOT
    print("\n6. TELEGRAM BOT:")
    if not TELEGRAM_TOKEN:
        print("   ❌ SKIPPED - TELEGRAM_BOT_TOKEN / BOT_TOKEN missing in .env")
    else:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                r = await client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe")
                if r.status_code == 200 and r.json().get("ok"):
                    bot_user = r.json().get("result", {}).get("username", "unknown")
                    print(f"   ✅ CONNECTED - Bot naam: @{bot_user}")
                else:
                    print(f"   ❌ INVALID TOKEN - Telegram error: {r.text[:200]}")
            except Exception as e:
                print(f"   ❌ FAILED - {e}")

    print("\n========== CHECK KHATAM ==========\n")


if __name__ == "__main__":
    asyncio.run(main())
