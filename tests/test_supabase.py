"""
tests/test_supabase.py - Tier 3: Supabase Permanent Brain Unit Tests
Verifies facts, rules, pending/confirmed approval workflow, and fixes.
"""
import pytest
from memory.supabase_db import SupabaseDB


@pytest.mark.asyncio
async def test_supabase_rules():
    supabase = SupabaseDB()
    if not supabase.is_configured:
        pytest.skip("Supabase not configured in .env")

    rules = await supabase.get_active_rules()
    assert len(rules) >= 3
    assert any("email SEND" in r for r in rules)
    assert any("sandbox" in r for r in rules)


@pytest.mark.asyncio
async def test_supabase_facts_workflow():
    supabase = SupabaseDB()
    if not supabase.is_configured:
        pytest.skip("Supabase not configured in .env")

    # Step A: Save test (status = pending)
    fact_id = await supabase.save_fact(
        fact_text="User ko Node pasand hai, Python nahi",
        category="preference",
        status="pending",
    )
    assert fact_id is not None

    # Step B: Approve test (status -> confirmed)
    confirmed = await supabase.confirm_fact(fact_id)
    assert confirmed is True

    # Step C: Recall test
    memories = await supabase.get_all_memories(limit=10)
    assert any("User ko Node pasand hai" in m.get("text", "") for m in memories)
