import unittest
from unittest.mock import patch, MagicMock
import json
from core.twitter_client import TwitterClient


class TestTwitterClient(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test_api_key"
        self.client = TwitterClient(self.api_key)
        
        # Mock tweet data
        self.mock_tweet_response = {
            "tweets": [
                {
                    "id": "1234567890",
                    "text": "This is a test tweet with media",
                    "createdAt": "2024-12-28T12:00:00Z",
                    "author": {
                        "userName": "testuser",
                        "name": "Test User",
                        "profilePicture": "https://example.com/profile.jpg"
                    },
                    "likeCount": 10,
                    "retweetCount": 5,
                    "replyCount": 2,
                    "viewCount": 100,
                    "media": [
                        {
                            "type": "image",
                            "url": "https://example.com/image.jpg",
                            "width": 1200,
                            "height": 800
                        }
                    ]
                },
                {
                    "id": "1234567891",
                    "text": "Another test tweet without media",
                    "createdAt": "2024-12-28T11:30:00Z",
                    "author": {
                        "userName": "testuser",
                        "name": "Test User",
                        "profilePicture": "https://example.com/profile.jpg"
                    },
                    "likeCount": 25,
                    "retweetCount": 8,
                    "replyCount": 3,
                    "viewCount": 200
                }
            ]
        }
    
    def test_init_sets_correct_attributes(self):
        """Test that client initializes with correct attributes"""
        self.assertEqual(self.client.api_key, "test_api_key")
        self.assertEqual(self.client.base_url, "https://api.twitterapi.io")
        self.assertEqual(self.client.headers["x-api-key"], "test_api_key")
    
    @patch('core.twitter_client.requests.get')
    def test_get_user_tweets_success(self, mock_get):
        """Test successful retrieval of user tweets"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_tweet_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Call method
        result = self.client.get_user_tweets("testuser", count=20)
        
        # Verify API call
        mock_get.assert_called_once_with(
            "https://api.twitterapi.io/twitter/user/tweets",
            headers={"x-api-key": "test_api_key"},
            params={"userName": "testuser", "count": 20}
        )
        
        # Verify parsed results
        self.assertEqual(len(result), 2)
        
        # Check first tweet
        tweet1 = result[0]
        self.assertEqual(tweet1["id"], "1234567890")
        self.assertEqual(tweet1["username"], "testuser")
        self.assertEqual(tweet1["display_name"], "Test User")
        self.assertEqual(tweet1["content"], "This is a test tweet with media")
        self.assertEqual(tweet1["created_at"], "2024-12-28T12:00:00Z")
        self.assertEqual(tweet1["metrics"]["likes"], 10)
        self.assertEqual(tweet1["metrics"]["retweets"], 5)
        self.assertEqual(tweet1["metrics"]["replies"], 2)
        self.assertEqual(len(tweet1["media"]), 1)
        self.assertEqual(tweet1["media"][0]["type"], "image")
        self.assertEqual(tweet1["media"][0]["url"], "https://example.com/image.jpg")
        
        # Check second tweet (no media)
        tweet2 = result[1]
        self.assertEqual(tweet2["id"], "1234567891")
        self.assertEqual(len(tweet2["media"]), 0)
    
    @patch('core.twitter_client.requests.get')
    def test_get_user_tweets_api_error(self, mock_get):
        """Test handling of API errors"""
        # Mock API error response
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response
        
        # Call method
        result = self.client.get_user_tweets("testuser")
        
        # Should return empty list on error
        self.assertEqual(result, [])
    
    @patch('core.twitter_client.requests.get')
    def test_get_user_tweets_rate_limit_handling(self, mock_get):
        """Test handling of rate limit responses"""
        # Mock rate limit response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"x-rate-limit-reset": "1640995200"}
        mock_response.raise_for_status.side_effect = Exception("Rate limit exceeded")
        mock_get.return_value = mock_response
        
        # Call method
        result = self.client.get_user_tweets("testuser")
        
        # Should return empty list and log rate limit
        self.assertEqual(result, [])
    
    @patch('core.twitter_client.requests.get')
    def test_get_multiple_users_tweets(self, mock_get):
        """Test fetching tweets from multiple users"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_tweet_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Call method
        usernames = ["user1", "user2", "user3"]
        result = self.client.get_multiple_users_tweets(usernames)
        
        # Should make 3 API calls
        self.assertEqual(mock_get.call_count, 3)
        
        # Should return combined results
        self.assertEqual(len(result), 6)  # 2 tweets * 3 users
    
    def test_parse_tweets_handles_missing_fields(self):
        """Test parsing tweets with missing optional fields"""
        incomplete_tweet_data = {
            "tweets": [
                {
                    "id": "123",
                    "text": "Minimal tweet",
                    "author": {
                        "userName": "user"
                    }
                }
            ]
        }
        
        result = self.client._parse_tweets(incomplete_tweet_data["tweets"])
        
        self.assertEqual(len(result), 1)
        tweet = result[0]
        self.assertEqual(tweet["id"], "123")
        self.assertEqual(tweet["username"], "user")
        self.assertEqual(tweet["display_name"], "")  # Should handle missing name
        self.assertEqual(tweet["metrics"]["likes"], 0)  # Should default to 0
        self.assertEqual(len(tweet["media"]), 0)  # Should handle missing media
    
    def test_extract_media_various_types(self):
        """Test media extraction for different media types"""
        tweet_with_media = {
            "media": [
                {
                    "type": "image",
                    "url": "https://example.com/image.jpg",
                    "width": 1200,
                    "height": 800
                },
                {
                    "type": "video",
                    "url": "https://example.com/video.mp4",
                    "width": 1920,
                    "height": 1080,
                    "duration": 30
                },
                {
                    "type": "gif",
                    "url": "https://example.com/animation.gif"
                }
            ]
        }
        
        result = self.client._extract_media(tweet_with_media)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["type"], "image")
        self.assertEqual(result[1]["type"], "video")
        self.assertEqual(result[2]["type"], "gif")
    
    def test_validate_api_key(self):
        """Test API key validation"""
        # Test valid key format
        self.assertTrue(self.client.validate_api_key())
        
        # Test invalid key
        invalid_client = TwitterClient("")
        self.assertFalse(invalid_client.validate_api_key())
    
    @patch('core.twitter_client.requests.get')
    def test_get_user_tweets_default_count(self, mock_get):
        """Test default tweet count parameter"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"tweets": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Call without count parameter
        self.client.get_user_tweets("testuser")
        
        # Should use default count of 20
        mock_get.assert_called_once_with(
            "https://api.twitterapi.io/twitter/user/tweets",
            headers={"x-api-key": "test_api_key"},
            params={"userName": "testuser", "count": 20}
        )


if __name__ == '__main__':
    unittest.main() 