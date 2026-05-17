"""
Send the leaderboard image to a Telegram chat.
Supports supergroup topics via TELEGRAM_THREAD_ID.
"""
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_THREAD_ID

logger = logging.getLogger(__name__)


def send_to_telegram(image_path: str) -> bool:
    """Sends the image at `image_path` to `TELEGRAM_CHAT_ID`.
    Optionally targets a specific topic (forum thread).
    Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram token or chat ID not set; skipping send.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": "Вот лидерборд этой недели! 🏃‍♂️🔥",
        "parse_mode": "HTML",
    }
    if TELEGRAM_THREAD_ID:
        payload["message_thread_id"] = TELEGRAM_THREAD_ID

    logger.info("Sending to Telegram chat %s (topic: %s)...", TELEGRAM_CHAT_ID, TELEGRAM_THREAD_ID or "main")

    try:
        with open(image_path, "rb") as img:
            resp = requests.post(url, data=payload, files={"photo": img}, timeout=20)
        if resp.status_code == 200:
            logger.info("Successfully sent to Telegram.")
            return True
        logger.error("Telegram error: %s — %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Failed to send: %s", e)
        return False
