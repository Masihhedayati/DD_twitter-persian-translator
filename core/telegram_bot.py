"""
Telegram Bot Client for Twitter Monitoring System

This module provides comprehensive Telegram bot functionality for sending
tweet notifications with media support, rate limiting, and error handling.
"""

import os
import logging
import asyncio
import aiofiles
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import time
from queue import Queue
from threading import Thread, Event
import json

from telegram import Bot, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from telegram.error import TelegramError, RetryAfter, TimedOut, NetworkError
from telegram.constants import ParseMode, FileSizeLimit

# Database is now handled via SQLAlchemy in main app - passed as parameter


class TelegramNotifier:
    """
    Comprehensive Telegram bot client for sending tweet notifications.
    
    Features:
    - Formatted message sending with media support
    - Rate limit handling and queue management
    - Multiple media types (images, videos, documents)
    - Error handling with retry logic
    - Message templates and formatting
    - Queue statistics and monitoring
    """
    
    def __init__(self, bot_token: str, chat_id: str, db_manager = None):
        """
        Initialize Telegram bot client.
        
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Target chat ID for notifications
            db_manager: Database manager instance
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.db_manager = db_manager
        
        self.bot = Bot(token=bot_token)
        self.logger = logging.getLogger(__name__)
        
        # Queue management
        self.message_queue = Queue()
        self.is_running = False
        self.worker_thread = None
        self.stop_event = Event()
        
        # Rate limiting (Telegram limits: 30 messages/second, 1 message/chat/second)
        self.last_message_time = 0
        self.message_interval = 1.1  # Slightly over 1 second for safety
        self.rate_limit_buffer = 5  # Extra seconds when rate limited
        
        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'media_sent': 0,
            'rate_limit_hits': 0,
            'queue_size': 0,
            'last_sent': None,
            'total_retries': 0
        }
        
        # Configuration
        self.max_retries = 3
        self.retry_delay = 2.0
        self.max_caption_length = 1024  # Telegram limit
        self.max_message_length = 4096  # Telegram limit
        
        self.logger.info(f"TelegramNotifier initialized for chat {chat_id}")
    
    async def validate_bot_token(self) -> bool:
        """
        Validate bot token by making a test API call.
        
        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            bot_info = await self.bot.get_me()
            self.logger.info(f"Bot validated: @{bot_info.username} ({bot_info.first_name})")
            return True
        except Exception as e:
            self.logger.error(f"Bot token validation failed: {e}")
            return False
    
    def start_worker(self) -> bool:
        """
        Start the background worker thread for processing message queue.
        
        Returns:
            bool: True if started successfully, False if already running
        """
        if self.is_running:
            self.logger.warning("Worker thread already running")
            return False
        
        self.is_running = True
        self.stop_event.clear()
        self.worker_thread = Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        self.logger.info("Telegram worker thread started")
        return True
    
    def stop_worker(self) -> bool:
        """
        Stop the background worker thread.
        
        Returns:
            bool: True if stopped successfully
        """
        if not self.is_running:
            return False
        
        self.is_running = False
        self.stop_event.set()
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
        
        self.logger.info(f"Telegram worker stopped. Queue had {self.message_queue.qsize()} pending messages")
        return True
    
    def _worker_loop(self):
        """Background worker thread that processes the message queue."""
        self.logger.info("Telegram worker loop started")
        
        while self.is_running and not self.stop_event.is_set():
            try:
                # Process messages from queue
                if not self.message_queue.empty():
                    message_data = self.message_queue.get_nowait()
                    asyncio.run(self._send_message_from_queue(message_data))
                    self.message_queue.task_done()
                else:
                    # Short sleep when queue is empty
                    time.sleep(0.5)
                    
            except Exception as e:
                self.logger.error(f"Error in worker loop: {e}")
                time.sleep(1)
        
        self.logger.info("Telegram worker loop ended")
    
    async def _send_message_from_queue(self, message_data: Dict[str, Any]):
        """
        Send a message from the queue with rate limiting and error handling.
        
        Args:
            message_data: Dictionary containing message information
        """
        # Respect rate limits
        current_time = time.time()
        time_since_last = current_time - self.last_message_time
        
        if time_since_last < self.message_interval:
            sleep_time = self.message_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        retry_count = 0
        max_retries = message_data.get('max_retries', self.max_retries)
        
        while retry_count < max_retries:
            try:
                # Send the message based on type
                if message_data['type'] == 'text':
                    await self._send_text_message(message_data)
                elif message_data['type'] == 'tweet':
                    await self._send_tweet_notification(message_data)
                
                # Success - update stats and database
                self.stats['messages_sent'] += 1
                self.stats['last_sent'] = datetime.now()
                self.last_message_time = time.time()
                
                # Update database if available
                if self.db_manager and 'tweet_id' in message_data:
                    self.db_manager.update_telegram_status(
                        message_data['tweet_id'], 
                        True, 
                        datetime.now()
                    )
                
                break  # Success, exit retry loop
                
            except RetryAfter as e:
                # Telegram rate limit - wait and retry
                self.stats['rate_limit_hits'] += 1
                retry_delay = e.retry_after + self.rate_limit_buffer
                self.logger.warning(f"Rate limited, waiting {retry_delay}s before retry")
                await asyncio.sleep(retry_delay)
                retry_count += 1
                
            except (TimedOut, NetworkError) as e:
                # Network issues - retry with exponential backoff
                retry_count += 1
                retry_delay = self.retry_delay * (2 ** (retry_count - 1))
                self.logger.warning(f"Network error: {e}. Retrying in {retry_delay}s (attempt {retry_count})")
                await asyncio.sleep(retry_delay)
                
            except TelegramError as e:
                # Other Telegram errors - log and skip
                self.logger.error(f"Telegram API error: {e}")
                self.stats['messages_failed'] += 1
                break
                
            except Exception as e:
                # Unexpected errors
                self.logger.error(f"Unexpected error sending message: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(self.retry_delay)
        
        if retry_count >= max_retries:
            self.stats['messages_failed'] += 1
            self.stats['total_retries'] += retry_count
            
            # Update database with failure
            if self.db_manager and 'tweet_id' in message_data:
                self.db_manager.update_telegram_status(
                    message_data['tweet_id'], 
                    False, 
                    datetime.now(),
                    f"Failed after {retry_count} retries"
                )
    
    async def _send_text_message(self, message_data: Dict[str, Any]):
        """Send a simple text message."""
        text = message_data['text']
        
        # Truncate if too long
        if len(text) > self.max_message_length:
            text = text[:self.max_message_length - 3] + "..."
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=message_data.get('disable_preview', True)
        )
    
    async def _send_tweet_notification(self, message_data: Dict[str, Any]):
        """Send a formatted tweet notification."""
        tweet = message_data['tweet']
        ai_result = message_data.get('ai_result')
        
        # Format tweet message
        message = self._format_tweet_message(tweet, ai_result)
        
        # Get media files
        media_files = self._get_tweet_media_files(tweet)
        
        if media_files:
            # Send with media
            await self._send_media_with_caption(media_files, message)
        else:
            # Send text only
            await self._send_text_message({
                'text': message,
                'disable_preview': False
            })
    
    async def _send_media_with_caption(self, media_files: List[Dict], caption: str):
        """Send media with caption."""
        if not media_files:
            return
        
        # Truncate caption if too long
        if len(caption) > self.max_caption_length:
            caption = caption[:self.max_caption_length - 3] + "..."
        
        try:
            media_file = media_files[0]  # Send first media item
            media_path = media_file['path']
            media_type = media_file['type']
            
            if not os.path.exists(media_path):
                # Send text only if media missing
                await self._send_text_message({
                    'text': caption,
                    'disable_preview': False
                })
                return
            
            if media_type == 'image':
                async with aiofiles.open(media_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=photo,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
            elif media_type == 'video':
                async with aiofiles.open(media_path, 'rb') as video:
                    await self.bot.send_video(
                        chat_id=self.chat_id,
                        video=video,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
            else:
                async with aiofiles.open(media_path, 'rb') as document:
                    await self.bot.send_document(
                        chat_id=self.chat_id,
                        document=document,
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
            
            self.stats['media_sent'] += 1
            
        except Exception as e:
            self.logger.error(f"Error sending media: {e}")
            # Fallback to text message
            await self._send_text_message({
                'text': caption,
                'disable_preview': False
            })
    
    def _format_tweet_message(self, tweet: Dict[str, Any], ai_result: Dict[str, Any] = None) -> str:
        """
        Format tweet data into a readable message.
        
        Args:
            tweet: Tweet data from database
            ai_result: AI analysis result
            
        Returns:
            str: Formatted message
        """
        username = tweet.get('username', 'Unknown')
        display_name = tweet.get('display_name', username)
        content = tweet.get('content', '')
        created_at = tweet.get('created_at', '')
        
        # Format header
        message = f"🐦 <b>{display_name}</b> (@{username})\n"
        message += f"🕐 {self._format_timestamp(created_at)}\n\n"
        
        # Tweet content
        message += f"{content}\n\n"
        
        # Add AI analysis if available
        if ai_result and ai_result.get('result'):
            message += f"🤖 <b>AI Analysis:</b>\n{ai_result['result']}\n\n"
        
        # Add metrics
        likes = tweet.get('likes_count', 0)
        retweets = tweet.get('retweets_count', 0)
        replies = tweet.get('replies_count', 0)
        
        if any([likes, retweets, replies]):
            message += f"📊 {likes}❤️ {retweets}🔄 {replies}💬\n"
        
        # Add link to original tweet
        tweet_id = tweet.get('id', '')
        if tweet_id:
            message += f"\n🔗 <a href='https://twitter.com/{username}/status/{tweet_id}'>View Tweet</a>"
        
        return message
    
    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format timestamp for display."""
        try:
            if isinstance(timestamp_str, str):
                # Parse ISO format timestamp
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = timestamp_str
            
            # Calculate time difference
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days}d ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours}h ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes}m ago"
            else:
                return "Just now"
                
        except Exception:
            return str(timestamp_str)
    
    def _get_tweet_media_files(self, tweet: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Get local media file paths for a tweet.
        
        Args:
            tweet: Tweet data
            
        Returns:
            List of media file information
        """
        media_files = []
        
        if not self.db_manager:
            return media_files
        
        try:
            # Get media from database
            media_records = self.db_manager.get_tweet_media(tweet.get('id', ''), completed_only=True)
            
            for media in media_records:
                local_path = media.get('local_path')
                if local_path and os.path.exists(local_path):
                    media_files.append({
                        'path': local_path,
                        'type': media.get('media_type', 'document')
                    })
            
        except Exception as e:
            self.logger.error(f"Error getting media files for tweet {tweet.get('id')}: {e}")
        
        return media_files
    
    def queue_tweet_notification(self, tweet: Dict[str, Any], ai_result: Dict[str, Any] = None) -> bool:
        """
        Queue a tweet notification for sending.
        
        Args:
            tweet: Tweet data
            ai_result: Optional AI analysis result
            
        Returns:
            bool: True if queued successfully
        """
        try:
            message_data = {
                'type': 'tweet',
                'tweet': tweet,
                'ai_result': ai_result,
                'tweet_id': tweet.get('id'),
                'timestamp': datetime.now().isoformat()
            }
            
            self.message_queue.put(message_data)
            self.stats['queue_size'] = self.message_queue.qsize()
            
            self.logger.info(f"Queued tweet notification: {tweet.get('username')}/{tweet.get('id')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue tweet notification: {e}")
            return False
    
    def queue_text_message(self, text: str, disable_preview: bool = True) -> bool:
        """
        Queue a simple text message.
        
        Args:
            text: Message text
            disable_preview: Whether to disable link previews
            
        Returns:
            bool: True if queued successfully
        """
        try:
            message_data = {
                'type': 'text',
                'text': text,
                'disable_preview': disable_preview,
                'timestamp': datetime.now().isoformat()
            }
            
            self.message_queue.put(message_data)
            self.stats['queue_size'] = self.message_queue.qsize()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue text message: {e}")
            return False
    
    async def send_tweet_notification(self, tweet: Dict[str, Any], ai_result: Dict[str, Any] = None) -> bool:
        """
        Send a tweet notification immediately (synchronous interface).
        
        Args:
            tweet: Tweet data dictionary
            ai_result: AI processing result (optional)
            
        Returns:
            bool: True if sent successfully
        """
        try:
            message_data = {
                'type': 'tweet',
                'tweet': tweet,
                'ai_result': ai_result,
                'tweet_id': tweet.get('id'),
                'timestamp': datetime.now().isoformat()
            }
            
            await self._send_tweet_notification(message_data)
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending tweet notification: {e}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and statistics.
        
        Returns:
            Dict containing queue status information
        """
        return {
            'is_running': self.is_running,
            'queue_size': self.message_queue.qsize(),
            'stats': self.stats.copy(),
            'worker_alive': self.worker_thread.is_alive() if self.worker_thread else False
        }
    
    def clear_queue(self) -> int:
        """
        Clear all pending messages from queue.
        
        Returns:
            int: Number of messages cleared
        """
        count = 0
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                count += 1
            except:
                break
        
        self.stats['queue_size'] = 0
        self.logger.info(f"Cleared {count} messages from queue")
        return count
    
    async def send_test_message(self) -> bool:
        """
        Send a test message to verify bot functionality.
        
        Returns:
            bool: True if test message sent successfully
        """
        try:
            test_message = (
                "🧪 <b>Twitter Monitor Test</b>\n\n"
                f"Bot is working correctly!\n"
                f"Chat ID: <code>{self.chat_id}</code>\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=test_message,
                parse_mode=ParseMode.HTML
            )
            
            self.logger.info("Test message sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send test message: {e}")
            return False


def create_telegram_notifier(config: Dict[str, Any], db_manager = None) -> Optional[TelegramNotifier]:
    """
    Factory function to create TelegramNotifier instance.
    
    Args:
        config: Configuration dictionary with Telegram settings
        db_manager: Optional database manager instance
        
    Returns:
        TelegramNotifier instance or None if configuration invalid
    """
    bot_token = config.get('TELEGRAM_BOT_TOKEN')
    chat_id = config.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logging.error("Telegram configuration missing: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")
        return None
    
    try:
        notifier = TelegramNotifier(bot_token, chat_id, db_manager)
        logging.info("TelegramNotifier created successfully")
        return notifier
        
    except Exception as e:
        logging.error(f"Failed to create TelegramNotifier: {e}")
        return None 