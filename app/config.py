import os
from dotenv import load_dotenv

load_dotenv()

# Strava
STRAVA_SESSION_COOKIE = os.getenv("STRAVA_SESSION_COOKIE", "")

# Club
CLUB_ID = int(os.getenv("STRAVA_CLUB_ID", ""))

# Schedule
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "00:05")
SCHEDULE_DAY = os.getenv("SCHEDULE_DAY", "monday")

# Output
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "leaderboard_output")
LEADERBOARD_MIN_RUNNERS = int(os.getenv("LEADERBOARD_MIN_RUNNERS", "20"))
LEADERBOARD_KM_CUTOFF = int(os.getenv("LEADERBOARD_KM_CUTOFF", "30"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_THREAD_ID = int(os.getenv("TELEGRAM_THREAD_ID", "0") or 0)
TELEGRAM_CAPTION = os.getenv("TELEGRAM_CAPTION", "Weekly club leaderboard")

# Cookie health check
TELEGRAM_ALERT_IDS = [x.strip() for x in os.getenv("TELEGRAM_ALERT_IDS", "").split(",") if x.strip()]
COOKIE_CHECK_INTERVAL_MINUTES = int(os.getenv("COOKIE_CHECK_INTERVAL_MINUTES", "180"))
LEADERBOARD_FAILURE_MESSAGE = os.getenv(
    "LEADERBOARD_FAILURE_MESSAGE",
    "К сожалению, токен Strava истёк, и админы ещё не обновили его. Лидерборд на этой неделе не сформирован. Свяжитесь с админами, чтобы исправить."
)
