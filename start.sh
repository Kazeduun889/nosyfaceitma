#!/bin/bash
# Start Flask App in background
gunicorn web.app:app --bind 0.0.0.0:$PORT &

# Start Telegram Bot in foreground
python main.py
