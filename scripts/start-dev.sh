#!/bin/bash

echo "🚀 Starting Local Development..."

# Check if development environment exists
if [ ! -f ".env.development" ]; then
    echo "❌ .env.development not found!"
    echo "📖 Please create it from env.example first:"
    echo "   cp env.example .env.development"
    echo "   # Then edit .env.development with your API keys"
    exit 1
fi

# Load development environment
set -a
source .env.development
set +a
echo "📋 Loaded .env.development"

# Start ngrok tunnel
echo "🌐 Starting ngrok tunnel..."
./scripts/start-dev-tunnel.sh

if [ $? -ne 0 ]; then
    echo "❌ Failed to start ngrok tunnel"
    exit 1
fi

# Load ngrok URL
if [ -f .env.ngrok ]; then
    set -a
    source .env.ngrok
    set +a
    echo "🔗 Webhook URL: $WEBHOOK_URL"
    echo "🌐 Public URL: $NGROK_PUBLIC_URL"
else
    echo "❌ ngrok environment not found"
    exit 1
fi

# Create development database if it doesn't exist
if [ ! -f "./dev_tweets.db" ]; then
    echo "🗄️  Creating development database..."
    python -c "
from core.database import init_db
init_db('./dev_tweets.db')
print('✅ Development database created')
"
fi

echo "🐍 Starting Flask in debug mode..."
echo "📊 Local Dashboard: http://localhost:${PORT:-5001}"
echo "🌐 Public Dashboard: ${NGROK_PUBLIC_URL}"
echo "📊 Version API: http://localhost:${PORT:-5001}/api/version"
echo "📊 ngrok Inspector: http://localhost:4040"
echo ""
echo "📝 To stop: Press Ctrl+C"
echo ""

# Set Flask environment for development
export FLASK_ENV=development
export FLASK_DEBUG=true

# Start Flask app
python app.py 