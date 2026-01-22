#!/bin/bash
# Start script for Telegram SSH Bot
cd "$(dirname "$0")"
source venv/bin/activate
python3 bot.py

