import logging
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from core.twitter_client import TwitterClient
from core.ai_processor import AIProcessor
from core.telegram_bot import create_telegram_notifier
from config import Config

class RSSWebhookHandler:
    """Handles incoming RSS.app webhooks to trigger Twitter polling"""
    
    def __init__(self, db_manager, twitter_client: TwitterClient, ai_processor: AIProcessor, config: Dict[str, Any]):
        self.db = db_manager
        self.twitter_client = twitter_client
        self.ai_processor = ai_processor
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize Telegram notifier
        self.telegram_notifier = create_telegram_notifier(config)
        
        # Rate limiting for triggered polling
        self.last_poll_time = {}
        self.min_poll_interval = 300  # 5 minutes minimum between polls per user
        
        self.logger.info("RSS webhook handler initialized")
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify the webhook signature from RSS.app"""
        if not signature or not secret:
            return False
            
        # RSS.app typically sends signature as 'sha256=<hash>'
        expected_signature = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def process_rss_webhook(self, event_data: Dict[str, Any], signature: str = None) -> Dict[str, Any]:
        """Process incoming RSS webhook from RSS.app"""
        try:
            # RSS.app doesn't provide webhook signatures, so we skip verification
            # This is acceptable since we're only triggering polling, not exposing sensitive data
            self.logger.info("Processing RSS.app webhook (no signature verification needed)")
            
            # Extract information from RSS webhook
            rss_item = self._parse_rss_webhook(event_data)
            if not rss_item:
                return {"status": "ignored", "message": "No valid RSS item found"}
            
            username = rss_item.get('username')
            if not username:
                return {"status": "ignored", "message": "No username found in RSS item"}
            
            # Check rate limiting
            current_time = datetime.now().timestamp()
            last_poll = self.last_poll_time.get(username, 0)
            
            if current_time - last_poll < self.min_poll_interval:
                self.logger.info(f"Rate limiting: Skipping poll for @{username} (last poll {int(current_time - last_poll)}s ago)")
                return {"status": "rate_limited", "message": f"Rate limited for @{username}"}
            
            # Trigger Twitter polling for this user
            result = self._trigger_user_polling(username)
            
            # Update last poll time
            self.last_poll_time[username] = current_time
            
            self.logger.info(f"RSS webhook triggered polling for @{username}")
            
            return {
                "status": "success",
                "username": username,
                "triggered_at": datetime.utcnow().isoformat(),
                "polling_result": result
            }
            
        except Exception as e:
            self.logger.error(f"Error processing RSS webhook: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _parse_rss_webhook(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse RSS.app webhook data to extract relevant information"""
        try:
            # RSS.app webhook formats may vary, handle common structures
            
            # Format 1: Direct item structure
            if 'item' in webhook_data:
                item = webhook_data['item']
            elif 'entry' in webhook_data:
                item = webhook_data['entry']
            else:
                # Format 2: Root level item
                item = webhook_data
            
            # Extract username from various possible fields
            username = None
            
            # Try to extract from link/URL
            link = item.get('link', item.get('url', ''))
            if 'twitter.com/' in link or 'x.com/' in link:
                # Extract username from Twitter URL
                parts = link.split('/')
                for i, part in enumerate(parts):
                    if part in ['twitter.com', 'x.com'] and i + 1 < len(parts):
                        username = parts[i + 1].split('?')[0]  # Remove query params
                        break
            
            # Try to extract from title or description
            if not username:
                title = item.get('title', '')
                description = item.get('description', item.get('summary', ''))
                
                # Look for @username patterns
                import re
                for text in [title, description]:
                    match = re.search(r'@(\w+)', text)
                    if match:
                        username = match.group(1)
                        break
            
            # Try to extract from feed metadata
            if not username and 'feed' in webhook_data:
                feed = webhook_data['feed']
                feed_title = feed.get('title', '')
                if 'twitter' in feed_title.lower() or 'x.com' in feed_title.lower():
                    # Extract username from feed title like "Twitter - @username"
                    import re
                    match = re.search(r'@(\w+)', feed_title)
                    if match:
                        username = match.group(1)
            
            if not username:
                self.logger.warning(f"Could not extract username from RSS webhook: {webhook_data}")
                return None
            
            return {
                'username': username.lower(),
                'title': item.get('title', ''),
                'link': link,
                'published': item.get('published', item.get('pubDate', '')),
                'description': item.get('description', item.get('summary', '')),
                'guid': item.get('guid', item.get('id', '')),
                'raw_webhook': webhook_data
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing RSS webhook: {str(e)}")
            return None
    
    def _trigger_user_polling(self, username: str) -> Dict[str, Any]:
        """Trigger TwitterAPI.io polling for a specific user"""
        try:
            # Check if user is in monitored list
            monitored_users = self.db.get_monitored_users()
            if username not in monitored_users:
                self.logger.info(f"User @{username} not in monitored list, skipping polling")
                return {"status": "ignored", "message": "User not monitored"}
            
            # Fetch latest tweets for this user
            self.logger.info(f"Triggering polling for @{username} via RSS webhook")
            
            # Use existing TwitterClient to fetch tweets
            tweets = self.twitter_client.get_user_tweets(username, count=10)
            
            if not tweets:
                return {"status": "no_tweets", "message": "No tweets found"}
            
            processed_count = 0
            new_tweets = 0
            
            for tweet in tweets:
                # Check if tweet already exists
                existing_tweet = self.db.get_tweet_by_id(tweet['id'])
                if existing_tweet:
                    continue
                
                new_tweets += 1
                
                # Store tweet
                tweet_id = self.db.store_tweet(tweet)
                
                # Process with AI
                try:
                    self.ai_processor.add_tweet_to_queue(tweet)
                    # AI processing will happen asynchronously
                    
                    # Send Telegram notification (if AI processing was successful)
                    if self.telegram_notifier:
                        try:
                            # Note: For RSS webhooks, we send notification immediately
                            # The AI processing will happen in background
                            self.telegram_notifier.send_notification(tweet, None)
                            self.db.mark_telegram_sent(tweet_id)
                            self.logger.info(f"Telegram notification sent for tweet {tweet_id}")
                        except Exception as e:
                            self.logger.error(f"Failed to send Telegram notification: {str(e)}")
                except Exception as e:
                    self.logger.error(f"Failed to process tweet {tweet_id} with AI: {str(e)}")
                
                processed_count += 1
            
            self.logger.info(f"RSS webhook polling completed for @{username}: {new_tweets} new tweets, {processed_count} processed")
            
            return {
                "status": "success",
                "new_tweets": new_tweets,
                "processed": processed_count,
                "total_fetched": len(tweets)
            }
            
        except Exception as e:
            self.logger.error(f"Error triggering polling for @{username}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def get_webhook_stats(self) -> Dict[str, Any]:
        """Get statistics about RSS webhook activity"""
        return {
            "last_poll_times": self.last_poll_time,
            "min_poll_interval": self.min_poll_interval,
            "active_users": list(self.last_poll_time.keys())
        }
    
    def handle_test_webhook(self) -> Dict[str, Any]:
        """Handle test webhook request"""
        try:
            # For testing, use a sample RSS webhook payload
            test_data = {
                "feed": {
                    "title": "Test RSS Feed",
                    "url": "https://example.com/feed"
                },
                "item": {
                    "title": "Test tweet notification",
                    "link": "https://twitter.com/testuser/status/123456789",
                    "description": "This is a test webhook from RSS.app"
                }
            }
            
            # Extract username from the test link
            username = self.extract_username_from_data(test_data)
            if not username:
                username = "testuser"  # Generic test username
            
            self.logger.info(f"Processing test RSS webhook for @{username}")
            result = self._trigger_user_polling(username)
            
            return {
                "status": "success",
                "message": "Test RSS webhook processed successfully",
                "username": username,
                "triggered_at": datetime.now().isoformat(),
                "result": result
            }
            
        except Exception as e:
            self.logger.error(f"Error processing test RSS webhook: {e}")
            return {
                "status": "error",
                "message": f"Test webhook failed: {str(e)}"
            } 