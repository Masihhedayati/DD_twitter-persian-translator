# Core package for Twitter Monitoring System
# This package contains all the core business logic modules

__version__ = "1.0.0"
__author__ = "Twitter Monitor Team"

# Import available modules
from .database import Database
from .twitter_client import TwitterClient
from .media_extractor import MediaExtractor
from .polling_scheduler import PollingScheduler
from .openai_client import OpenAIClient
from .ai_processor import AIProcessor
from .telegram_bot import TelegramNotifier, create_telegram_notifier

__all__ = [
    'Database',
    'TwitterClient',
    'MediaExtractor', 
    'PollingScheduler',
    'OpenAIClient',
    'AIProcessor',
    'TelegramNotifier',
    'create_telegram_notifier'
]

# TODO: Add these imports as modules are created:
# from .telegram_bot import TelegramNotifier 