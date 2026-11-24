"""
main.py - Hermes FastAPI Server & Process Orchestrator
Designed for Hugging Face Spaces and local deployment:
  - Port 7860 health endpoints (GET /, GET /health)
  - REST Chat API (POST /api/chat)
  - Telegram Bot Polling / Webhook
"""
import asyncio
from contextlib import asynccontextmanager

from bot.telegram_bot import create_bot_application
from core.brain import brain
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from utils.helpers import Config, logger

bot_app = None
bot_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    global bot_app, bot_task
    logger.info("🚀 Starting Hermes Server...")

    # 1. Initialize DB and memories
    await brain.initialize()

    # 2. Start Telegram bot in background if configured
    bot_app = create_bot_application()
    if bot_app:
        await bot_app.initialize()
        await bot_app.start()
        logger.info("🤖 Starting Telegram polling...")
        bot_task = asyncio.create_task(bot_app.updater.start_polling(drop_pending_updates=True))
    else:
        logger.warning("⚠️ Bot not started: TELEGRAM_BOT_TOKEN missing in .env")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Hermes Server...")
    if bot_app and bot_app.updater and bot_app.updater.running:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


app = FastAPI(
    title="Hermes Co-Founder Brain",
    description="3-Tier Persistent Memory System (Redis + Turso + Supabase) with Tool Calling",
    version="2.0.0",
    lifespan=lifespan,
)


# ---------- Health Check Endpoints (Hugging Face Spaces) ----------
@app.get("/")
@app.get("/health")
async def health_check():
    """Hugging Face Space requires port 7860 to respond with 200 OK."""
    status = Config.check_status()
    return {
        "status": "healthy",
        "agent": "Hermes Co-Founder",
        "version": "2.0.0",
        "services": status,
    }


# ---------- REST Chat Endpoint ----------
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_user"
    modality: str = "text"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat_api(req: ChatRequest):
    """Direct API endpoint for communicating with Hermes."""
    reply = await brain.process_message(
        session_id=req.session_id,
        user_msg=req.message,
        modality=req.modality,
    )
    return ChatResponse(reply=reply, session_id=req.session_id)


# ---------- Telegram Webhook Endpoint ----------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Optional webhook endpoint for Telegram in production."""
    if bot_app:
        try:
            data = await request.json()
            from telegram import Update
            update = Update.de_json(data, bot_app.bot)
            await bot_app.process_update(update)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"[Webhook] Error processing update: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})
    return JSONResponse(status_code=400, content={"error": "Bot not running"})


if __name__ == "__main__":
    uvicorn.run(
        "main.py:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=False,
    )
