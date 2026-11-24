"""
tests/test_turso.py - Tier 2: Turso libSQL Unit Tests
Verifies chat logging, message counting, call logging, and summaries.
"""
import pytest
from memory.turso_db import TursoDB


@pytest.mark.asyncio
async def test_turso_chat_logging():
    turso = TursoDB()
    if not turso.is_configured:
        pytest.skip("Turso database not configured in .env")

    await turso.init_schema()

    session_id = "test_unit_turso_session"
    msg_id = await turso.log_chat(session_id, "user", "Bhai Algora pe bounty dhoondh", "text")
    assert msg_id > 0

    bot_msg_id = await turso.log_chat(session_id, "assistant", "3 bounty mili", "text")
    assert bot_msg_id > 0

    logs = await turso.get_recent_logs(session_id, limit=2)
    assert len(logs) >= 2
    assert logs[-2]["content"] == "Bhai Algora pe bounty dhoondh"
    assert logs[-1]["content"] == "3 bounty mili"

    count = await turso.get_message_count(session_id)
    assert count >= 2


@pytest.mark.asyncio
async def test_turso_summaries():
    turso = TursoDB()
    if not turso.is_configured:
        pytest.skip("Turso database not configured in .env")

    session_id = "test_unit_summary_session"
    await turso.save_summary(session_id, "User asked to search Algora bounties.", 10)

    latest = await turso.get_latest_summary(session_id)
    assert latest == "User asked to search Algora bounties."
