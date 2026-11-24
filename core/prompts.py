"""
core/prompts.py - Hermes System Prompts, Rules, and Context Formatter
Defines Hermes's personality as Technical Co-Founder and enforces safety rules.
"""

BASE_HERMES_SYSTEM_PROMPT = """You are Hermes, the user's technical Co-Founder and Senior Dev Partner.
You are direct, concise, practical, and highly capable.
You speak naturally in Hinglish or English (always match the language and tone the user writes in).

Operating Principles:
1. First Step Clarification: Har jawab me pehle step me kya kar raha hu ye clear batana hai.
2. Safety First: Never execute destructive or outgoing actions (like sending emails) without explicit user confirmation.
3. Code Quality: Ensure code is thoroughly reasoned and verified before presenting it.
4. Memory Conscious: Always adhere to the permanent rules and past preferences listed below.
"""

def format_context_prompt(
    rules: list[str],
    facts: list[str],
    summary: str = "",
    current_task: str = "",
) -> str:
    """Build the memory section injected into the system prompt."""
    sections = []

    if rules:
        rule_list = "\n".join(f"- {r}" for r in rules)
        sections.append(f"## PERMANENT OPERATING RULES (Strictly Follow):\n{rule_list}")

    if facts:
        fact_list = "\n".join(f"- {f}" for f in facts)
        sections.append(f"## RELEVANT PAST FACTS & PREFERENCES:\n{fact_list}")

    if summary:
        sections.append(f"## PAST CONVERSATION SUMMARY:\n{summary}")

    if current_task:
        sections.append(f"## CURRENT ACTIVE TASK:\n{current_task}")

    if not sections:
        return ""

    return "\n\n# HIPPOCAMPUS PERSISTENT MEMORY\n" + "\n\n".join(sections)
