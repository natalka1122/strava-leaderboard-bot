# Strava Leaderboard Bot 🏃‍♂️

Weekly Strava club leaderboard bot that generates and shares attractive leaderboard images with running statistics.

## Features

- Fetches Strava club leaderboard via web API
- Generates styled PNG leaderboard with athlete photos and stats
- Supports multiple stat columns: Distance, Runs, Longest Run, Avg Pace, Elevation Gain
- Sends results to Telegram group chat
- Runs on a weekly schedule (default: Monday 00:05)

## Requirements

- Docker
- Docker Compose
- Strava session cookie (refresh every 2-4 weeks)
- Telegram Bot Token (for messaging)

## Setup

1. Clone the repository:
```bash
git clone https://github.com/natalka1122/strava-leaderboard-bot.git
cd strava-leaderboard-bot
```

2. Create `.env` file from the example:
```bash
cp .env.example .env
```

3. Configure your `.env` file with:
- `STRAVA_SESSION_COOKIE`: Get from browser DevTools → Application → Cookies → .strava.com → `_strava4_session`
- `STRAVA_CLUB_ID`: Your Strava club ID (e.g., `1125315`)
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token (from @BotFather)
- `TELEGRAM_CHAT_ID`: Target chat ID for messages

For Telegram setup:
- Create a bot via @BotFather
- Get the chat ID by sending a message to your chat and using: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`

## Running

1. Build and start:
```bash
docker-compose up -d --build
```

2. View logs:
```bash
docker-compose logs -f
```

3. Stop:
```bash
docker-compose down
```

## Schedule

The bot is configured to run weekly by default. Change in `.env` or `docker-compose.yml` if needed. Default is Monday 00:05.

## Project Structure

```
├── app/              Application code
│   ├── bot.py        Entry point
│   ├── config.py     Configuration
│   ├── strava_scraper.py Strava API client
│   ├── image_generator.py   Image creation
│   └── telegram_client.py   Telegram integration
├── .env.example      Configuration template
├── Dockerfile        Container build
└── docker-compose.yml Docker Compose setup
```

## Notes

- Leaderboard images are generated with athlete avatars and highlight top 3 runners
- Images are stored in `leaderboard_output/` directory
- The bot requires a fresh Strava session cookie every 2-4 weeks
- Make sure your Telegram bot has permissions to send messages to the target chat

## License

MIT License
