"""
tests/test_redis.py - Tier 1: Upstash Redis Unit Tests
Verifies hot context push/get, mode switching, turn locks, and task persistence.
"""
import pytest
from memory.redis_cache import RedisCache


@pytest.mark.asyncio
async def test_redis_hot_context():
    redis = RedisCache()
    if not redis.is_configured:
        pytest.skip("Upstash Redis not configured in .env")

    session_id = "test_unit_session"
    await redis.push_message(session_id, "user", "Bhai PR banana hai")
    await redis.push_message(session_id, "assistant", "Bhai PR bana raha hu")

    messages = await redis.get_recent_messages(session_id, limit=2)
    assert len(messages) >= 2
    assert messages[-2]["content"] == "Bhai PR banana hai"
    assert messages[-1]["content"] == "Bhai PR bana raha hu"


@pytest.mark.asyncio
async def test_redis_lock():
    redis = RedisCache()
    if not redis.is_configured:
        pytest.skip("Upstash Redis not configured in .env")

    session_id = "test_lock_session"
    # Acquire lock
    locked = await redis.acquire_lock(session_id, timeout=10)
    assert locked is True

    # Second acquire should fail because lock is held
    locked_again = await redis.acquire_lock(session_id, timeout=10)
    assert locked_again is False

    # Release lock
    await redis.release_lock(session_id)
    # Should be able to acquire again
    relocked = await redis.acquire_lock(session_id, timeout=10)
    assert relocked is True
    await redis.release_lock(session_id)


@pytest.mark.asyncio
async def test_redis_mode_and_task():
    redis = RedisCache()
    if not redis.is_configured:
        pytest.skip("Upstash Redis not configured in .env")

    session_id = "test_state_session"
    await redis.set_mode(session_id, "voice")
    mode = await redis.get_mode(session_id)
    assert mode == "voice"

    await redis.set_current_task(session_id, "Build TODO App")
    task = await redis.get_current_task(session_id)
    assert task == "Build TODO App"

    await redis.clear_current_task(session_id)
    cleared = await redis.get_current_task(session_id)
    assert cleared is None
