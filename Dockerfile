FROM python:3.14-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN mkdir -p leaderboard_output

# Process probe via /proc (procps isn't installed in slim); container is
# healthy only while the bot process is alive — crash loops show unhealthy
HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
  CMD ["sh", "-c", "grep -qa 'bot.py' /proc/[0-9]*/cmdline 2>/dev/null || exit 1"]

ENV TZ=Europe/Budapest

CMD ["python", "bot.py"]
