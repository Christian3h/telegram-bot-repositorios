FROM python:3.11-alpine

WORKDIR /app

# Copy application files
COPY bot.py /app/bot.py
COPY tasks_watcher.py /app/tasks_watcher.py
COPY watched_repos.example.json /app/watched_repos.example.json

# Run unbuffered Python daemon
CMD ["python", "-u", "bot.py", "--daemon"]
