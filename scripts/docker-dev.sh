#!/bin/bash

echo "🐳 Starting Docker Development Environment..."

# Check if .env.development exists
if [ ! -f ".env.development" ]; then
    echo "❌ .env.development not found!"
    echo "📖 Please create it first: cp env.development.example .env.development"
    exit 1
fi

# Load environment variables
export $(cat .env.development | grep -v '^#' | xargs)

# Add your ngrok authtoken if you have one
# export NGROK_AUTHTOKEN=your_ngrok_authtoken_here

echo "🚀 Starting Docker containers..."
docker-compose -f docker-compose.dev.yml up --build

echo "📊 Access your app at:"
echo "   Local: http://localhost:5001"
echo "   ngrok dashboard: http://localhost:4040" 