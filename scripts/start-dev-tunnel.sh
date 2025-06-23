#!/bin/bash

echo "🔗 Starting ngrok tunnel..."

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok is not installed!"
    echo "📖 Please follow the manual setup steps first"
    exit 1
fi

# Kill existing ngrok processes
pkill -f ngrok 2>/dev/null || true

# Start ngrok tunnel
echo "🚀 Launching ngrok on port 5001..."
ngrok http 5001 --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
echo "⏳ Waiting for ngrok to initialize..."
sleep 5

# Check if ngrok is running
if ! kill -0 $NGROK_PID 2>/dev/null; then
    echo "❌ ngrok failed to start. Check ngrok.log for details:"
    cat ngrok.log
    exit 1
fi

# Get the public URL with retries
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
        break
    fi
    
    echo "⏳ Attempt $i/10: Waiting for ngrok URL..."
    sleep 2
done

if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ Failed to get ngrok URL after 10 attempts"
    echo "🔍 Check ngrok.log for errors:"
    cat ngrok.log
    kill $NGROK_PID 2>/dev/null
    exit 1
fi

echo "✅ Tunnel: ${WEBHOOK_URL}"
echo "✅ Webhook: ${WEBHOOK_URL}/webhook/twitter"
echo "📊 Dashboard: http://localhost:4040"

# Save for other scripts
echo "WEBHOOK_URL=${WEBHOOK_URL}/webhook/twitter" > .env.ngrok
echo "NGROK_PID=${NGROK_PID}" >> .env.ngrok
echo "NGROK_PUBLIC_URL=${WEBHOOK_URL}" >> .env.ngrok

echo "🎉 ngrok tunnel ready!"
echo "💡 Use 'kill ${NGROK_PID}' to stop the tunnel" 