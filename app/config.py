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
LEADERBOARD_PER_PAGE = int(os.getenv("LEADERBOARD_PER_PAGE", "20"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_THREAD_ID = int(os.getenv("TELEGRAM_THREAD_ID", "0") or 0)
