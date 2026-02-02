#!/bin/bash
# Script to start the bot safely (only one instance)

BOT_DIR="/root/telegram-ssh-bot"
PID_FILE="/tmp/telegram_ssh_bot.pid"
LOG_FILE="$BOT_DIR/bot.log"

# Check if bot is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Bot is already running with PID: $OLD_PID"
        exit 1
    else
        # Remove stale PID file
        rm -f "$PID_FILE"
    fi
fi

# Check for any running bot processes
if pgrep -f "python3 bot.py" > /dev/null; then
    echo "Bot process already running. Stopping old processes..."
    pkill -9 -f "python3 bot.py"
    sleep 2
fi

# Change to bot directory
cd "$BOT_DIR" || exit 1

# Activate virtual environment
source venv/bin/activate || exit 1

# Start bot
STARTUP_MARKER="STARTUP_MARKER_$(date +%s)_$$"
echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] $STARTUP_MARKER" >> "$LOG_FILE"
nohup python3 bot.py >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Save PID
echo "$BOT_PID" > "$PID_FILE"

# Wait for process + readiness ("Application started") instead of just PID existing
READY_TIMEOUT_SECONDS=120
for ((i=1; i<=READY_TIMEOUT_SECONDS; i++)); do
    if ! ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo "❌ Bot process exited during startup. Check log: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    # Check readiness only after our marker line
    if awk -v m="$STARTUP_MARKER" '
        $0 ~ m {found=1; next}
        found && $0 ~ /Application started/ {ready=1; exit}
        END {exit (ready ? 0 : 1)}
    ' "$LOG_FILE"; then
        echo "✅ Bot started and READY with PID: $BOT_PID"
        echo "Log file: $LOG_FILE"
        echo "To stop: kill $BOT_PID or use stop_bot.sh"
        exit 0
    fi

    sleep 1
done

echo "⚠️ Bot process started (PID: $BOT_PID) but not READY after ${READY_TIMEOUT_SECONDS}s."
echo "Check log: $LOG_FILE"
exit 0

