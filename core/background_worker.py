import logging
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
from queue import Queue

from .database import Database
from .ai_processor import AIProcessor
from .media_extractor import MediaExtractor
from .openai_client import OpenAIClient


class BackgroundWorker:
    """
    Background worker that continuously processes tweets missing AI translations or media downloads
    
    Responsibilities:
    - Find tweets without AI analysis and queue them for processing
    - Find tweets with missing media downloads and retry downloading
    - Process failed/partial downloads
    - Maintain database completeness over time
    """
    
    def __init__(self, database: Database, openai_client: OpenAIClient, media_storage_path: str):
        """
        Initialize background worker
        
        Args:
            database: Database instance
            openai_client: OpenAI client for AI processing
            media_storage_path: Path for media storage
        """
        self.database = database
        self.openai_client = openai_client
        self.media_extractor = MediaExtractor(media_storage_path)
        self.ai_processor = AIProcessor(database, openai_client)
        
        self.logger = logging.getLogger(__name__)
        
        # Worker configuration
        self.processing_interval = 300  # 5 minutes between cycles
        self.batch_size = 10  # Process 10 tweets per batch
        self.max_retries = 3  # Maximum retries for failed items
        
        # Worker state
        self.is_running = False
        self.worker_thread = None
        self.ai_queue = Queue()
        self.media_queue = Queue()
        
        # Statistics
        self.stats = {
            'ai_processed': 0,
            'media_processed': 0,
            'ai_failed': 0,
            'media_failed': 0,
            'cycles_completed': 0,
            'last_cycle': None,
            'started_at': None
        }
    
    def start(self):
        """Start the background worker"""
        if self.is_running:
            self.logger.warning("Background worker is already running")
            return
        
        self.is_running = True
        self.stats['started_at'] = datetime.now()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        self.logger.info("Background worker started successfully")
    
    def stop(self):
        """Stop the background worker"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        
        self.logger.info("Background worker stopped")
    
    def _worker_loop(self):
        """Main worker loop that continuously processes missing data"""
        self.logger.info("Background worker loop started")
        
        while self.is_running:
            try:
                cycle_start = datetime.now()
                self.logger.debug("Starting background processing cycle")
                
                # Process tweets missing AI analysis
                ai_processed = self._process_missing_ai_analysis()
                
                # Process tweets missing media downloads
                media_processed = self._process_missing_media()
                
                # Update statistics
                self.stats['ai_processed'] += ai_processed
                self.stats['media_processed'] += media_processed
                self.stats['cycles_completed'] += 1
                self.stats['last_cycle'] = cycle_start
                
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                
                if ai_processed > 0 or media_processed > 0:
                    self.logger.info(f"Background cycle completed: {ai_processed} AI, {media_processed} media processed in {cycle_duration:.1f}s")
                
                # Sleep until next cycle
                time.sleep(self.processing_interval)
                
            except Exception as e:
                self.logger.error(f"Error in background worker loop: {e}")
                time.sleep(30)  # Short sleep before retrying
    
    def _process_missing_ai_analysis(self) -> int:
        """
        Find and process tweets missing AI analysis
        
        Returns:
            Number of tweets processed
        """
        try:
            # Find tweets without AI analysis
            missing_ai_tweets = self.database.get_tweets_without_ai_analysis(limit=self.batch_size)
            
            if not missing_ai_tweets:
                return 0
            
            processed_count = 0
            
            for tweet_data in missing_ai_tweets:
                try:
                    tweet_id = tweet_data['id']
                    content = tweet_data['content']
                    
                    self.logger.debug(f"Processing AI analysis for tweet {tweet_id}")
                    
                    # Generate AI analysis
                    ai_result = self.ai_processor.process_tweet_async({
                        'id': tweet_id,
                        'content': content,
                        'username': tweet_data.get('username', ''),
                        'created_at': tweet_data.get('created_at', '')
                    })
                    
                    if ai_result and ai_result.get('analysis'):
                        # Update tweet with AI analysis
                        self.database.update_tweet_ai_analysis(
                            tweet_id=tweet_id,
                            ai_analysis=ai_result['analysis'],
                            sentiment_score=ai_result.get('sentiment_score'),
                            keywords=ai_result.get('keywords', [])
                        )
                        
                        processed_count += 1
                        self.logger.debug(f"AI analysis completed for tweet {tweet_id}")
                        
                    else:
                        self.logger.warning(f"AI analysis failed for tweet {tweet_id}")
                        self.stats['ai_failed'] += 1
                
                except Exception as e:
                    self.logger.error(f"Error processing AI analysis for tweet: {e}")
                    self.stats['ai_failed'] += 1
            
            return processed_count
            
        except Exception as e:
            self.logger.error(f"Error in _process_missing_ai_analysis: {e}")
            return 0
    
    def _process_missing_media(self) -> int:
        """
        Find and process tweets with missing media downloads
        
        Returns:
            Number of media items processed
        """
        try:
            # Find tweets with media but no downloaded files
            missing_media_tweets = self.database.get_tweets_with_missing_media(limit=self.batch_size)
            
            if not missing_media_tweets:
                return 0
            
            processed_count = 0
            
            for tweet_data in missing_media_tweets:
                try:
                    tweet_id = tweet_data['id']
                    
                    self.logger.debug(f"Processing missing media for tweet {tweet_id}")
                    
                    # Get media information from database
                    media_items = self.database.get_tweet_media(tweet_id)
                    
                    for media_item in media_items:
                        # Check if media file exists locally
                        local_path = media_item.get('local_path')
                        if local_path and self._file_exists_and_valid(local_path):
                            continue  # File already exists and is valid
                        
                        # Retry downloading the media
                        success = self._retry_media_download(tweet_id, media_item)
                        
                        if success:
                            processed_count += 1
                        else:
                            self.stats['media_failed'] += 1
                
                except Exception as e:
                    self.logger.error(f"Error processing missing media for tweet: {e}")
                    self.stats['media_failed'] += 1
            
            return processed_count
            
        except Exception as e:
            self.logger.error(f"Error in _process_missing_media: {e}")
            return 0
    
    def _retry_media_download(self, tweet_id: str, media_item: Dict) -> bool:
        """
        Retry downloading a specific media item
        
        Args:
            tweet_id: Tweet ID
            media_item: Media item dictionary
            
        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Prepare media data for download
            media_url = media_item.get('original_url')
            media_type = media_item.get('media_type', 'photo')
            
            if not media_url:
                self.logger.warning(f"No media URL for tweet {tweet_id}, media item {media_item.get('id')}")
                return False
            
            # Use media extractor to download
            download_result = asyncio.run(self.media_extractor._download_single_media(
                tweet_id=tweet_id,
                media_info={
                    'type': media_type,
                    'url': media_url,
                    'width': media_item.get('width'),
                    'height': media_item.get('height'),
                    'duration': media_item.get('duration')
                },
                index=0,
                date_str=datetime.now().strftime('%Y-%m-%d')
            ))
            
            if download_result.get('status') == 'completed':
                # Update database with new local path
                self.database.update_media_local_path(
                    media_item['id'],
                    download_result['local_path']
                )
                
                self.logger.info(f"Successfully downloaded media for tweet {tweet_id}")
                return True
            else:
                self.logger.warning(f"Failed to download media for tweet {tweet_id}: {download_result.get('error_message')}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error retrying media download: {e}")
            return False
    
    def _file_exists_and_valid(self, file_path: str) -> bool:
        """
        Check if file exists and is valid (not empty/corrupted)
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file exists and is valid
        """
        try:
            import os
            if not os.path.exists(file_path):
                return False
            
            # Check file size (should be > 0)
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False
            
            # Basic validation - file should be readable
            with open(file_path, 'rb') as f:
                f.read(1)  # Try to read first byte
            
            return True
            
        except Exception:
            return False
    
    def get_stats(self) -> Dict:
        """
        Get background worker statistics
        
        Returns:
            Dictionary with worker statistics
        """
        stats = self.stats.copy()
        stats['is_running'] = self.is_running
        stats['uptime_seconds'] = None
        
        if self.stats['started_at']:
            uptime = datetime.now() - self.stats['started_at']
            stats['uptime_seconds'] = uptime.total_seconds()
        
        return stats
    
    def force_process_tweet(self, tweet_id: str) -> Dict:
        """
        Force immediate processing of a specific tweet
        
        Args:
            tweet_id: Tweet ID to process
            
        Returns:
            Processing result
        """
        try:
            result = {
                'ai_processed': False,
                'media_processed': False,
                'errors': []
            }
            
            # Get tweet data
            tweet_data = self.database.get_tweet_by_id(tweet_id)
            if not tweet_data:
                result['errors'].append(f"Tweet {tweet_id} not found")
                return result
            
            # Process AI analysis if missing
            if not tweet_data.get('ai_analysis'):
                try:
                    ai_result = self.ai_processor.process_tweet_async(tweet_data)
                    if ai_result and ai_result.get('analysis'):
                        self.database.update_tweet_ai_analysis(
                            tweet_id=tweet_id,
                            ai_analysis=ai_result['analysis'],
                            sentiment_score=ai_result.get('sentiment_score'),
                            keywords=ai_result.get('keywords', [])
                        )
                        result['ai_processed'] = True
                except Exception as e:
                    result['errors'].append(f"AI processing failed: {e}")
            
            # Process missing media
            media_items = self.database.get_tweet_media(tweet_id)
            for media_item in media_items:
                local_path = media_item.get('local_path')
                if not local_path or not self._file_exists_and_valid(local_path):
                    try:
                        success = self._retry_media_download(tweet_id, media_item)
                        if success:
                            result['media_processed'] = True
                    except Exception as e:
                        result['errors'].append(f"Media processing failed: {e}")
            
            return result
            
        except Exception as e:
            return {
                'ai_processed': False,
                'media_processed': False,
                'errors': [f"Force processing failed: {e}"]
            } 