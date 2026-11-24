"""
utils/helpers.py - Configuration management, logging, and common utilities
"""
import json
import logging
import os
import sys
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hermes")


def get_env(key: str, default: Optional[str] = None, alt_keys: Optional[list[str]] = None) -> str:
    """Fetch an environment variable checking alternate legacy/standard names."""
    val = os.environ.get(key)
    if val is not None and val.strip():
        return val.strip()

    if alt_keys:
        for alt in alt_keys:
            val = os.environ.get(alt)
            if val is not None and val.strip():
                return val.strip()

    if default is not None:
        return default
    return ""


class Config:
    """Centralized configuration with fallback compatibility."""

    # Telegram
    TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", alt_keys=["TELEGRAM_TOKEN"])
    TELEGRAM_OWNER_ID = get_env("TELEGRAM_OWNER_ID", alt_keys=["OWNER_CHAT_ID"])

    # Tier 1 - Upstash Redis
    UPSTASH_REDIS_REST_URL = get_env("UPSTASH_REDIS_REST_URL", alt_keys=["UPSTASH_URL"])
    UPSTASH_REDIS_REST_TOKEN = get_env("UPSTASH_REDIS_REST_TOKEN", alt_keys=["UPSTASH_TOKEN"])

    # Tier 2 - Turso libSQL
    TURSO_DATABASE_URL = get_env("TURSO_DATABASE_URL", alt_keys=["TURSO_URL"]).replace("libsql://", "https://").rstrip("/")
    TURSO_AUTH_TOKEN = get_env("TURSO_AUTH_TOKEN", alt_keys=["TURSO_TOKEN"])

    # Tier 3 - Supabase
    SUPABASE_URL = get_env("SUPABASE_URL").rstrip("/")
    SUPABASE_KEY = get_env("SUPABASE_KEY")

    # Embeddings
    HF_TOKEN = get_env("HF_TOKEN")
    HF_EMBED_URL = get_env(
        "HF_EMBED_URL",
        default="https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5/pipeline/feature-extraction",
    )

    # LLM Provider
    GROQ_API_KEY = get_env("GROQ_API_KEY")
    OPENAI_API_KEY = get_env("OPENAI_API_KEY")
    HERMES_URL = get_env("HERMES_URL").rstrip("/")
    HERMES_MODEL = get_env("HERMES_MODEL", default="hermes")

    # Server
    PORT = int(get_env("PORT", default="7860"))
    HOST = get_env("HOST", default="0.0.0.0")

    @classmethod
    def check_status(cls) -> dict[str, bool]:
        """Check which services are configured."""
        return {
            "telegram": bool(cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_OWNER_ID),
            "upstash_redis": bool(cls.UPSTASH_REDIS_REST_URL and cls.UPSTASH_REDIS_REST_TOKEN),
            "turso": bool(cls.TURSO_DATABASE_URL and cls.TURSO_AUTH_TOKEN),
            "supabase": bool(cls.SUPABASE_URL and cls.SUPABASE_KEY),
            "hf_embeddings": bool(cls.HF_TOKEN),
            "llm": bool(cls.GROQ_API_KEY or cls.OPENAI_API_KEY or cls.HERMES_URL),
        }


def safe_json_loads(data: str, default: Any = None) -> Any:
    """Safely decode JSON string."""
    try:
        return json.loads(data)
    except Exception:
        return default
