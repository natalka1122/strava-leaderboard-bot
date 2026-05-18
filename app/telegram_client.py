"""
Send the leaderboard image to a Telegram chat.
Supports supergroup topics via TELEGRAM_THREAD_ID.
"""
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_THREAD_ID, TELEGRAM_CAPTION

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
        "caption": TELEGRAM_CAPTION,
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


def send_group_message(text: str) -> bool:
    """Send a plain text message to the configured group chat.
    Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram token or chat ID not set; skipping send.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if TELEGRAM_THREAD_ID:
        payload["message_thread_id"] = TELEGRAM_THREAD_ID

    try:
        resp = requests.post(url, data=payload, timeout=20)
        if resp.status_code == 200:
            logger.info("Group message sent")
            return True
        logger.error("Telegram error: %s — %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Failed to send group message: %s", e)
        return False


def send_message(chat_id: str, text: str) -> bool:
    """Send a plain text message to a specific chat or user."""
    if not TELEGRAM_BOT_TOKEN:
        logger.info("Telegram token not set; skipping send.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, data=payload, timeout=20)
        if resp.status_code == 200:
            logger.info("Message sent to chat %s", chat_id)
            return True
        logger.error("Telegram error for chat %s: %s — %s", chat_id, resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Failed to send message to chat %s: %s", chat_id, e)
        return False
