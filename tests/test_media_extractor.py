import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import os
import tempfile
import shutil
from core.media_extractor import MediaExtractor


class TestMediaExtractor(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.media_storage_path = os.path.join(self.temp_dir, 'media')
        self.extractor = MediaExtractor(self.media_storage_path)
        
        # Mock tweet with media
        self.mock_tweet = {
            'id': '1234567890',
            'username': 'testuser',
            'created_at': '2024-12-28T12:00:00Z',
            'media': [
                {
                    'type': 'image',
                    'url': 'https://example.com/image.jpg',
                    'width': 1200,
                    'height': 800
                },
                {
                    'type': 'video',
                    'url': 'https://example.com/video.mp4',
                    'width': 1920,
                    'height': 1080,
                    'duration': 30
                }
            ]
        }
        
        # Mock image and video content
        self.mock_image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        self.mock_video_content = b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom'
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_creates_storage_directories(self):
        """Test that initializer creates necessary storage directories"""
        # Check that directories are created
        self.assertTrue(os.path.exists(self.media_storage_path))
        self.assertTrue(os.path.exists(os.path.join(self.media_storage_path, 'images')))
        self.assertTrue(os.path.exists(os.path.join(self.media_storage_path, 'videos')))
        self.assertTrue(os.path.exists(os.path.join(self.media_storage_path, 'audio')))
    
    def test_generate_filename(self):
        """Test filename generation with different media types"""
        # Test image filename
        image_filename = self.extractor._generate_filename(
            '1234567890', 'image', 'https://example.com/image.jpg', 0
        )
        self.assertEqual(image_filename, 'tweet_1234567890_img_0.jpg')
        
        # Test video filename
        video_filename = self.extractor._generate_filename(
            '1234567890', 'video', 'https://example.com/video.mp4', 1
        )
        self.assertEqual(video_filename, 'tweet_1234567890_vid_1.mp4')
        
        # Test filename without extension
        no_ext_filename = self.extractor._generate_filename(
            '1234567890', 'image', 'https://example.com/image', 0
        )
        self.assertEqual(no_ext_filename, 'tweet_1234567890_img_0')
    
    def test_get_media_directory_path(self):
        """Test media directory path generation by date"""
        # Test with specific date
        date_str = '2024-12-28'
        image_dir = self.extractor._get_media_directory_path('image', date_str)
        expected_path = os.path.join(self.media_storage_path, 'images', '2024', '12', '28')
        self.assertEqual(image_dir, expected_path)
        
        # Test video directory
        video_dir = self.extractor._get_media_directory_path('video', date_str)
        expected_path = os.path.join(self.media_storage_path, 'videos', '2024', '12', '28')
        self.assertEqual(video_dir, expected_path)
    
    def test_extract_file_extension(self):
        """Test file extension extraction from URLs"""
        # Test common extensions
        self.assertEqual(self.extractor._extract_file_extension('image.jpg'), '.jpg')
        self.assertEqual(self.extractor._extract_file_extension('video.mp4'), '.mp4')
        self.assertEqual(self.extractor._extract_file_extension('audio.m4a'), '.m4a')
        
        # Test URL with query parameters
        self.assertEqual(self.extractor._extract_file_extension('image.png?size=large'), '.png')
        
        # Test no extension
        self.assertEqual(self.extractor._extract_file_extension('noextension'), '')
    
    @patch('aiohttp.ClientSession.get')
    def test_download_single_media_success(self, mock_get):
        """Test successful download of single media file"""
        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=self.mock_image_content)
        mock_response.headers = {'content-length': '1024', 'content-type': 'image/jpeg'}
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Run async test
        async def run_test():
            media_info = {
                'type': 'image',
                'url': 'https://example.com/image.jpg',
                'width': 1200,
                'height': 800
            }
            
            result = await self.extractor._download_single_media(
                '1234567890', media_info, 0, '2024-12-28'
            )
            
            # Verify result
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['media_type'], 'image')
            self.assertEqual(result['file_size'], 1024)
            self.assertTrue(result['local_path'].endswith('tweet_1234567890_img_0.jpg'))
            
            # Verify file was created
            self.assertTrue(os.path.exists(result['local_path']))
        
        asyncio.run(run_test())
    
    @patch('aiohttp.ClientSession.get')
    def test_download_single_media_http_error(self, mock_get):
        """Test handling of HTTP errors during download"""
        # Mock HTTP error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async def run_test():
            media_info = {
                'type': 'image',
                'url': 'https://example.com/notfound.jpg'
            }
            
            result = await self.extractor._download_single_media(
                '1234567890', media_info, 0, '2024-12-28'
            )
            
            # Verify error handling
            self.assertEqual(result['status'], 'failed')
            self.assertIn('HTTP 404', result['error_message'])
        
        asyncio.run(run_test())
    
    @patch('aiohttp.ClientSession.get')
    def test_download_single_media_with_retry(self, mock_get):
        """Test retry logic on temporary failures"""
        # Mock first call fails, second succeeds
        mock_response_fail = AsyncMock()
        mock_response_fail.status = 500
        
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.read = AsyncMock(return_value=self.mock_image_content)
        mock_response_success.headers = {'content-length': '1024'}
        
        mock_get.return_value.__aenter__.side_effect = [
            mock_response_fail,
            mock_response_success
        ]
        
        async def run_test():
            media_info = {
                'type': 'image',
                'url': 'https://example.com/retry.jpg'
            }
            
            result = await self.extractor._download_single_media(
                '1234567890', media_info, 0, '2024-12-28'
            )
            
            # Should succeed after retry
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(mock_get.call_count, 2)
        
        asyncio.run(run_test())
    
    def test_download_tweet_media_sync(self):
        """Test synchronous wrapper for downloading tweet media"""
        with patch.object(self.extractor, 'download_tweet_media_async') as mock_async:
            mock_async.return_value = [{'status': 'completed'}]
            
            result = self.extractor.download_tweet_media(self.mock_tweet)
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['status'], 'completed')
            mock_async.assert_called_once()
    
    @patch('aiohttp.ClientSession.get')
    def test_download_tweet_media_async_multiple_files(self, mock_get):
        """Test downloading multiple media files from a tweet"""
        # Mock responses for both image and video
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=self.mock_image_content)
        mock_response.headers = {'content-length': '1024'}
        mock_get.return_value.__aenter__.return_value = mock_response
        
        async def run_test():
            results = await self.extractor.download_tweet_media_async(self.mock_tweet)
            
            # Should have 2 results (image and video)
            self.assertEqual(len(results), 2)
            
            # Check both completed successfully
            for result in results:
                self.assertEqual(result['status'], 'completed')
                self.assertIn(result['media_type'], ['image', 'video'])
        
        asyncio.run(run_test())
    
    def test_get_storage_stats(self):
        """Test storage statistics calculation"""
        # Create some test files
        test_file = os.path.join(self.media_storage_path, 'images', 'test.jpg')
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'wb') as f:
            f.write(b'test data')
        
        stats = self.extractor.get_storage_stats()
        
        self.assertIn('total_files', stats)
        self.assertIn('total_size_bytes', stats)
        self.assertIn('total_size_mb', stats)
        self.assertIn('by_type', stats)
        self.assertGreater(stats['total_files'], 0)
        self.assertGreater(stats['total_size_bytes'], 0)
    
    def test_cleanup_old_files(self):
        """Test cleanup of old media files"""
        # Create old test file
        old_dir = os.path.join(self.media_storage_path, 'images', '2020', '01', '01')
        os.makedirs(old_dir, exist_ok=True)
        old_file = os.path.join(old_dir, 'old_file.jpg')
        with open(old_file, 'wb') as f:
            f.write(b'old data')
        
        # Run cleanup (should remove files older than 90 days)
        removed_count = self.extractor.cleanup_old_files(days_to_keep=1)
        
        self.assertGreater(removed_count, 0)
        self.assertFalse(os.path.exists(old_file))
    
    def test_verify_download_integrity(self):
        """Test download integrity verification"""
        # Create test file
        test_file = os.path.join(self.temp_dir, 'test.jpg')
        with open(test_file, 'wb') as f:
            f.write(self.mock_image_content)
        
        # Test valid file
        self.assertTrue(self.extractor._verify_download_integrity(
            test_file, len(self.mock_image_content)
        ))
        
        # Test file size mismatch
        self.assertFalse(self.extractor._verify_download_integrity(
            test_file, 999999
        ))
        
        # Test non-existent file
        self.assertFalse(self.extractor._verify_download_integrity(
            '/nonexistent/file.jpg', 100
        ))
    
    def test_is_valid_media_type(self):
        """Test media type validation"""
        # Valid types
        self.assertTrue(self.extractor._is_valid_media_type('image'))
        self.assertTrue(self.extractor._is_valid_media_type('video'))
        self.assertTrue(self.extractor._is_valid_media_type('audio'))
        self.assertTrue(self.extractor._is_valid_media_type('gif'))
        
        # Invalid types
        self.assertFalse(self.extractor._is_valid_media_type('unknown'))
        self.assertFalse(self.extractor._is_valid_media_type(''))
        self.assertFalse(self.extractor._is_valid_media_type(None))


if __name__ == '__main__':
    unittest.main() 