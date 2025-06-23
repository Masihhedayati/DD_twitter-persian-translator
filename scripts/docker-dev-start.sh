#!/bin/bash

echo "🐳 Starting Docker Development Environment..."

# Configure ngrok if authtoken is provided
if [ ! -z "$NGROK_AUTHTOKEN" ]; then
    echo "🔑 Configuring ngrok..."
    ngrok config add-authtoken $NGROK_AUTHTOKEN
    
    # Start ngrok in background
    echo "🔗 Starting ngrok tunnel..."
    ngrok http 5001 --log=stdout > /app/logs/ngrok.log 2>&1 &
    NGROK_PID=$!
    
    # Wait for ngrok to start
    sleep 5
    
    # Try to get the public URL
    for i in {1..10}; do
        WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for tunnel in tunnels:
        if tunnel.get('proto') == 'https':
            print(tunnel['public_url'])
            break
except:
    pass
" 2>/dev/null)
        
        if [ ! -z "$WEBHOOK_URL" ]; then
            echo "✅ ngrok tunnel ready: ${WEBHOOK_URL}"
            echo "✅ Webhook URL: ${WEBHOOK_URL}/webhook/twitter"
            break
        fi
        
        echo "⏳ Waiting for ngrok... ($i/10)"
        sleep 2
    done
    
    if [ -z "$WEBHOOK_URL" ]; then
        echo "⚠️  Could not get ngrok URL, but continuing..."
    fi
else
    echo "⚠️  No NGROK_AUTHTOKEN provided, skipping ngrok setup"
fi

# Create development database if it doesn't exist
if [ ! -f "/app/dev_tweets.db" ]; then
    echo "🗄️  Creating development database..."
    python3 -c "
from core.database import init_db
init_db('/app/dev_tweets.db')
print('✅ Development database created')
"
fi

echo "🐍 Starting Flask application in development mode..."
echo "📊 Local: http://localhost:5001"
echo "🌐 Public: ${WEBHOOK_URL:-'ngrok not configured'}"
echo "📊 ngrok dashboard: http://localhost:4040"
echo ""

# Start Flask with hot reload
exec python3 app.py 