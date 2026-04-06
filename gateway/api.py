import logging
import os
import tempfile
import asyncio
import json
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Ensure logging is set up
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com/webhook")
WEBHOOK_PATH = "/webhook"
HOST = "192.168.50.55"
PORT = 8765

# Init aiogram components
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set webhook on startup
    try:
        await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
        logger.info(f"Webhook set to {WEBHOOK_URL}{WEBHOOK_PATH}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
    yield
    # Delete webhook on shutdown
    try:
        await bot.delete_webhook()
        logger.info("Webhook deleted")
    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    update_data = await request.json()
    update = types.Update(**update_data)
    await dp.feed_update(bot, update)
    return {"status": "ok"}

@app.get("/")
async def health_check():
    return {"status": "healthy"}

@dp.message()
async def handle_message(message: types.Message):
    """
    Handle incoming messages and dispatch to a subprocess worker.
    """
    user_id = message.from_user.id
    text = message.text

    if not text:
        return

    logger.info(f"Received message from {user_id}: {text}")

    # Step 3: Subprocess-per-message pattern implementation
    # Create input JSON file
    fd_in, in_path = tempfile.mkstemp(prefix="hermes_in_", suffix=".json")
    fd_out, out_path = tempfile.mkstemp(prefix="hermes_out_", suffix=".json")

    try:
        with os.fdopen(fd_in, 'w') as f:
            json.dump({
                "user_id": user_id,
                "text": text,
                "message_id": message.message_id
            }, f)

        # Close output file descriptor so worker can write to it
        os.close(fd_out)

        # Spawn worker subprocess
        worker_script = os.path.join(os.path.dirname(__file__), "worker.py")

        logger.info(f"Spawning worker for {user_id} with in={in_path}, out={out_path}")

        # We run this in a thread pool to avoid blocking the asyncio event loop
        loop = asyncio.get_running_loop()
        process_task = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["python", worker_script, "--in-file", in_path, "--out-file", out_path],
                capture_output=True,
                text=True
            )
        )

        if process_task.returncode != 0:
            logger.error(f"Worker failed with code {process_task.returncode}:\n{process_task.stderr}")
            await message.reply("Sorry, an error occurred while processing your message.")
            return

        # Read the output JSON file
        with open(out_path, 'r') as f:
            try:
                result = json.load(f)
                response_text = result.get("response", "")
                if response_text:
                    await message.reply(response_text)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode output from worker: {open(out_path).read()}")
                await message.reply("Internal processing error.")

    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        await message.reply("A critical error occurred.")
    finally:
        # Step 3 Cleanup
        for path in (in_path, out_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.error(f"Failed to cleanup temp file {path}: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=HOST, port=PORT, reload=True)
