"""
bot/telegram_bot.py - Telegram Interface for Hermes Co-Founder Agent
Commands: /start, /memory, /remember, /forget, /rules, /bounty, /sandbox, /mode
Routes regular chat to core.brain.
"""
import asyncio
import os
from typing import Optional

from core.brain import brain
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from tools.bounty import bounty_hunter
from tools.sandbox import sandbox
from utils.helpers import Config, logger

OWNER_ID_STR = Config.TELEGRAM_OWNER_ID
OWNER_ID = int(OWNER_ID_STR) if (OWNER_ID_STR.isdigit() or (OWNER_ID_STR.startswith("-") and OWNER_ID_STR[1:].isdigit())) else 0


def owner_only(fn):
    """Ensure only the authorized owner can execute bot commands and interact."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not update.effective_chat:
            return
        if OWNER_ID and update.effective_chat.id != OWNER_ID:
            logger.warning(f"[Bot] Unauthorized access attempt from chat_id: {update.effective_chat.id}")
            return  # Silently ignore unauthorized users
        return await fn(update, ctx)
    return wrapper


async def reply_long(update: Update, text: str):
    """Split replies into chunks under Telegram's 4096 char limit."""
    if not text:
        return
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i : i + 4000])


# ---------- Command Handlers ----------
@owner_only
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "⚡ **Hermes Co-Founder Agent is Ready!**\n\n"
        "Main tera Technical Co-Founder aur Senior Dev Partner hu.\n\n"
        "**Available Commands:**\n"
        "• `/memory` - Dimaag me stored facts aur rules dekho\n"
        "• `/remember <fact>` - Koi zaroori fact ya rule yaad karwao\n"
        "• `/forget <id>` - Purani memory delete karo\n"
        "• `/rules` - Hermes ke golden operating rules\n"
        "• `/bounty [query]` - Open GitHub/Algora bounties dhoondho\n"
        "• `/sandbox <code>` - Isolated sandbox me Python code test karo\n"
        "• `/mode [text|voice]` - Mode check ya change karo\n\n"
        "Direct message likh ke baat shuru kar sakta hai bhai!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


@owner_only
async def cmd_memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    memories = await brain.supabase.get_all_memories(limit=30)
    if not memories:
        return await update.message.reply_text("Abhi dimaag me koi permanent memory nahi hai.")

    pending = [m for m in memories if m.get("status") == "pending"]
    confirmed = [m for m in memories if m.get("status") != "pending"]

    lines = ["🧠 **Hermes Permanent Memory (Hippocampus):**\n"]

    if pending:
        lines.append("⏳ **Pending Approvals (Nayi Yaadein Mili):**")
        for m in pending:
            lines.append(f"• `#{m.get('id')}` [{m.get('type')}] {m.get('text')} -> Approve karne ke liye: `/approve {m.get('id')}`")
        lines.append("")

    if confirmed:
        lines.append("✅ **Confirmed Memories & Rules:**")
        for m in confirmed:
            m_id = m.get("id", "-")
            m_type = m.get("type", "rule")
            lines.append(f"• `#{m_id}` [{m_type.upper()}] {m.get('text')}")

    await reply_long(update, "\n".join(lines))


@owner_only
async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("Usage: `/approve <id>` (jaise `/approve 5`)", parse_mode="Markdown")

    fact_id = int(ctx.args[0])
    success = await brain.supabase.confirm_fact(fact_id)
    if success:
        await update.message.reply_text(f"✅ Memory `#{fact_id}` confirm kar di gayi hai! Ab ye permanent recall me activate ho gayi.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Memory `#{fact_id}` confirm nahi ho paayi (ID check karo).")


@owner_only
async def cmd_remember(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fact = " ".join(ctx.args).strip() if ctx.args else ""
    if not fact:
        return await update.message.reply_text("Usage: `/remember <rule ya preference>`", parse_mode="Markdown")

    emb = await brain.embeddings.get_embedding(fact)
    fact_id = await brain.supabase.save_fact(fact_text=fact, category="user_preference", status="confirmed", embedding=emb)
    await update.message.reply_text(f"✅ Confirmed memory yaad kar li bhai! [ID #{fact_id}]: {fact}")


@owner_only
async def cmd_forget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("Usage: `/forget <id>` (jaise `/forget 3`)", parse_mode="Markdown")

    rec_id = int(ctx.args[0])
    # Try deleting from facts and rules
    res1 = await brain.supabase.delete_memory("facts", rec_id)
    res2 = await brain.supabase.delete_memory("rules", rec_id)
    if res1 or res2:
        await update.message.reply_text(f"🗑️ Memory #{rec_id} dimaag se hata di gayi hai.")
    else:
        await update.message.reply_text(f"Memory #{rec_id} nahi mili.")


@owner_only
async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rules = await brain.supabase.get_active_rules()
    lines = ["🛡️ **Hermes Golden Operating Rules:**\n"]
    for i, r in enumerate(rules, 1):
        lines.append(f"{i}. {r}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@owner_only
async def cmd_bounty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = " ".join(ctx.args).strip() if ctx.args else "python"
    await update.message.reply_text(f"🔍 Bounties dhoondh raha hu for `{query}`...")
    summary = await bounty_hunter.get_summary_formatted(query=query)
    await reply_long(update, summary)


@owner_only
async def cmd_sandbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = " ".join(ctx.args).strip() if ctx.args else ""
    if not code:
        return await update.message.reply_text("Usage: `/sandbox print('Hello Hermes')`")

    res = await sandbox.run_python(code)
    if res["success"]:
        await update.message.reply_text(f"✅ Sandbox Success ({res['duration_sec']}s):\n```\n{res['output']}\n```", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ Sandbox Error ({res['duration_sec']}s):\n```\n{res['error']}\n```", parse_mode="Markdown")


@owner_only
async def cmd_mode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sid = str(update.effective_chat.id)
    if not ctx.args or ctx.args[0].lower() not in ("text", "voice"):
        curr = await brain.redis.get_mode(sid)
        return await update.message.reply_text(f"Current mode: `{curr}`\nUsage: `/mode text` ya `/mode voice`")

    new_mode = ctx.args[0].lower()
    await brain.redis.set_mode(sid, new_mode)
    await update.message.reply_text(f"Mode set to: `{new_mode}`")


# ---------- Message Handlers ----------
@owner_only
async def on_text_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sid = str(update.effective_chat.id)
    text = update.message.text

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Process through Brain
    reply = await brain.process_message(session_id=sid, user_msg=text, modality="text")
    await reply_long(update, reply)


@owner_only
async def on_voice_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙️ Voice message mila! (STT model hook up karne ke baad direct audio process hoga)")


def create_bot_application() -> Optional[Application]:
    """Build and configure the python-telegram-bot application."""
    token = Config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("[Bot] TELEGRAM_BOT_TOKEN not configured; Telegram bot will not start.")
        return None

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("memories", cmd_memory))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("bounty", cmd_bounty))
    app.add_handler(CommandHandler("sandbox", cmd_sandbox))
    app.add_handler(CommandHandler("mode", cmd_mode))

    # Messages
    app.add_handler(MessageHandler(filters.VOICE, on_voice_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    return app
