#!/bin/bash

# Start Permanent ngrok Tunnel for RSS.app Webhooks
# This script creates a more stable ngrok tunnel using configuration

set -e

echo "🔗 Starting Permanent ngrok Tunnel for RSS.app..."

# Start ngrok tunnel directly (using default config)
echo "🚀 Starting ngrok tunnel..."
ngrok http 5001 --log=stdout &
NGROK_PID=$!

echo "⏳ Waiting for ngrok to initialize..."
sleep 5

# Get the tunnel URL
echo "🔍 Getting tunnel URL..."
TUNNEL_URL=""
for i in {1..10}; do
    TUNNEL_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url // empty' 2>/dev/null || echo "")
    if [[ -n "$TUNNEL_URL" && "$TUNNEL_URL" != "null" ]]; then
        break
    fi
    echo "   Attempt $i/10..."
    sleep 2
done

if [[ -z "$TUNNEL_URL" || "$TUNNEL_URL" == "null" ]]; then
    echo "❌ Failed to get tunnel URL"
    kill $NGROK_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "✅ Permanent ngrok Tunnel Ready!"
echo "🌐 Webhook URL: $TUNNEL_URL/webhook/rss"
echo "📊 Dashboard: http://localhost:4040"
echo "🔗 Public URL: $TUNNEL_URL"
echo ""
echo "📝 Use this URL in RSS.app webhook configuration:"
echo "   $TUNNEL_URL/webhook/rss"
echo ""
echo "💡 To stop the tunnel: kill $NGROK_PID"
echo "💡 Or use: pkill -f 'ngrok start'"
echo ""

# Save tunnel info
echo "$TUNNEL_URL" > .ngrok_url
echo "$NGROK_PID" > .ngrok_pid

echo "🎉 Tunnel is running in background!"
echo "📝 Tunnel URL saved to .ngrok_url"
echo "📝 Process ID saved to .ngrok_pid" 