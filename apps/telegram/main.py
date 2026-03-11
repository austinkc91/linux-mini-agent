"""Telegram bot entry point for Linux Agent remote control.

Usage:
    TELEGRAM_BOT_TOKEN=<your-token> uv run python main.py

Optional env vars:
    LISTEN_URL          - Listen server URL (default: http://localhost:7600)
    TELEGRAM_ALLOWED_USERS - Comma-separated list of authorized Telegram user IDs
                             (default: allow all users — set this for security!)
"""

import logging
import os
import sys

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot import (
    handle_start,
    handle_job,
    handle_jobs,
    handle_status,
    handle_stop,
    handle_screenshot,
    handle_steer,
    handle_drive,
    handle_shell,
    handle_photo,
    handle_document,
    handle_text,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is required.")
        print()
        print("To get a bot token:")
        print("  1. Open Telegram and message @BotFather")
        print("  2. Send /newbot and follow the prompts")
        print("  3. Copy the token and set it:")
        print("     export TELEGRAM_BOT_TOKEN='your-token-here'")
        print()
        print("Optional security:")
        print("  export TELEGRAM_ALLOWED_USERS='123456789,987654321'")
        print("  (Your Telegram user ID — send /start to the bot to see it)")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()

    # Command handlers
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_start))
    app.add_handler(CommandHandler("job", handle_job))
    app.add_handler(CommandHandler("jobs", handle_jobs))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CommandHandler("stop", handle_stop))
    app.add_handler(CommandHandler("screenshot", handle_screenshot))
    app.add_handler(CommandHandler("steer", handle_steer))
    app.add_handler(CommandHandler("drive", handle_drive))
    app.add_handler(CommandHandler("shell", handle_shell))

    # Media handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Plain text → treat as job prompt
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Telegram bot starting...")
    logger.info(f"Listen URL: {os.environ.get('LISTEN_URL', 'http://localhost:7600')}")
    if os.environ.get("TELEGRAM_ALLOWED_USERS"):
        logger.info(f"Authorized users: {os.environ['TELEGRAM_ALLOWED_USERS']}")
    else:
        logger.warning("No TELEGRAM_ALLOWED_USERS set — all users can control this bot!")

    app.run_polling()


if __name__ == "__main__":
    main()
