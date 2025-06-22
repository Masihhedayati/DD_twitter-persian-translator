#!/bin/bash

# Twitter Monitor Deployment Script
# Version: 1.0
# Description: Automated deployment script for Twitter monitoring system

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="twitter-monitor"
VENV_NAME="venv"
PYTHON_VERSION="3.8"
DEFAULT_ENV_FILE=".env.example"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_python() {
    log_info "Checking Python version..."
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
        PYTHON_CURRENT=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        log_success "Python $PYTHON_CURRENT found"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
        PYTHON_CURRENT=$(python --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        log_success "Python $PYTHON_CURRENT found"
    else
        log_error "Python not found. Please install Python $PYTHON_VERSION or higher"
        exit 1
    fi
}

check_docker() {
    if command -v docker >/dev/null 2>&1; then
        log_success "Docker found"
        return 0
    else
        log_warning "Docker not found"
        return 1
    fi
}

create_venv() {
    log_info "Creating virtual environment..."
    if [ ! -d "$VENV_NAME" ]; then
        $PYTHON_CMD -m venv $VENV_NAME
        log_success "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi
}

activate_venv() {
    log_info "Activating virtual environment..."
    if [ -f "$VENV_NAME/bin/activate" ]; then
        source $VENV_NAME/bin/activate
        log_success "Virtual environment activated"
    elif [ -f "$VENV_NAME/Scripts/activate" ]; then
        source $VENV_NAME/Scripts/activate
        log_success "Virtual environment activated (Windows)"
    else
        log_error "Virtual environment activation script not found"
        exit 1
    fi
}

install_dependencies() {
    log_info "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    log_success "Dependencies installed"
}

create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p logs media data
    log_success "Directories created"
}

setup_env_file() {
    log_info "Setting up environment configuration..."
    if [ ! -f ".env" ]; then
        if [ -f "$DEFAULT_ENV_FILE" ]; then
            cp $DEFAULT_ENV_FILE .env
            log_warning "Created .env from template. Please edit .env with your API keys!"
        else
            cat > .env << EOF
# Twitter Monitoring System Configuration
TWITTER_API_KEY=your_twitterapi_io_key_here
OPENAI_API_KEY=your_openai_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# System Configuration
MONITORED_USERS=elonmusk,naval,paulg
CHECK_INTERVAL=60
PORT=5001
DEBUG=True

# Database
DATABASE_PATH=./tweets.db

# Media Configuration
MEDIA_STORAGE_PATH=./media
MAX_MEDIA_SIZE=104857600
MEDIA_RETENTION_DAYS=90

# AI Configuration
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=150
DEFAULT_AI_PROMPT=Analyze this tweet and provide a brief summary of its key points and sentiment.

# Notification Settings
NOTIFICATION_ENABLED=true
NOTIFY_ALL_TWEETS=false
NOTIFY_AI_PROCESSED_ONLY=true
NOTIFICATION_DELAY=10
EOF
            log_warning "Created .env file. Please edit .env with your API keys!"
        fi
    else
        log_info ".env file already exists"
    fi
}

init_database() {
    log_info "Initializing database..."
    $PYTHON_CMD -c "from core.database import Database; Database('./tweets.db')"
    log_success "Database initialized"
}

run_tests() {
    log_info "Running test suite..."
    if python -m pytest --version >/dev/null 2>&1; then
        python -m pytest tests/ -v --tb=short
        log_success "Tests completed"
    else
        log_warning "pytest not found, skipping tests"
    fi
}

start_application() {
    log_info "Starting application..."
    $PYTHON_CMD app.py &
    APP_PID=$!
    sleep 5
    
    # Check if app is running
    if curl -f http://localhost:5001/health >/dev/null 2>&1; then
        log_success "Application started successfully on http://localhost:5001"
        log_info "Application PID: $APP_PID"
        echo $APP_PID > app.pid
    else
        log_error "Application failed to start properly"
        kill $APP_PID 2>/dev/null || true
        exit 1
    fi
}

stop_application() {
    log_info "Stopping application..."
    if [ -f "app.pid" ]; then
        PID=$(cat app.pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            rm app.pid
            log_success "Application stopped"
        else
            log_warning "Application was not running"
            rm app.pid
        fi
    else
        log_warning "No PID file found"
        # Try to find and kill the process
        pkill -f "python app.py" || true
    fi
}

docker_build() {
    log_info "Building Docker image..."
    docker build -t $PROJECT_NAME:latest .
    log_success "Docker image built"
}

docker_run() {
    log_info "Running Docker container..."
    docker run -d \
        --name $PROJECT_NAME \
        -p 5001:5001 \
        --env-file .env \
        -v $(pwd)/data:/app/data \
        -v $(pwd)/logs:/app/logs \
        -v $(pwd)/media:/app/media \
        $PROJECT_NAME:latest
    log_success "Docker container started"
}

docker_stop() {
    log_info "Stopping Docker container..."
    docker stop $PROJECT_NAME 2>/dev/null || true
    docker rm $PROJECT_NAME 2>/dev/null || true
    log_success "Docker container stopped"
}

show_help() {
    echo "Twitter Monitor Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install     - Install dependencies and setup environment"
    echo "  start       - Start the application"
    echo "  stop        - Stop the application"
    echo "  restart     - Restart the application"
    echo "  test        - Run test suite"
    echo "  docker-build - Build Docker image"
    echo "  docker-start - Start with Docker"
    echo "  docker-stop  - Stop Docker container"
    echo "  status      - Check application status"
    echo "  logs        - Show application logs"
    echo "  help        - Show this help message"
    echo ""
}

check_status() {
    log_info "Checking application status..."
    
    if [ -f "app.pid" ]; then
        PID=$(cat app.pid)
        if kill -0 $PID 2>/dev/null; then
            log_success "Application is running (PID: $PID)"
            
            # Check health endpoint
            if curl -f http://localhost:5001/health >/dev/null 2>&1; then
                log_success "Health check passed"
            else
                log_warning "Health check failed"
            fi
        else
            log_warning "PID file exists but process is not running"
            rm app.pid
        fi
    else
        log_info "Application is not running (no PID file)"
    fi
    
    # Check Docker container
    if check_docker; then
        if docker ps --format "table {{.Names}}" | grep -q $PROJECT_NAME; then
            log_success "Docker container is running"
        else
            log_info "Docker container is not running"
        fi
    fi
}

show_logs() {
    log_info "Showing application logs..."
    if [ -f "logs/app.log" ]; then
        tail -f logs/app.log
    else
        log_warning "Log file not found"
    fi
}

# Main script logic
case "$1" in
    "install")
        log_info "Starting installation..."
        check_python
        create_venv
        activate_venv
        install_dependencies
        create_directories
        setup_env_file
        init_database
        log_success "Installation completed successfully!"
        log_warning "Please edit .env file with your API keys before starting the application"
        ;;
    
    "start")
        log_info "Starting application..."
        check_python
        activate_venv
        start_application
        ;;
    
    "stop")
        stop_application
        ;;
    
    "restart")
        stop_application
        sleep 2
        check_python
        activate_venv
        start_application
        ;;
    
    "test")
        check_python
        activate_venv
        run_tests
        ;;
    
    "docker-build")
        check_docker || { log_error "Docker is required for this command"; exit 1; }
        docker_build
        ;;
    
    "docker-start")
        check_docker || { log_error "Docker is required for this command"; exit 1; }
        setup_env_file
        docker_stop  # Stop any existing container
        docker_build
        docker_run
        ;;
    
    "docker-stop")
        check_docker || { log_error "Docker is required for this command"; exit 1; }
        docker_stop
        ;;
    
    "status")
        check_status
        ;;
    
    "logs")
        show_logs
        ;;
    
    "help"|"--help"|"-h")
        show_help
        ;;
    
    *)
        if [ -z "$1" ]; then
            show_help
        else
            log_error "Unknown command: $1"
            show_help
            exit 1
        fi
        ;;
esac 