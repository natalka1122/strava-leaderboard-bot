"""
Send the leaderboard image to a Telegram chat.
"""
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def send_to_telegram(image_path: str) -> bool:
    """Sends the image at `image_path` to `TELEGRAM_CHAT_ID`.
    Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram token or chat ID not set; skipping send.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    logger.info("Sending image to Telegram chat %s...", TELEGRAM_CHAT_ID)

    try:
        with open(image_path, "rb") as img:
            caption = "Вот лидерборд этой недели! 🏃‍️🔥"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML"
            }
            resp = requests.post(
                url,
                data=payload,
                files={"photo": img},
                timeout=20
            )

        if resp.status_code == 200:
            logger.info("Successfully sent to Telegram.")
            return True
        else:
            logger.error(f"Telegram error: {resp.status_code} - {resp.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send to Telegram: {e}")
        return False
