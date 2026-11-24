"""
tests/test_brain.py - End-to-End Cognitive Flow & Tools Tests
Verifies sandbox code execution, bounty tools, email drafting guard, and brain pipeline.
"""
import pytest
from core.brain import HermesBrain
from tools.bounty import bounty_hunter
from tools.email import email_tool
from tools.sandbox import sandbox


@pytest.mark.asyncio
async def test_sandbox_tool():
    res = await sandbox.run_python("print('Sandbox verification: 2 + 2 =', 2 + 2)")
    assert res["success"] is True
    assert "2 + 2 = 4" in res["output"]


@pytest.mark.asyncio
async def test_email_safety_lock():
    # 1. Draft email
    draft = email_tool.draft_email(
        to="founder@example.com",
        subject="Pitch Deck Review",
        body="Attached is the updated presentation.",
    )
    assert draft["status"] == "DRAFT_READY"
    assert draft["approval_required"] is True

    # 2. Attempt to send without explicit owner approval -> BLOCKED
    blocked = email_tool.send_email(
        to=draft["to"],
        subject=draft["subject"],
        body=draft["body"],
        approval_token="UNAUTHORIZED",
    )
    assert blocked["status"] == "BLOCKED"

    # 3. Send with explicit approval token -> SENT
    approved = email_tool.send_email(
        to=draft["to"],
        subject=draft["subject"],
        body=draft["body"],
        approval_token="APPROVED_BY_OWNER",
    )
    assert approved["status"] == "SENT"


@pytest.mark.asyncio
async def test_brain_direct_tool_routing():
    brain = HermesBrain()
    reply = await brain.process_message(
        session_id="test_tool_session",
        user_msg="Bhai Algora bounties dhoondh",
        modality="text",
    )
    assert "tool execute kiya" in reply or "bounties" in reply.lower()
