#!/bin/bash

# Stop Permanent ngrok Tunnel

echo "🛑 Stopping permanent ngrok tunnel..."

# Kill ngrok process using saved PID
if [[ -f .ngrok_pid ]]; then
    NGROK_PID=$(cat .ngrok_pid)
    if kill -0 $NGROK_PID 2>/dev/null; then
        echo "🔗 Stopping ngrok tunnel (PID: $NGROK_PID)..."
        kill $NGROK_PID
        echo "✅ Tunnel stopped"
    else
        echo "⚠️  Tunnel process not found (PID: $NGROK_PID)"
    fi
    rm -f .ngrok_pid
else
    echo "⚠️  No saved PID found, trying to kill all ngrok processes..."
    pkill -f "ngrok start" || echo "No ngrok processes found"
fi

# Clean up saved files
rm -f .ngrok_url
rm -f .ngrok_pid

echo "🧹 Cleanup complete" 