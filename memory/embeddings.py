"""
memory/embeddings.py - Hugging Face Feature Extraction (BAAI/bge-small-en-v1.5, 384-d)
Produces embeddings used for vector similarity search in Supabase.
"""
import asyncio
import logging
from typing import Optional

import httpx
from utils.helpers import Config, logger

DEFAULT_HF_URL = (
    "https://router.huggingface.co/hf-inference/models/BAAI/bge-small-en-v1.5/pipeline/feature-extraction"
)


class EmbeddingsService:
    """Generates 384-dimensional dense vectors using Hugging Face Inference API."""

    def __init__(self, token: Optional[str] = None, url: Optional[str] = None):
        self.token = token or Config.HF_TOKEN
        self.url = url or Config.HF_EMBED_URL or DEFAULT_HF_URL
        self._http = httpx.AsyncClient(timeout=35.0)

    @property
    def is_configured(self) -> bool:
        return bool(self.token)

    async def get_embedding(self, text: str) -> list[float]:
        """Fetch 384-d embedding vector for input text with retry on 503 cold-starts."""
        text = text.strip()
        if not text:
            return [0.0] * 384

        if not self.is_configured:
            logger.warning("[Embeddings] HF_TOKEN not configured; returning empty vector.")
            return [0.0] * 384

        for attempt in range(4):
            try:
                r = await self._http.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"inputs": text[:2000], "options": {"wait_for_model": True}},
                )

                if r.status_code == 503:
                    # Model cold-start on Hugging Face free tier
                    wait_time = 3 * (attempt + 1)
                    logger.info(f"[Embeddings] HF model loading (503), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                r.raise_for_status()
                data = r.json()

                # Unwrap token-level nesting [[...]] to sentence embedding [...]
                while isinstance(data, list) and data and isinstance(data[0], list):
                    data = data[0]

                if isinstance(data, list) and all(isinstance(x, (int, float)) for x in data):
                    return [float(x) for x in data]

                logger.error(f"[Embeddings] Unexpected format from HF: {type(data)}")
                return [0.0] * 384

            except httpx.HTTPStatusError as e:
                logger.error(f"[Embeddings] HTTP error {e.response.status_code}: {e.response.text}")
                if attempt == 3:
                    break
            except Exception as e:
                logger.error(f"[Embeddings] Request error: {e}")
                if attempt == 3:
                    break
                await asyncio.sleep(2)

        return [0.0] * 384
