#!/bin/bash

echo "🛑 Stopping development environment..."

# Kill ngrok processes
if [ -f .env.ngrok ]; then
    source .env.ngrok
    if [ ! -z "$NGROK_PID" ]; then
        echo "🔗 Stopping ngrok tunnel (PID: $NGROK_PID)..."
        kill $NGROK_PID 2>/dev/null || true
    fi
    rm -f .env.ngrok
fi

# Kill any remaining ngrok processes
pkill -f ngrok 2>/dev/null || true

# Kill Flask processes
pkill -f "python app.py" 2>/dev/null || true

# Clean up log files
rm -f ngrok.log

echo "✅ Development environment stopped"
echo "🧹 Cleanup complete" 