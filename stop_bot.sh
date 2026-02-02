#!/bin/bash
# Script to stop the bot safely

PID_FILE="/tmp/telegram_ssh_bot.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping bot with PID: $PID"
        kill "$PID"
        sleep 3
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Force killing..."
            kill -9 "$PID"
        fi
        rm -f "$PID_FILE"
        echo "✅ Bot stopped"
    else
        echo "PID file exists but process not running. Cleaning up..."
        rm -f "$PID_FILE"
    fi
fi

# Also kill any remaining bot processes
if pgrep -f "python3 bot.py" > /dev/null; then
    echo "Stopping remaining bot processes..."
    pkill -9 -f "python3 bot.py"
    sleep 2
fi

echo "Done"

