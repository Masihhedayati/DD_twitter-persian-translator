"""
Test suite for TelegramNotifier class

Tests cover:
- Bot initialization and validation
- Message formatting and sending
- Queue management and worker threads
- Rate limiting and error handling
- Database integration
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import time

# Import the classes to test
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.telegram_bot import TelegramNotifier, create_telegram_notifier
from core.database import Database


class TestTelegramNotifier:
    """Test suite for TelegramNotifier functionality"""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager"""
        db = Mock(spec=Database)
        db.update_telegram_status = Mock(return_value=True)
        db.get_tweet_media = Mock(return_value=[])
        return db
    
    @pytest.fixture
    def sample_tweet(self):
        """Sample tweet data for testing"""
        return {
            'id': '1234567890',
            'username': 'testuser',
            'display_name': 'Test User',
            'content': 'This is a sample tweet for testing purposes.',
            'created_at': '2024-12-28T10:30:00Z',
            'likes_count': 42,
            'retweets_count': 7,
            'replies_count': 3
        }
    
    @pytest.fixture
    def sample_ai_result(self):
        """Sample AI analysis result"""
        return {
            'result': 'This tweet discusses testing methodologies with a positive sentiment.',
            'model_used': 'gpt-3.5-turbo',
            'tokens_used': 150
        }
    
    def test_initialization(self, mock_db_manager):
        """Test TelegramNotifier initialization"""
        bot_token = "test_bot_token"
        chat_id = "test_chat_id"
        
        notifier = TelegramNotifier(bot_token, chat_id, mock_db_manager)
        
        assert notifier.bot_token == bot_token
        assert notifier.chat_id == chat_id
        assert notifier.db_manager == mock_db_manager
        assert notifier.is_running is False
        assert notifier.message_queue.qsize() == 0
        assert notifier.stats['messages_sent'] == 0
    
    def test_initialization_without_db(self):
        """Test initialization without database manager"""
        notifier = TelegramNotifier("token", "chat_id")
        assert notifier.db_manager is None
    
    def test_queue_tweet_notification(self, mock_db_manager, sample_tweet, sample_ai_result):
        """Test queuing a tweet notification"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        
        result = notifier.queue_tweet_notification(sample_tweet, sample_ai_result)
        
        assert result is True
        assert notifier.message_queue.qsize() == 1
        assert notifier.stats['queue_size'] == 1
        
        # Check queued message data
        message_data = notifier.message_queue.get()
        assert message_data['type'] == 'tweet'
        assert message_data['tweet'] == sample_tweet
        assert message_data['ai_result'] == sample_ai_result
        assert message_data['tweet_id'] == sample_tweet['id']
    
    def test_queue_text_message(self, mock_db_manager):
        """Test queuing a simple text message"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        test_text = "This is a test message"
        
        result = notifier.queue_text_message(test_text)
        
        assert result is True
        assert notifier.message_queue.qsize() == 1
        
        # Check queued message data
        message_data = notifier.message_queue.get()
        assert message_data['type'] == 'text'
        assert message_data['text'] == test_text
        assert message_data['disable_preview'] is True
    
    def test_format_tweet_message_basic(self, mock_db_manager, sample_tweet):
        """Test basic tweet message formatting"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        
        message = notifier._format_tweet_message(sample_tweet)
        
        assert sample_tweet['display_name'] in message
        assert sample_tweet['username'] in message
        assert sample_tweet['content'] in message
        assert "🐦" in message  # Tweet emoji
        assert "🕐" in message  # Time emoji
        assert "📊" in message  # Stats emoji
        assert "🔗" in message  # Link emoji
    
    def test_format_tweet_message_with_ai(self, mock_db_manager, sample_tweet, sample_ai_result):
        """Test tweet message formatting with AI analysis"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        
        message = notifier._format_tweet_message(sample_tweet, sample_ai_result)
        
        assert sample_ai_result['result'] in message
        assert "🤖" in message  # AI emoji
        assert "AI Analysis:" in message
    
    def test_format_timestamp_recent(self, mock_db_manager):
        """Test timestamp formatting for recent times"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        
        # Test "just now"
        now = datetime.now()
        result = notifier._format_timestamp(now.isoformat())
        assert result == "Just now"
        
        # Test minutes ago
        minutes_ago = now - timedelta(minutes=5)
        result = notifier._format_timestamp(minutes_ago.isoformat())
        assert "5m ago" in result
    
    def test_get_queue_status(self, mock_db_manager):
        """Test getting queue status"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        
        status = notifier.get_queue_status()
        
        assert 'is_running' in status
        assert 'queue_size' in status
        assert 'stats' in status
        assert 'worker_alive' in status
        assert status['is_running'] is False
        assert status['queue_size'] == 0
    
    def test_clear_queue(self, mock_db_manager):
        """Test clearing the message queue"""
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        
        # Add some messages to queue
        notifier.queue_text_message("Message 1")
        notifier.queue_text_message("Message 2")
        notifier.queue_text_message("Message 3")
        
        assert notifier.message_queue.qsize() == 3
        
        cleared_count = notifier.clear_queue()
        
        assert cleared_count == 3
        assert notifier.message_queue.qsize() == 0
        assert notifier.stats['queue_size'] == 0
    
    @patch('core.telegram_bot.Bot')
    @pytest.mark.asyncio
    async def test_send_test_message_success(self, mock_bot_class, mock_db_manager):
        """Test sending test message successfully"""
        mock_bot_instance = AsyncMock()
        mock_bot_class.return_value = mock_bot_instance
        
        notifier = TelegramNotifier("token", "chat_id", mock_db_manager)
        result = await notifier.send_test_message()
        
        assert result is True
        mock_bot_instance.send_message.assert_called_once()
        
        # Check message format
        call_args = mock_bot_instance.send_message.call_args
        assert call_args[1]['chat_id'] == "chat_id"
        assert "Twitter Monitor Test" in call_args[1]['text']
    
    def test_create_telegram_notifier_success(self, mock_db_manager):
        """Test successful creation using factory function"""
        config = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }
        
        notifier = create_telegram_notifier(config, mock_db_manager)
        
        assert notifier is not None
        assert isinstance(notifier, TelegramNotifier)
        assert notifier.bot_token == 'test_token'
        assert notifier.chat_id == 'test_chat_id'
    
    def test_create_telegram_notifier_missing_config(self):
        """Test factory function with missing configuration"""
        config = {
            'TELEGRAM_BOT_TOKEN': 'test_token'
            # Missing TELEGRAM_CHAT_ID
        }
        
        notifier = create_telegram_notifier(config)
        
        assert notifier is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 