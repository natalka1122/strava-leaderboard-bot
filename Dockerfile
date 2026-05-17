FROM python:3.14-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN mkdir -p leaderboard_output

ENV TZ=Europe/Budapest

CMD ["python", "bot.py"]
