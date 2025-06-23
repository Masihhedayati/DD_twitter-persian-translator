import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json

from .database import Database
from .openai_client import OpenAIClient


class AIProcessor:
    """
    AI Processing Pipeline that integrates OpenAI analysis with tweet processing.
    Handles background processing, batch operations, and error recovery.
    """
    
    def __init__(self, database: Database, openai_client: OpenAIClient, 
                 batch_size: int = 10, processing_interval: int = 60):
        """Initialize AI processor"""
        self.database = database
        self.openai_client = openai_client
        self.batch_size = batch_size
        self.processing_interval = processing_interval
        
        # Processing state
        self.is_running = False
        self.processing_thread = None
        self.start_time = time.time()
        self.last_activity = time.time()
        
        # Statistics
        self.processed_count = 0
        self.error_count = 0
        self.total_tokens_used = 0
        self.total_cost = 0.0
        
        # Configuration
        self.max_retries = 3
        self.retry_delay = 300  # 5 minutes
        self.enable_auto_retry = True
        
        self.logger = logging.getLogger(__name__)
        
    def get_unprocessed_tweets(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get tweets that haven't been processed by AI yet"""
        try:
            limit = limit or self.batch_size
            tweets = self.database.get_unprocessed_tweets(limit=limit)
            return tweets
        except Exception as e:
            self.logger.error(f"Error getting unprocessed tweets: {e}")
            return []
    
    def process_single_tweet(self, tweet_data: Dict[str, Any], 
                           template_name: str = "persian_translator") -> Dict[str, Any]:
        """Process a single tweet with AI analysis using Persian translator by default"""
        try:
            self.logger.info(f"Processing tweet {tweet_data.get('id')} with AI (Persian translator)")
            
            # Use the OpenAI client's synchronous wrapper
            result = self.openai_client.analyze_tweet(tweet_data, template_name)
            
            # Update last activity
            self.last_activity = time.time()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing tweet {tweet_data.get('id')}: {e}")
            return {
                'status': 'failed',
                'tweet_id': tweet_data.get('id'),
                'error_message': str(e)
            }
    
    def process_tweet_async(self, tweet_data: Dict[str, Any], 
                          template_name: str = "persian_translator") -> Dict[str, Any]:
        """Async wrapper for processing a single tweet - used by background worker"""
        try:
            result = self.process_single_tweet(tweet_data, template_name)
            
            # Transform the result format for background worker compatibility
            if result.get('status') == 'completed':
                ai_result_data = result.get('ai_result', {})
                analysis_text = ai_result_data.get('raw_response', '') if isinstance(ai_result_data, dict) else str(ai_result_data)
                
                return {
                    'analysis': analysis_text,
                    'sentiment_score': None,  # Could extract from analysis if needed
                    'keywords': []  # Could extract from analysis if needed
                }
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error in async tweet processing: {e}")
            return None
    
    def store_ai_result(self, ai_result: Dict[str, Any]) -> bool:
        """Store AI analysis result in database"""
        try:
            # Extract data for storage
            tweet_id = ai_result.get('tweet_id')
            if not tweet_id:
                self.logger.error("No tweet_id in AI result")
                return False
            
            # Extract the actual translation text from the AI result
            ai_result_data = ai_result.get('ai_result', {})
            if isinstance(ai_result_data, dict) and 'raw_response' in ai_result_data:
                # Extract the raw response content
                result_text = ai_result_data.get('raw_response', '')
            else:
                # Fallback to JSON string if it's a different structure
                result_text = json.dumps(ai_result_data) if ai_result_data else ''
            
            # Prepare data for database
            result_data = {
                'tweet_id': tweet_id,
                'model_used': ai_result.get('model_used', 'unknown'),
                'prompt_type': 'persian_translator',
                'result': result_text,
                'tokens_used': ai_result.get('tokens_used', 0),
                'processing_time': ai_result.get('processing_time', 0),
                'cost': ai_result.get('cost', 0.0),
                'status': ai_result.get('status', 'completed'),
                'error_message': ai_result.get('error_message')
            }
            
            success = self.database.store_ai_result(result_data)
            
            if success:
                # Update statistics
                self.total_tokens_used += result_data['tokens_used']
                self.total_cost += result_data.get('cost', 0.0)
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error storing AI result: {e}")
            return False
    
    def update_tweet_status(self, tweet_id: str, processed: bool) -> bool:
        """Update tweet's AI processing status"""
        try:
            return self.database.update_tweet_ai_status(tweet_id, processed)
        except Exception as e:
            self.logger.error(f"Error updating tweet status: {e}")
            return False
    
    def process_batch(self) -> List[Dict[str, Any]]:
        """Process a batch of unprocessed tweets"""
        results = []
        
        try:
            # Get unprocessed tweets
            tweets = self.get_unprocessed_tweets()
            
            if not tweets:
                self.logger.info("No tweets to process")
                return results
            
            self.logger.info(f"Processing batch of {len(tweets)} tweets")
            
            # Process each tweet
            for tweet in tweets:
                try:
                    # Process with AI
                    ai_result = self.process_single_tweet(tweet)
                    results.append(ai_result)
                    
                    # Store result
                    if ai_result.get('status') == 'completed':
                        # Store AI analysis
                        store_success = self.store_ai_result(ai_result)
                        
                        # Update tweet status
                        status_success = self.update_tweet_status(
                            tweet['id'], True
                        )
                        
                        if store_success and status_success:
                            self.processed_count += 1
                            self.logger.info(f"Successfully processed tweet {tweet['id']}")
                        else:
                            self.error_count += 1
                            self.logger.error(f"Failed to store results for tweet {tweet['id']}")
                    else:
                        # Mark as failed but don't increment processed count
                        self.error_count += 1
                        self.logger.error(f"AI processing failed for tweet {tweet['id']}: "
                                        f"{ai_result.get('error_message', 'Unknown error')}")
                        
                        # Still update status to avoid reprocessing immediately
                        self.update_tweet_status(tweet['id'], False)
                    
                    # Small delay to avoid overwhelming APIs
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.logger.error(f"Error processing tweet {tweet.get('id', 'unknown')}: {e}")
                    self.error_count += 1
                    results.append({
                        'status': 'failed',
                        'tweet_id': tweet.get('id'),
                        'error_message': str(e)
                    })
            
        except Exception as e:
            self.logger.error(f"Error in batch processing: {e}")
        
        return results
    
    def start_background_processing(self):
        """Start background processing in a separate thread"""
        if self.is_running:
            self.logger.warning("Background processing is already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        self.processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True,
            name="AIProcessorThread"
        )
        self.processing_thread.start()
        
        self.logger.info("Background AI processing started")
    
    def stop_background_processing(self):
        """Stop background processing"""
        if not self.is_running:
            self.logger.warning("Background processing is not running")
            return
        
        self.is_running = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
        
        self.logger.info("Background AI processing stopped")
    
    def _processing_loop(self):
        """Main processing loop for background operation"""
        self.logger.info("AI processing loop started")
        
        while self.is_running:
            try:
                # Process batch
                results = self.process_batch()
                
                if results:
                    success_count = sum(1 for r in results if r.get('status') == 'completed')
                    error_count = len(results) - success_count
                    
                    self.logger.info(f"Batch completed: {success_count} success, {error_count} errors")
                
                # Sleep until next processing interval
                for _ in range(self.processing_interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                time.sleep(30)  # Wait 30 seconds before retrying
        
        self.logger.info("AI processing loop stopped")
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics and metrics"""
        uptime_seconds = time.time() - self.start_time
        total_processed = self.processed_count + self.error_count
        success_rate = self.processed_count / max(1, total_processed)
        
        tweets_per_minute = 0.0
        if uptime_seconds > 0:
            tweets_per_minute = (self.processed_count * 60) / uptime_seconds
        
        return {
            'is_running': self.is_running,
            'uptime_seconds': uptime_seconds,
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'total_processed': total_processed,
            'success_rate': success_rate,
            'tweets_per_minute': tweets_per_minute,
            'total_tokens_used': self.total_tokens_used,
            'total_cost': self.total_cost,
            'last_activity': self.last_activity,
            'batch_size': self.batch_size,
            'processing_interval': self.processing_interval
        }
    
    def reset_statistics(self):
        """Reset processing statistics"""
        self.processed_count = 0
        self.error_count = 0
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.start_time = time.time()
        self.logger.info("Processing statistics reset")
    
    def set_batch_size(self, batch_size: int):
        """Set the batch size for processing"""
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")
        
        self.batch_size = batch_size
        self.logger.info(f"Batch size set to {batch_size}")
    
    def set_processing_interval(self, interval: int):
        """Set the processing interval in seconds"""
        if interval <= 0:
            raise ValueError("Processing interval must be positive")
        
        self.processing_interval = interval
        self.logger.info(f"Processing interval set to {interval} seconds")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current processing queue status"""
        try:
            unprocessed_count = self.database.get_unprocessed_count()
            total_count = self.database.get_total_tweets_count()
            processed_count = total_count - unprocessed_count
            
            completion_percentage = 0.0
            if total_count > 0:
                completion_percentage = (processed_count / total_count) * 100
            
            return {
                'unprocessed_count': unprocessed_count,
                'processed_count': processed_count,
                'total_count': total_count,
                'completion_percentage': completion_percentage,
                'queue_size': unprocessed_count
            }
            
        except Exception as e:
            self.logger.error(f"Error getting queue status: {e}")
            return {
                'error': str(e),
                'unprocessed_count': 0,
                'processed_count': 0,
                'total_count': 0
            }
    
    def process_specific_tweet(self, tweet_id: str, 
                             template_name: str = "persian_translator") -> Dict[str, Any]:
        """Process a specific tweet by ID"""
        try:
            # Get tweet from database
            tweet = self.database.get_tweet_by_id(tweet_id)
            
            if not tweet:
                return {
                    'status': 'not_found',
                    'message': 'Tweet not found',
                    'tweet_id': tweet_id
                }
            
            # Process with AI
            ai_result = self.process_single_tweet(tweet, template_name)
            
            # Store result if successful
            if ai_result.get('status') == 'completed':
                store_success = self.store_ai_result(ai_result)
                status_success = self.update_tweet_status(tweet_id, True)
                
                if store_success and status_success:
                    self.processed_count += 1
                    self.logger.info(f"Successfully processed specific tweet {tweet_id}")
                else:
                    self.logger.error(f"Failed to store results for specific tweet {tweet_id}")
            
            return ai_result
            
        except Exception as e:
            self.logger.error(f"Error processing specific tweet {tweet_id}: {e}")
            return {
                'status': 'failed',
                'tweet_id': tweet_id,
                'error_message': str(e)
            }
    
    def reprocess_failed_tweets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Reprocess tweets that previously failed AI analysis"""
        results = []
        
        try:
            # Get failed tweets
            failed_tweets = self.database.get_failed_ai_tweets(limit=limit)
            
            if not failed_tweets:
                self.logger.info("No failed tweets to reprocess")
                return results
            
            self.logger.info(f"Reprocessing {len(failed_tweets)} failed tweets")
            
            # Process each failed tweet
            for tweet in failed_tweets:
                try:
                    # Clear previous error status
                    self.database.clear_ai_error(tweet['id'])
                    
                    # Reprocess with AI
                    ai_result = self.process_single_tweet(tweet)
                    results.append(ai_result)
                    
                    # Store result
                    if ai_result.get('status') == 'completed':
                        store_success = self.store_ai_result(ai_result)
                        status_success = self.update_tweet_status(tweet['id'], True)
                        
                        if store_success and status_success:
                            self.processed_count += 1
                            self.logger.info(f"Successfully reprocessed tweet {tweet['id']}")
                    
                    time.sleep(1)  # Longer delay for retry processing
                    
                except Exception as e:
                    self.logger.error(f"Error reprocessing tweet {tweet.get('id')}: {e}")
                    results.append({
                        'status': 'failed',
                        'tweet_id': tweet.get('id'),
                        'error_message': str(e)
                    })
            
        except Exception as e:
            self.logger.error(f"Error in reprocessing failed tweets: {e}")
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the AI processor"""
        now = time.time()
        uptime = now - self.start_time
        time_since_activity = now - self.last_activity
        
        # Consider unhealthy if no activity for 2 hours
        is_healthy = self.is_running and time_since_activity < 7200
        
        return {
            'is_healthy': is_healthy,
            'is_running': self.is_running,
            'uptime': uptime,
            'last_activity': self.last_activity,
            'time_since_activity': time_since_activity,
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'openai_stats': self.openai_client.get_statistics()
        }
    
    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent AI processing results"""
        try:
            return self.database.get_recent_ai_results(limit=limit)
        except Exception as e:
            self.logger.error(f"Error getting recent results: {e}")
            return []
    
    def pause_processing(self):
        """Temporarily pause processing without stopping"""
        if hasattr(self, '_paused'):
            return
        
        self._paused = True
        self.logger.info("AI processing paused")
    
    def resume_processing(self):
        """Resume paused processing"""
        if hasattr(self, '_paused'):
            del self._paused
            self.logger.info("AI processing resumed")
    
    def is_paused(self) -> bool:
        """Check if processing is currently paused"""
        return hasattr(self, '_paused')
        
        return openai_enabled and telegram_enabled 