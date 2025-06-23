import requests
import time
import logging
from typing import List, Dict, Optional
from requests.exceptions import RequestException
from datetime import datetime, timedelta


class TwitterClient:
    """
    Twitter API client using TwitterAPI.io service
    Handles tweet fetching, rate limiting, and error recovery
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Twitter client
        
        Args:
            api_key: TwitterAPI.io API key
        """
        self.api_key = api_key
        self.base_url = "https://api.twitterapi.io"
        self.headers = {"x-api-key": api_key}
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting configuration
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 0
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
    
    def validate_api_key(self) -> bool:
        """
        Validate that API key is provided and not empty
        
        Returns:
            bool: True if API key is valid format
        """
        return bool(self.api_key and self.api_key.strip())
    
    def get_user_tweets(self, username: str, count: int = 20) -> List[Dict]:
        """
        Fetch latest tweets from a specific user
        
        Args:
            username: Twitter username (without @)
            count: Number of tweets to fetch (default: 20, max: 100)
            
        Returns:
            List of parsed tweet dictionaries
        """
        if not self.validate_api_key():
            self.logger.error("Invalid API key provided")
            return []
        
        # Respect rate limiting
        self._wait_for_rate_limit()
        
        try:
            url = f"{self.base_url}/twitter/user/last_tweets"
            params = {
                "userName": username,
                "count": min(count, 100)  # Limit to API maximum
            }
            
            self.logger.info(f"Fetching {count} tweets for user: {username}")
            
            response = requests.get(
                url, 
                headers=self.headers, 
                params=params,
                timeout=30
            )
            
            # Update rate limit info from response headers
            self._update_rate_limit_info(response)
            
            response.raise_for_status()
            
            data = response.json()
            # Handle the new API response structure
            if data.get('status') == 'success' and 'data' in data:
                tweets_data = data['data'].get('tweets', [])
                tweets = self._parse_tweets(tweets_data)
            else:
                tweets = []
            
            self.logger.info(f"Successfully fetched {len(tweets)} tweets for {username}")
            return tweets
            
        except RequestException as e:
            if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                self.logger.warning(f"Rate limit exceeded for user {username}")
                self._handle_rate_limit(e.response)
            else:
                self.logger.error(f"Error fetching tweets for {username}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching tweets for {username}: {e}")
            return []
    
    def get_multiple_users_tweets(self, usernames: List[str], count: int = 20) -> List[Dict]:
        """
        Fetch tweets from multiple users
        
        Args:
            usernames: List of Twitter usernames
            count: Number of tweets per user
            
        Returns:
            Combined list of tweets from all users
        """
        all_tweets = []
        
        for username in usernames:
            user_tweets = self.get_user_tweets(username, count)
            all_tweets.extend(user_tweets)
            
            # Small delay between users to be respectful
            time.sleep(0.5)
        
        # Sort by creation date (newest first)
        all_tweets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return all_tweets

    def get_historical_tweets(self, usernames: List[str], hours: int = 2) -> List[Dict]:
        """
        Fetch tweets from the last N hours for multiple users
        
        Args:
            usernames: List of Twitter usernames
            hours: Number of hours to look back (default: 2)
            
        Returns:
            List of tweets from the specified time period
        """
        self.logger.info(f"Fetching tweets from last {hours} hours for users: {usernames}")
        
        # Calculate cutoff time in UTC (timezone-naive)
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        all_tweets = []
        
        for username in usernames:
            # Fetch more tweets to ensure we get enough from the time period
            user_tweets = self.get_user_tweets(username, count=50)
            
            # Filter tweets by time
            recent_tweets = []
            for tweet in user_tweets:
                try:
                    # Parse tweet creation time
                    tweet_time = self._parse_tweet_time(tweet.get('created_at', ''))
                    if tweet_time and tweet_time >= cutoff_time:
                        recent_tweets.append(tweet)
                except Exception as e:
                    self.logger.warning(f"Error parsing tweet time for {username}: {e}")
                    continue
            
            all_tweets.extend(recent_tweets)
            self.logger.info(f"Found {len(recent_tweets)} tweets from last {hours}h for {username}")
            
            # Small delay between users
            time.sleep(0.5)
        
        # Sort by creation date (newest first)
        all_tweets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        self.logger.info(f"Total historical tweets found: {len(all_tweets)}")
        return all_tweets

    def _parse_tweet_time(self, time_str: str) -> Optional[datetime]:
        """
        Parse tweet creation time from various possible formats
        
        Args:
            time_str: Time string from Twitter API
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not time_str:
            return None
        
        # Common Twitter API time formats
        time_formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with microseconds
            '%Y-%m-%dT%H:%M:%SZ',     # ISO format without microseconds
            '%a %b %d %H:%M:%S %z %Y', # Twitter v1.1 format (e.g., "Sun Jun 22 03:59:03 +0000 2025")
            '%Y-%m-%d %H:%M:%S',      # Simple format
        ]
        
        for fmt in time_formats:
            try:
                parsed_time = datetime.strptime(time_str, fmt)
                
                # FIX: Correct year issue - if parsed year is 2025 but month/day suggests 2024
                if parsed_time.year == 2025:
                    current_date = datetime.utcnow()
                    # If the parsed date is more than 1 day in the future, it's likely 2024
                    if parsed_time > current_date + timedelta(days=1):
                        parsed_time = parsed_time.replace(year=2024)
                        self.logger.warning(f"Corrected year from 2025 to 2024 for: {time_str}")
                
                # If the parsed time is timezone-aware, convert to UTC then make naive
                if parsed_time.tzinfo is not None:
                    # Convert to UTC and remove timezone info
                    parsed_time = parsed_time.utctimetuple()
                    parsed_time = datetime(*parsed_time[:6])
                return parsed_time
            except ValueError:
                continue
        
        # Try parsing relative time (e.g., "2h", "30m")
        try:
            if time_str.endswith('h'):
                hours_ago = int(time_str[:-1])
                return datetime.utcnow() - timedelta(hours=hours_ago)
            elif time_str.endswith('m'):
                minutes_ago = int(time_str[:-1])
                return datetime.utcnow() - timedelta(minutes=minutes_ago)
            elif time_str.endswith('s'):
                seconds_ago = int(time_str[:-1])
                return datetime.utcnow() - timedelta(seconds=seconds_ago)
        except ValueError:
            pass
        
        self.logger.warning(f"Could not parse time format: {time_str}")
        return None
    
    def _parse_tweets(self, tweets_data: List[Dict]) -> List[Dict]:
        """
        Parse raw tweet data from API response into standardized format
        
        Args:
            tweets_data: Raw tweet data from API
            
        Returns:
            List of standardized tweet dictionaries
        """
        parsed_tweets = []
        
        for tweet in tweets_data:
            try:
                author = tweet.get('author', {})
                
                # Get complete tweet text (handle retweets properly)
                content = self._get_complete_text(tweet)
                
                parsed_tweet = {
                    'id': tweet.get('id', ''),
                    'username': author.get('userName', ''),
                    'display_name': author.get('name', ''),
                    'profile_picture': author.get('profilePicture', ''),
                    'content': content,
                    'created_at': tweet.get('createdAt', ''),
                    'tweet_type': self._determine_tweet_type(tweet),
                    'metrics': {
                        'likes': tweet.get('likeCount', 0),
                        'retweets': tweet.get('retweetCount', 0),
                        'replies': tweet.get('replyCount', 0),
                        'views': tweet.get('viewCount', 0)
                    },
                    'media': self._extract_media(tweet),
                    'urls': self._extract_urls(tweet),
                    'hashtags': self._extract_hashtags(tweet),
                    'mentions': self._extract_mentions(tweet)
                }
                
                parsed_tweets.append(parsed_tweet)
                
            except Exception as e:
                self.logger.error(f"Error parsing tweet {tweet.get('id', 'unknown')}: {e}")
                continue
        
        return parsed_tweets
    
    def _get_complete_text(self, tweet: Dict) -> str:
        """
        Get complete tweet text, handling retweets and truncated content
        
        Args:
            tweet: Raw tweet data
            
        Returns:
            Complete tweet text
        """
        # Check if this is a retweet with complete text in retweeted_tweet
        if tweet.get('retweeted_tweet') and tweet['retweeted_tweet'].get('text'):
            # For retweets, get the original tweet text and prepend RT info
            original_text = tweet['retweeted_tweet']['text']
            original_author = tweet['retweeted_tweet'].get('author', {}).get('userName', 'unknown')
            return f"RT @{original_author}: {original_text}"
        
        # Check if this is a quote tweet with complete text
        elif tweet.get('quoted_tweet') and tweet['quoted_tweet'].get('text'):
            # For quote tweets, combine the quote text with original
            quote_text = tweet.get('text', '')
            quoted_text = tweet['quoted_tweet']['text']
            quoted_author = tweet['quoted_tweet'].get('author', {}).get('userName', 'unknown')
            
            # Remove the t.co link from quote text if present
            import re
            quote_text = re.sub(r'https://t\.co/\w+$', '', quote_text).strip()
            
            return f"{quote_text}\n\nQuoting @{quoted_author}: {quoted_text}"
        
        # For regular tweets, return the text as-is
        else:
            return tweet.get('text', '')
    
    def _extract_media(self, tweet: Dict) -> List[Dict]:
        """
        Extract media information from tweet, including from retweets and quotes
        
        Args:
            tweet: Raw tweet data
            
        Returns:
            List of media dictionaries
        """
        media_items = []
        
        # Helper function to extract media from a tweet object
        def extract_from_tweet_obj(tweet_obj):
            items = []
            
            # Check for media in main tweet
            if 'media' in tweet_obj and tweet_obj['media']:
                for media in tweet_obj['media']:
                    media_item = {
                        'type': media.get('type', 'unknown'),
                        'url': media.get('url', ''),
                        'width': media.get('width'),
                        'height': media.get('height'),
                        'duration': media.get('duration'),  # For videos
                        'preview_image': media.get('previewImage'),  # Video thumbnails
                        'alt_text': media.get('altText', '')
                    }
                    items.append(media_item)
            
            # Check for extended entities (more detailed media info)
            if 'extendedEntities' in tweet_obj and 'media' in tweet_obj['extendedEntities']:
                for media in tweet_obj['extendedEntities']['media']:
                    media_item = {
                        'type': media.get('type', 'unknown'),
                        'url': media.get('media_url_https', media.get('url', '')),
                        'width': media.get('original_info', {}).get('width'),
                        'height': media.get('original_info', {}).get('height'),
                        'alt_text': media.get('alt_text', ''),
                        'expanded_url': media.get('expanded_url', '')
                    }
                    
                    # For videos, extract video info
                    if media.get('type') == 'video' and 'video_info' in media:
                        video_info = media['video_info']
                        media_item['duration'] = video_info.get('duration_millis')
                        media_item['aspect_ratio'] = video_info.get('aspect_ratio', [])
                        
                        # Get the highest quality video URL
                        if 'variants' in video_info:
                            best_variant = None
                            best_bitrate = 0
                            for variant in video_info['variants']:
                                if variant.get('content_type') == 'video/mp4':
                                    bitrate = variant.get('bitrate', 0)
                                    if bitrate > best_bitrate:
                                        best_bitrate = bitrate
                                        best_variant = variant
                            
                            if best_variant:
                                # Use the video URL as the main URL for downloading
                                media_item['url'] = best_variant['url']
                                media_item['video_url'] = best_variant['url']
                                media_item['bitrate'] = best_variant.get('bitrate')
                                media_item['thumbnail_url'] = media.get('media_url_https', '')
                    
                    # For animated GIFs, treat as video
                    elif media.get('type') == 'animated_gif' and 'video_info' in media:
                        video_info = media['video_info']
                        media_item['duration'] = video_info.get('duration_millis')
                        
                        # For GIFs, get the mp4 variant (Twitter converts GIFs to mp4)
                        if 'variants' in video_info:
                            for variant in video_info['variants']:
                                if variant.get('content_type') == 'video/mp4':
                                    media_item['url'] = variant['url']
                                    media_item['video_url'] = variant['url']
                                    break
                    
                    items.append(media_item)
            
            return items
        
        # Extract media from main tweet
        media_items.extend(extract_from_tweet_obj(tweet))
        
        # Extract media from retweeted tweet
        if tweet.get('retweeted_tweet'):
            media_items.extend(extract_from_tweet_obj(tweet['retweeted_tweet']))
        
        # Extract media from quoted tweet
        if tweet.get('quoted_tweet'):
            media_items.extend(extract_from_tweet_obj(tweet['quoted_tweet']))
        
        return media_items
    
    def _extract_urls(self, tweet: Dict) -> List[str]:
        """Extract URLs from tweet"""
        urls = []
        if 'entities' in tweet and 'urls' in tweet['entities']:
            for url_entity in tweet['entities']['urls']:
                urls.append(url_entity.get('expanded_url', url_entity.get('url', '')))
        return urls
    
    def _extract_hashtags(self, tweet: Dict) -> List[str]:
        """Extract hashtags from tweet"""
        hashtags = []
        if 'entities' in tweet and 'hashtags' in tweet['entities']:
            for hashtag in tweet['entities']['hashtags']:
                hashtags.append(hashtag.get('text', ''))
        return hashtags
    
    def _extract_mentions(self, tweet: Dict) -> List[str]:
        """Extract user mentions from tweet"""
        mentions = []
        if 'entities' in tweet and 'user_mentions' in tweet['entities']:
            for mention in tweet['entities']['user_mentions']:
                mentions.append(mention.get('screen_name', ''))
        return mentions
    
    def _determine_tweet_type(self, tweet: Dict) -> str:
        """
        Determine the type of tweet (original, reply, retweet, quote)
        
        Args:
            tweet: Raw tweet data
            
        Returns:
            Tweet type string
        """
        if tweet.get('in_reply_to_status_id'):
            return 'reply'
        elif tweet.get('retweeted_status'):
            return 'retweet'  
        elif tweet.get('quoted_status'):
            return 'quote'
        else:
            return 'tweet'
    
    def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()
        
        # Ensure minimum interval between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        # If we're rate limited, wait until reset
        if self.rate_limit_remaining <= 1 and current_time < self.rate_limit_reset:
            wait_time = self.rate_limit_reset - current_time + 1
            self.logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _update_rate_limit_info(self, response):
        """Update rate limit information from response headers"""
        headers = response.headers
        
        if 'x-rate-limit-remaining' in headers:
            self.rate_limit_remaining = int(headers['x-rate-limit-remaining'])
        
        if 'x-rate-limit-reset' in headers:
            self.rate_limit_reset = int(headers['x-rate-limit-reset'])
    
    def _handle_rate_limit(self, response):
        """Handle rate limit response"""
        reset_time = response.headers.get('x-rate-limit-reset')
        if reset_time:
            self.rate_limit_reset = int(reset_time)
            wait_time = self.rate_limit_reset - time.time() + 1
            self.logger.warning(f"Rate limited, reset in {wait_time:.1f} seconds")
    
    def get_api_status(self) -> Dict:
        """
        Get current API status and rate limit information
        
        Returns:
            Dictionary with API status information
        """
        return {
            'api_key_valid': self.validate_api_key(),
            'rate_limit_remaining': self.rate_limit_remaining,
            'rate_limit_reset': self.rate_limit_reset,
            'last_request_time': self.last_request_time
        } 