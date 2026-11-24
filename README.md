# ⚡ Hermes Co-Founder Agent

> **Hermes** is an autonomous Technical Co-Founder and Senior Dev Partner powered by a **3-Tier Persistent Memory System (Hippocampus)**, built-in tool verification, and strict operating safety rules.

---

## 🏛️ System Architecture

```
                    TU (Telegram User)
                           │
                           ▼
               ┌───────────────────────┐
               │     HERMES BRAIN      │
               │  FastAPI on HF Space  │
               │                       │
               │  1. Samjhega kya bola │
               │  2. Yaad nikalega     │
               │  3. Tool chalayega    │
               │  4. Jawab dega + Yaad │
               │     save karega       │
               └───────────────────────┘
                 │         │         │
                 ▼         ▼         ▼
             ┌────────┐┌────────┐┌───────────┐
             │UPSTASH ││ TURSO  ││ SUPABASE  │
             │ REDIS  ││ libSQL ││ + pgvector│
             │        ││        ││           │
             │ Tier 1 ││ Tier 2 ││  Tier 3   │
             │  Hot   ││ Diary  ││ Permanent │
             │ Context││  Logs  ││   Brain   │
             └────────┘└────────┘└───────────┘
                 │         │         │
                 └─────────┼─────────┘
                           │
                           ▼
             ┌───────────────────────────┐
             │    BACKGROUND WORKERS     │
             │  Extractor (every 10 msgs)│
             │ Summarizer (every 50 msgs)│
             │   HF Embeddings (384-d)   │
             └───────────────────────────┘
```

---

## 🧠 Hippocampus: 3-Tier Memory Breakdown

| Tier | Technology | Purpose | Data Stored |
|---|---|---|---|
| **Tier 1** | **Upstash Redis** | Instant Hot Context & Turn Locks | Last 20 messages, current task, modality mode, turn concurrency locks (~2h TTL) |
| **Tier 2** | **Turso (libSQL)** | Historical Diary & Summaries | `chat_logs` (full chat history), `call_logs` (transcripts), `summaries` (compressed summaries) |
| **Tier 3** | **Supabase (pgvector)** | Permanent Cognitive Brain | `facts` (preferences & details), `rules` (operating constraints), `fixes` (past lessons) |

### 🛡️ Memory Approval Workflow
- When the background extractor detects a new preference from conversation, it marks it as `status = 'pending'`.
- The user can review pending memories via `/memory` and confirm with `/approve <id>`.
- Only `confirmed` memories are recalled into the active reasoning loop, preventing hallucination or accidental contamination.

---

## 🛠️ Hermes Tools & Safety Rules

### Golden Safety Rules (Pre-seeded)
1. **Rule 1:** `Bina approval ke email SEND mat karna` (Zero unauthorized email dispatch)
2. **Rule 2:** `Code dene se pehle sandbox me test karna hi hai` (Isolated sandbox verification before replying)
3. **Rule 3:** `Har jawab me pehle step me kya kar raha hu ye batana hai` (Always explain the first action step clearly)

### Built-in Tools
- **`tools/sandbox.py`**: Isolated Python and Node.js execution sandbox with timeout and stdout/stderr capture.
- **`tools/bounty.py`**: Algora & GitHub open bounty searcher.
- **`tools/email.py`**: Safe email drafting tool with mandatory user confirmation gate.
- **`tools/github.py`**: Repository inspection and PR description generator.

---

## 📂 Project Directory Structure

```
hermes-memory/
├── main.py                 # FastAPI server (HF Spaces port 7860 + Telegram polling)
├── bot.py                  # Direct Telegram bot standalone runner
├── verify.py               # One-click connection verification script
├── test_connections.py     # Connection tests
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template (no hardcoded secrets)
├── .gitignore              # Ignores .env, .venv, caches, and logs
├── pytest.ini              # Pytest configuration
├── Dockerfile              # Docker container configuration for Hugging Face Spaces
│
├── bot/
│   ├── __init__.py
│   └── telegram_bot.py     # Telegram handlers (/start, /memory, /approve, /rules, etc.)
│
├── core/
│   ├── __init__.py
│   ├── brain.py            # Central cognitive engine coordinating memory & tools
│   └── prompts.py          # Hermes system prompts & memory injection formatters
│
├── memory/
│   ├── __init__.py
│   ├── redis_cache.py      # Tier 1: Upstash Redis hot context
│   ├── turso_db.py         # Tier 2: Turso libSQL diary & logs
│   ├── supabase_db.py      # Tier 3: Supabase permanent brain & pgvector
│   ├── embeddings.py       # Hugging Face BAAI/bge-small-en-v1.5 embeddings
│   ├── extractor.py        # Background fact/rule extractor (every 10 msgs)
│   └── summarizer.py       # Background chat summarizer (every 50 msgs)
│
├── tools/
│   ├── __init__.py
│   ├── sandbox.py          # Subprocess code testing environment
│   ├── bounty.py           # Algora/GitHub bounty finder
│   ├── email.py            # Guarded email drafter
│   └── github.py           # GitHub repo & PR helpers
│
├── tests/
│   ├── test_redis.py       # Tier 1 unit tests
│   ├── test_turso.py       # Tier 2 unit tests
│   ├── test_supabase.py    # Tier 3 unit tests
│   └── test_brain.py       # End-to-end cognitive flow & safety tests
│
└── utils/
    ├── __init__.py
    └── helpers.py          # Unified config, logging, and environment loader
```

---

## 🚀 Setup & Installation

### 1. Clone & Setup Virtual Environment
```bash
git clone https://github.com/<your-username>/hermes-memory.git
cd hermes-memory

python -m venv .venv

# Windows:
.\.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```ini
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_OWNER_ID=your_numeric_chat_id

# Tier 1 - Upstash Redis (REST)
UPSTASH_REDIS_REST_URL=https://xxxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=your_upstash_token

# Tier 2 - Turso libSQL
TURSO_DATABASE_URL=https://xxxx.turso.io
TURSO_AUTH_TOKEN=your_turso_token

# Tier 3 - Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Hugging Face Embeddings
HF_TOKEN=hf_your_token

# LLM Engine (Groq or OpenAI or self-hosted Hermes)
GROQ_API_KEY=your_groq_api_key
# OPENAI_API_KEY=
# HERMES_URL=http://localhost:8080/v1
```

> **Security Note:** All credentials and URLs are read exclusively from `.env`. No credentials or private URLs are ever committed to the repository.

---

## 🗄️ Supabase Database Schema

Run this SQL in your **Supabase SQL Editor** to create the tables and vector match function:

```sql
-- Enable vector extension
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

-- Operating Rules table
CREATE TABLE IF NOT EXISTS rules (
    id BIGSERIAL PRIMARY KEY,
    rule_text TEXT UNIQUE NOT NULL,
    embedding vector(384),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Lessons learned / Fixes table
CREATE TABLE IF NOT EXISTS fixes (
    id BIGSERIAL PRIMARY KEY,
    issue TEXT NOT NULL,
    fix_solution TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector similarity match function for confirmed facts
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
```

---

## 🧪 Testing & Verification

### 1. Connection Check
Run `verify.py` to inspect all cloud credentials and endpoints:
```bash
python verify.py
```

Expected output:
```text
========== HERMES CONNECTION CHECK ==========

1. ENV KEYS:
   TELEGRAM_BOT_TOKEN   : ✅ OK
   OWNER_CHAT_ID        : ✅ OK
   UPSTASH_REDIS        : ✅ OK
   TURSO_DATABASE       : ✅ OK
   SUPABASE_URL         : ✅ OK
   SUPABASE_KEY         : ✅ OK
   HF_TOKEN             : ✅ OK

2. HF EMBEDDING (Hugging Face):
   ✅ CONNECTED - Embedding len: 384

3. UPSTASH REDIS:
   ✅ CONNECTED - Value wapas aaya: PR banana hai

4. TURSO DB:
   ✅ CONNECTED - Row save + read ho gaya: [['1']]

5. SUPABASE:
   ✅ CONNECTED - facts table khul gayi

6. TELEGRAM BOT:
   ✅ CONNECTED - Bot naam: @YourBot

========== CHECK KHATAM ==========
```

### 2. Automated Test Suite
Run the test suite across memory tiers and tools:
```bash
python -m pytest -v
```

---

## 🏃 Running Hermes

### Option A: FastAPI Server (Recommended for HF Spaces & Cloud)
```bash
python main.py
```
- Listens on `http://0.0.0.0:7860`
- Provides health checks (`GET /` and `GET /health`)
- REST chat endpoint (`POST /api/chat`)
- Starts background Telegram bot polling automatically.

### Option B: Standalone Telegram Bot
```bash
python bot.py
```

---

## 📱 Telegram Commands

| Command | Description | Example |
|---|---|---|
| `/start` | Welcome overview & command list | `/start` |
| `/memory` | View pending approvals and confirmed memories | `/memory` |
| `/approve <id>` | Confirm a pending memory into active recall | `/approve 4` |
| `/remember <fact>` | Explicitly record a permanent fact/preference | `/remember Always use TypeScript` |
| `/forget <id>` | Delete a memory by its ID | `/forget 4` |
| `/rules` | View Hermes's active golden safety rules | `/rules` |
| `/bounty [query]` | Search open GitHub & Algora bounties | `/bounty python` |
| `/sandbox <code>` | Run Python code in an isolated sandbox | `/sandbox print(2+2)` |
| `/mode [text\|voice]` | Check or toggle interaction modality | `/mode text` |

---

## 📄 License
MIT License. Free to use, modify, and distribute.
