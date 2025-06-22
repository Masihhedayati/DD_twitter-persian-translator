import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import json
from datetime import datetime, timedelta
from core.openai_client import OpenAIClient


class TestOpenAIClient(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.api_key = "test_openai_api_key"
        self.client = OpenAIClient(self.api_key)
        
        # Mock tweet data
        self.mock_tweet = {
            'id': '1234567890',
            'username': 'testuser',
            'content': 'This is a test tweet about AI and technology. Very interesting developments!',
            'created_at': '2024-12-28T12:00:00Z'
        }
        
        # Mock OpenAI response
        self.mock_openai_response = {
            'choices': [
                {
                    'message': {
                        'content': json.dumps({
                            'sentiment': 'positive',
                            'topics': ['AI', 'technology'],
                            'summary': 'Tweet discusses AI and technology developments',
                            'keywords': ['AI', 'technology', 'developments'],
                            'confidence': 0.85
                        })
                    }
                }
            ],
            'usage': {
                'prompt_tokens': 150,
                'completion_tokens': 50,
                'total_tokens': 200
            },
            'model': 'gpt-3.5-turbo'
        }
    
    def test_init_creates_client(self):
        """Test OpenAI client initialization"""
        self.assertEqual(self.client.api_key, self.api_key)
        self.assertIsNotNone(self.client.default_model)
        self.assertIsNotNone(self.client.prompt_templates)
        self.assertEqual(self.client.max_retries, 3)
        self.assertEqual(self.client.request_timeout, 30)
    
    def test_validate_api_key_valid(self):
        """Test API key validation with valid key"""
        # Valid key should be 20+ characters starting with 'sk-'
        valid_key = "sk-" + "x" * 45
        client = OpenAIClient(valid_key)
        self.assertTrue(client.validate_api_key())
    
    def test_validate_api_key_invalid(self):
        """Test API key validation with invalid keys"""
        # Empty key
        client = OpenAIClient("")
        self.assertFalse(client.validate_api_key())
        
        # Too short
        client = OpenAIClient("sk-short")
        self.assertFalse(client.validate_api_key())
        
        # Wrong format
        client = OpenAIClient("invalid-key-format")
        self.assertFalse(client.validate_api_key())
    
    def test_get_prompt_template_default(self):
        """Test getting default prompt template"""
        template = self.client.get_prompt_template('default')
        
        self.assertIsNotNone(template)
        self.assertIn('{tweet_content}', template)
        self.assertIn('sentiment', template.lower())
        self.assertIn('topics', template.lower())
    
    def test_get_prompt_template_custom(self):
        """Test getting custom prompt template"""
        # Add custom template
        custom_template = "Analyze this tweet: {tweet_content}. Focus on emotions."
        self.client.add_prompt_template('emotion_analysis', custom_template)
        
        retrieved = self.client.get_prompt_template('emotion_analysis')
        self.assertEqual(retrieved, custom_template)
    
    def test_get_prompt_template_nonexistent(self):
        """Test getting non-existent prompt template returns default"""
        template = self.client.get_prompt_template('nonexistent')
        default_template = self.client.get_prompt_template('default')
        self.assertEqual(template, default_template)
    
    def test_format_prompt(self):
        """Test prompt formatting with tweet data"""
        template = "Analyze: {tweet_content} by @{username}"
        
        formatted = self.client._format_prompt(template, self.mock_tweet)
        
        expected = "Analyze: This is a test tweet about AI and technology. Very interesting developments! by @testuser"
        self.assertEqual(formatted, expected)
    
    def test_format_prompt_missing_field(self):
        """Test prompt formatting with missing tweet field"""
        template = "Analyze: {tweet_content} with {missing_field}"
        
        formatted = self.client._format_prompt(template, self.mock_tweet)
        
        # Should replace missing fields with empty string
        expected = "Analyze: This is a test tweet about AI and technology. Very interesting developments! with "
        self.assertEqual(formatted, expected)
    
    def test_count_tokens_approximate(self):
        """Test token counting approximation"""
        text = "This is a test tweet about AI and technology."
        
        tokens = self.client._count_tokens_approximate(text)
        
        # Should be reasonable approximation (roughly 1 token per 4 characters)
        self.assertGreater(tokens, 5)
        self.assertLess(tokens, 20)
    
    def test_validate_response_valid(self):
        """Test response validation with valid JSON response"""
        valid_response = json.dumps({
            'sentiment': 'positive',
            'topics': ['AI', 'technology'],
            'summary': 'Test summary'
        })
        
        is_valid, parsed = self.client._validate_response(valid_response)
        
        self.assertTrue(is_valid)
        self.assertEqual(parsed['sentiment'], 'positive')
        self.assertEqual(len(parsed['topics']), 2)
    
    def test_validate_response_invalid_json(self):
        """Test response validation with invalid JSON"""
        invalid_response = "This is not valid JSON"
        
        is_valid, parsed = self.client._validate_response(invalid_response)
        
        self.assertFalse(is_valid)
        self.assertIsNone(parsed)
    
    def test_validate_response_missing_fields(self):
        """Test response validation with missing required fields"""
        incomplete_response = json.dumps({
            'sentiment': 'positive'
            # Missing topics and summary
        })
        
        is_valid, parsed = self.client._validate_response(incomplete_response)
        
        # Should still be valid but may have warnings
        self.assertTrue(is_valid)
        self.assertEqual(parsed['sentiment'], 'positive')
    
    @patch('openai.ChatCompletion.acreate')
    def test_analyze_tweet_success(self, mock_create):
        """Test successful tweet analysis"""
        # Mock OpenAI API response
        mock_create.return_value = self.mock_openai_response
        
        # Run async test
        async def run_test():
            result = await self.client.analyze_tweet_async(self.mock_tweet)
            
            # Verify result structure
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['tweet_id'], '1234567890')
            self.assertIn('ai_result', result)
            self.assertIn('tokens_used', result)
            self.assertIn('model_used', result)
            self.assertIn('processing_time', result)
            
            # Verify AI result content
            ai_result = result['ai_result']
            self.assertEqual(ai_result['sentiment'], 'positive')
            self.assertEqual(ai_result['topics'], ['AI', 'technology'])
        
        asyncio.run(run_test())
    
    @patch('openai.ChatCompletion.acreate')
    def test_analyze_tweet_api_error(self, mock_create):
        """Test tweet analysis with API error"""
        # Mock API error
        mock_create.side_effect = Exception("API rate limit exceeded")
        
        async def run_test():
            result = await self.client.analyze_tweet_async(self.mock_tweet)
            
            # Verify error handling
            self.assertEqual(result['status'], 'failed')
            self.assertIn('error_message', result)
            self.assertIn('rate limit', result['error_message'])
        
        asyncio.run(run_test())
    
    @patch('openai.ChatCompletion.acreate')
    def test_analyze_tweet_with_retry(self, mock_create):
        """Test tweet analysis with retry logic"""
        # Mock first call fails, second succeeds
        mock_create.side_effect = [
            Exception("Temporary error"),
            self.mock_openai_response
        ]
        
        async def run_test():
            result = await self.client.analyze_tweet_async(self.mock_tweet)
            
            # Should succeed after retry
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(mock_create.call_count, 2)
        
        asyncio.run(run_test())
    
    def test_analyze_tweet_sync_wrapper(self):
        """Test synchronous wrapper for tweet analysis"""
        with patch.object(self.client, 'analyze_tweet_async') as mock_async:
            mock_async.return_value = {'status': 'completed'}
            
            result = self.client.analyze_tweet(self.mock_tweet)
            
            self.assertEqual(result['status'], 'completed')
            mock_async.assert_called_once_with(self.mock_tweet, 'default')
    
    @patch('openai.ChatCompletion.acreate')
    def test_analyze_tweets_batch(self, mock_create):
        """Test batch processing of multiple tweets"""
        # Mock successful responses
        mock_create.return_value = self.mock_openai_response
        
        tweets = [self.mock_tweet, {**self.mock_tweet, 'id': '1234567891'}]
        
        async def run_test():
            results = await self.client.analyze_tweets_batch_async(tweets)
            
            # Should process both tweets
            self.assertEqual(len(results), 2)
            for result in results:
                self.assertEqual(result['status'], 'completed')
        
        asyncio.run(run_test())
    
    def test_get_usage_stats(self):
        """Test getting usage statistics"""
        # Add some mock usage
        self.client.total_tokens_used = 1000
        self.client.total_requests = 5
        self.client.total_cost = 0.05
        
        stats = self.client.get_usage_stats()
        
        self.assertEqual(stats['total_tokens_used'], 1000)
        self.assertEqual(stats['total_requests'], 5)
        self.assertEqual(stats['total_cost'], 0.05)
        self.assertIn('avg_tokens_per_request', stats)
    
    def test_calculate_cost(self):
        """Test cost calculation for different models"""
        # Test GPT-3.5-turbo cost
        cost_35 = self.client._calculate_cost(1000, 'gpt-3.5-turbo')
        self.assertGreater(cost_35, 0)
        
        # Test GPT-4 cost (should be more expensive)
        cost_4 = self.client._calculate_cost(1000, 'gpt-4')
        self.assertGreater(cost_4, cost_35)
    
    def test_reset_usage_stats(self):
        """Test resetting usage statistics"""
        # Set some usage
        self.client.total_tokens_used = 1000
        self.client.total_requests = 5
        
        self.client.reset_usage_stats()
        
        # Should be reset to zero
        self.assertEqual(self.client.total_tokens_used, 0)
        self.assertEqual(self.client.total_requests, 0)
        self.assertEqual(self.client.total_cost, 0.0)
    
    def test_add_custom_prompt_template(self):
        """Test adding custom prompt templates"""
        template_name = "custom_sentiment"
        template_content = "What is the sentiment of: {tweet_content}?"
        
        success = self.client.add_prompt_template(template_name, template_content)
        
        self.assertTrue(success)
        self.assertIn(template_name, self.client.prompt_templates)
        self.assertEqual(self.client.prompt_templates[template_name], template_content)
    
    def test_remove_prompt_template(self):
        """Test removing prompt templates"""
        # Add then remove template
        self.client.add_prompt_template('temp_template', 'Test template')
        
        success = self.client.remove_prompt_template('temp_template')
        
        self.assertTrue(success)
        self.assertNotIn('temp_template', self.client.prompt_templates)
        
        # Test removing non-existent template
        success = self.client.remove_prompt_template('nonexistent')
        self.assertFalse(success)
    
    def test_get_available_models(self):
        """Test getting list of available models"""
        models = self.client.get_available_models()
        
        self.assertIsInstance(models, list)
        self.assertIn('gpt-3.5-turbo', models)
        self.assertIn('gpt-4', models)
    
    def test_set_default_model(self):
        """Test setting default model"""
        original_model = self.client.default_model
        
        success = self.client.set_default_model('gpt-4')
        
        self.assertTrue(success)
        self.assertEqual(self.client.default_model, 'gpt-4')
        
        # Test invalid model
        success = self.client.set_default_model('invalid-model')
        self.assertFalse(success)
        self.assertEqual(self.client.default_model, 'gpt-4')  # Should remain unchanged


if __name__ == '__main__':
    unittest.main() 