import logging
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from core.database import Database
from core.ai_processor import AIProcessor
from core.telegram_bot import create_telegram_notifier
from config import Config

class TwitterWebhookHandler:
    """Handles incoming Twitter webhooks for real-time tweet monitoring"""
    
    def __init__(self, db_manager: Database, ai_processor: AIProcessor, config: Dict[str, Any]):
        self.db = db_manager
        self.ai_processor = ai_processor
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize Telegram notifier
        self.telegram_notifier = create_telegram_notifier(config)
        
        # List of monitored users
        self.monitored_users = config.get('MONITORED_USERS', 'elonmusk,naval,paulg').split(',')
        self.monitored_users = [user.strip() for user in self.monitored_users]
        
        self.logger.info(f"Webhook handler initialized for users: {self.monitored_users}")
    
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify the webhook signature from Twitter"""
        if not signature or not secret:
            return False
            
        # Twitter sends signature as 'sha256=<hash>'
        expected_signature = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def process_webhook_event(self, event_data: Dict[str, Any], signature: str = None) -> Dict[str, Any]:
        """Process incoming webhook event from Twitter"""
        try:
            # Verify signature if provided
            webhook_secret = self.config.get('TWITTER_WEBHOOK_SECRET')
            if webhook_secret and signature:
                payload_bytes = json.dumps(event_data, separators=(',', ':')).encode('utf-8')
                if not self.verify_webhook_signature(payload_bytes, signature, webhook_secret):
                    self.logger.warning("Invalid webhook signature")
                    return {"status": "error", "message": "Invalid signature"}
            
            # Handle different event types
            if 'tweet_create_events' in event_data:
                return self._handle_tweet_events(event_data['tweet_create_events'])
            elif 'user' in event_data and 'text' in event_data:
                # Direct tweet object
                return self._handle_single_tweet(event_data)
            else:
                self.logger.info(f"Unhandled webhook event type: {list(event_data.keys())}")
                return {"status": "ignored", "message": "Event type not handled"}
                
        except Exception as e:
            self.logger.error(f"Error processing webhook event: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _handle_tweet_events(self, tweet_events: list) -> Dict[str, Any]:
        """Handle multiple tweet events"""
        processed_count = 0
        
        for tweet_data in tweet_events:
            result = self._handle_single_tweet(tweet_data)
            if result.get("status") == "success":
                processed_count += 1
        
        return {
            "status": "success",
            "message": f"Processed {processed_count}/{len(tweet_events)} tweets"
        }
    
    def _handle_single_tweet(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single tweet event"""
        try:
            # Extract user information
            user_data = tweet_data.get('user', {})
            username = user_data.get('screen_name', '').lower()
            
            # Check if this user is in our monitoring list
            if username not in self.monitored_users:
                self.logger.debug(f"Tweet from unmonitored user: {username}")
                return {"status": "ignored", "message": f"User {username} not monitored"}
            
            # Parse tweet data
            parsed_tweet = self._parse_webhook_tweet(tweet_data)
            
            # Store in database
            tweet_id = self.db.store_tweet(parsed_tweet)
            
            # Process with AI immediately
            try:
                ai_result = self.ai_processor.process_tweet(parsed_tweet)
                if ai_result:
                    self.db.store_ai_result(tweet_id, ai_result)
                    self.logger.info(f"AI processed webhook tweet {tweet_id}")
                    
                    # Send Telegram notification
                    if self.telegram_notifier:
                        try:
                            self.telegram_notifier.send_notification(parsed_tweet, ai_result)
                            self.db.mark_telegram_sent(tweet_id)
                            self.logger.info(f"Telegram notification sent for tweet {tweet_id}")
                        except Exception as e:
                            self.logger.error(f"Failed to send Telegram notification: {str(e)}")
                            
            except Exception as e:
                self.logger.error(f"Failed to process tweet {tweet_id} with AI: {str(e)}")
            
            self.logger.info(f"Successfully processed webhook tweet {tweet_id} from @{username}")
            
            return {
                "status": "success",
                "tweet_id": tweet_id,
                "username": username,
                "message": "Tweet processed successfully"
            }
            
        except Exception as e:
            self.logger.error(f"Error handling single tweet: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _parse_webhook_tweet(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse tweet data from webhook format to our internal format"""
        user_data = tweet_data.get('user', {})
        
        # Extract media
        media = []
        entities = tweet_data.get('entities', {})
        extended_entities = tweet_data.get('extended_entities', {})
        
        # Process media from entities
        for media_item in extended_entities.get('media', []):
            media.append({
                'type': media_item.get('type', 'photo'),
                'url': media_item.get('media_url_https', media_item.get('media_url', '')),
                'display_url': media_item.get('display_url', '')
            })
        
        # Extract URLs
        urls = []
        for url_item in entities.get('urls', []):
            urls.append({
                'url': url_item.get('url', ''),
                'expanded_url': url_item.get('expanded_url', ''),
                'display_url': url_item.get('display_url', '')
            })
        
        # Extract hashtags
        hashtags = [tag.get('text', '') for tag in entities.get('hashtags', [])]
        
        # Extract mentions
        mentions = [mention.get('screen_name', '') for mention in entities.get('user_mentions', [])]
        
        # Determine tweet type
        tweet_type = 'tweet'
        if tweet_data.get('in_reply_to_status_id'):
            tweet_type = 'reply'
        elif tweet_data.get('retweeted_status'):
            tweet_type = 'retweet'
        elif tweet_data.get('quoted_status'):
            tweet_type = 'quote'
        
        return {
            'id': str(tweet_data.get('id_str', tweet_data.get('id', ''))),
            'username': user_data.get('screen_name', ''),
            'display_name': user_data.get('name', ''),
            'profile_picture': user_data.get('profile_image_url_https', ''),
            'content': tweet_data.get('full_text', tweet_data.get('text', '')),
            'created_at': tweet_data.get('created_at', ''),
            'tweet_type': tweet_type,
            'metrics': {
                'likes': tweet_data.get('favorite_count', 0),
                'retweets': tweet_data.get('retweet_count', 0),
                'replies': tweet_data.get('reply_count', 0),
                'views': tweet_data.get('view_count', 0)
            },
            'media': media,
            'urls': urls,
            'hashtags': hashtags,
            'mentions': mentions,
            'detected_at': datetime.utcnow().isoformat()
        }
    
    def handle_crc_challenge(self, crc_token: str) -> Dict[str, str]:
        """Handle Twitter's CRC challenge for webhook verification"""
        webhook_secret = self.config.get('TWITTER_WEBHOOK_SECRET', '')
        
        if not webhook_secret:
            raise ValueError("TWITTER_WEBHOOK_SECRET not configured")
        
        # Create HMAC SHA256 hash
        hash_digest = hmac.new(
            webhook_secret.encode('utf-8'),
            crc_token.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Return base64 encoded response
        import base64
        response_token = base64.b64encode(hash_digest).decode('utf-8')
        
        return {
            "response_token": f"sha256={response_token}"
        } 