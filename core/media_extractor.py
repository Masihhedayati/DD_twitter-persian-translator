import os
import asyncio
import aiohttp
import aiofiles
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
import mimetypes
from PIL import Image
import requests
import json


class MediaExtractor:
    """
    Async media downloader for Twitter media files
    Handles images, videos, audio, and GIFs with retry logic and organized storage
    """
    
    def __init__(self, media_storage_path: str):
        """
        Initialize media extractor
        
        Args:
            media_storage_path: Base path for media storage
        """
        self.media_storage_path = media_storage_path
        self.logger = logging.getLogger(__name__)
        
        # Download configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.timeout = 30  # seconds
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.concurrent_downloads = 5  # max parallel downloads
        
        # Valid media types
        self.valid_media_types = {'image', 'video', 'audio', 'gif'}
        
        # Create storage directories
        self._create_storage_directories()
        
    def _create_storage_directories(self):
        """Create necessary storage directory structure"""
        base_dirs = ['images', 'videos', 'audio', 'thumbnails']
        
        for dir_name in base_dirs:
            dir_path = os.path.join(self.media_storage_path, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            
        self.logger.info(f"Created media storage directories at {self.media_storage_path}")
    
    def download_tweet_media(self, tweet: Dict) -> List[Dict]:
        """
        Synchronous wrapper for downloading tweet media
        
        Args:
            tweet: Tweet dictionary with media information
            
        Returns:
            List of download results
        """
        return asyncio.run(self.download_tweet_media_async(tweet))
    
    async def download_tweet_media_async(self, tweet: Dict) -> List[Dict]:
        """
        Download all media from a tweet asynchronously
        
        Args:
            tweet: Tweet dictionary with media information
            
        Returns:
            List of download results with status, paths, and metadata
        """
        if not tweet.get('media'):
            self.logger.info(f"No media found in tweet {tweet.get('id', 'unknown')}")
            return []
        
        tweet_id = tweet.get('id', str(time.time()))
        created_at = tweet.get('created_at', datetime.now().isoformat())
        date_str = self._extract_date_from_timestamp(created_at)
        
        self.logger.info(f"Downloading {len(tweet['media'])} media files for tweet {tweet_id}")
        
        # Create semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.concurrent_downloads)
        
        # Create download tasks
        tasks = []
        for index, media_info in enumerate(tweet['media']):
            task = self._download_single_media_with_semaphore(
                semaphore, tweet_id, media_info, index, date_str
            )
            tasks.append(task)
        
        # Wait for all downloads to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Download task {i} failed: {result}")
                processed_results.append({
                    'status': 'failed',
                    'error_message': str(result),
                    'media_index': i
                })
            else:
                processed_results.append(result)
        
        successful_downloads = sum(1 for r in processed_results if r.get('status') == 'completed')
        self.logger.info(f"Downloaded {successful_downloads}/{len(processed_results)} media files for tweet {tweet_id}")
        
        return processed_results
    
    async def _download_single_media_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                                   tweet_id: str, media_info: Dict, 
                                                   index: int, date_str: str) -> Dict:
        """Download single media file with semaphore limiting"""
        async with semaphore:
            return await self._download_single_media(tweet_id, media_info, index, date_str)
    
    async def _download_single_media(self, tweet_id: str, media_info: Dict, 
                                   index: int, date_str: str) -> Dict:
        """
        Download a single media file with retry logic
        
        Args:
            tweet_id: Tweet ID
            media_info: Media information dictionary
            index: Media index in tweet
            date_str: Date string for file organization
            
        Returns:
            Download result dictionary
        """
        media_type = media_info.get('type', 'unknown')
        media_url = media_info.get('url', '')
        
        if not self._is_valid_media_type(media_type):
            return {
                'status': 'failed',
                'error_message': f'Invalid media type: {media_type}',
                'media_type': media_type,
                'original_url': media_url
            }
        
        if not media_url:
            return {
                'status': 'failed',
                'error_message': 'No media URL provided',
                'media_type': media_type
            }
        
        # Generate filename and paths
        filename = self._generate_filename(tweet_id, media_type, media_url, index)
        media_dir = self._get_media_directory_path(media_type, date_str)
        os.makedirs(media_dir, exist_ok=True)
        local_path = os.path.join(media_dir, filename)
        
        # Attempt download with retries
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Download attempt {attempt + 1}/{self.max_retries} for {media_url}")
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(media_url) as response:
                        if response.status == 200:
                            # Check file size
                            content_length = response.headers.get('content-length')
                            if content_length and int(content_length) > self.max_file_size:
                                return {
                                    'status': 'failed',
                                    'error_message': f'File too large: {content_length} bytes',
                                    'media_type': media_type,
                                    'original_url': media_url
                                }
                            
                            # Download file
                            file_content = await response.read()
                            
                            # Save to disk
                            async with aiofiles.open(local_path, 'wb') as f:
                                await f.write(file_content)
                            
                            # Verify download integrity
                            if not self._verify_download_integrity(local_path, len(file_content)):
                                raise Exception("Download integrity check failed")
                            
                            # Success result
                            return {
                                'status': 'completed',
                                'media_type': media_type,
                                'original_url': media_url,
                                'local_path': local_path,
                                'file_size': len(file_content),
                                'width': media_info.get('width'),
                                'height': media_info.get('height'),
                                'duration': media_info.get('duration'),
                                'content_type': response.headers.get('content-type', ''),
                                'downloaded_at': datetime.now().isoformat()
                            }
                        else:
                            # HTTP error
                            if response.status in [404, 403, 410]:
                                # Permanent errors - don't retry
                                return {
                                    'status': 'failed',
                                    'error_message': f'HTTP {response.status}: Media not available',
                                    'media_type': media_type,
                                    'original_url': media_url
                                }
                            else:
                                # Temporary error - retry
                                raise aiohttp.ClientResponseError(
                                    request_info=response.request_info,
                                    history=response.history,
                                    status=response.status
                                )
            
            except Exception as e:
                self.logger.warning(f"Download attempt {attempt + 1} failed for {media_url}: {e}")
                
                if attempt < self.max_retries - 1:
                    # Wait before retry with exponential backoff
                    wait_time = self.retry_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                else:
                    # Final attempt failed
                    return {
                        'status': 'failed',
                        'error_message': str(e),
                        'media_type': media_type,
                        'original_url': media_url,
                        'attempts': self.max_retries
                    }
        
        # Should never reach here
        return {
            'status': 'failed',
            'error_message': 'Unknown error occurred',
            'media_type': media_type,
            'original_url': media_url
        }
    
    def _generate_filename(self, tweet_id: str, media_type: str, url: str, index: int) -> str:
        """
        Generate filename for media file
        
        Args:
            tweet_id: Tweet ID
            media_type: Type of media (image, video, audio)
            url: Original media URL
            index: Media index in tweet
            
        Returns:
            Generated filename
        """
        # Determine file extension
        extension = self._extract_file_extension(url)
        
        # Create type prefix
        type_prefix = {
            'image': 'img',
            'video': 'vid',
            'audio': 'aud',
            'gif': 'gif'
        }.get(media_type, 'med')
        
        # Generate filename
        filename = f"tweet_{tweet_id}_{type_prefix}_{index}{extension}"
        
        return filename
    
    def _get_media_directory_path(self, media_type: str, date_str: str) -> str:
        """
        Get directory path for media storage organized by type and date
        
        Args:
            media_type: Type of media
            date_str: Date string (YYYY-MM-DD)
            
        Returns:
            Directory path
        """
        # Map media types to directory names
        type_dirs = {
            'image': 'images',
            'video': 'videos',
            'audio': 'audio',
            'gif': 'images'  # Store GIFs with images
        }
        
        base_dir = type_dirs.get(media_type, 'unknown')
        
        # Parse date and create year/month/day structure
        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            year = str(date_obj.year)
            month = f"{date_obj.month:02d}"
            day = f"{date_obj.day:02d}"
        except:
            # Fallback to current date
            now = datetime.now()
            year = str(now.year)
            month = f"{now.month:02d}"
            day = f"{now.day:02d}"
        
        return os.path.join(self.media_storage_path, base_dir, year, month, day)
    
    def _extract_file_extension(self, url: str) -> str:
        """
        Extract file extension from URL
        
        Args:
            url: Media URL
            
        Returns:
            File extension with dot (e.g., '.jpg')
        """
        # Parse URL to remove query parameters
        parsed = urlparse(url)
        path = parsed.path
        
        # Get extension from path
        _, ext = os.path.splitext(path)
        
        # Fallback: try to guess from query parameters
        if not ext and parsed.query:
            query_params = parse_qs(parsed.query)
            for param in ['format', 'name']:
                if param in query_params:
                    value = query_params[param][0]
                    if '.' in value:
                        _, ext = os.path.splitext(value)
                        break
        
        return ext.lower()
    
    def _extract_date_from_timestamp(self, timestamp: str) -> str:
        """
        Extract date string from timestamp
        
        Args:
            timestamp: ISO timestamp string
            
        Returns:
            Date string (YYYY-MM-DD)
        """
        try:
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime('%Y-%m-%d')
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    def _verify_download_integrity(self, file_path: str, expected_size: int) -> bool:
        """
        Verify download integrity by checking file size and existence
        
        Args:
            file_path: Path to downloaded file 
            expected_size: Expected file size in bytes
            
        Returns:
            True if file is valid
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            actual_size = os.path.getsize(file_path)
            
            # Allow small differences in file size (sometimes headers differ)
            size_diff = abs(actual_size - expected_size)
            tolerance = max(100, expected_size * 0.01)  # 1% or 100 bytes, whichever is larger
            
            return size_diff <= tolerance
            
        except Exception as e:
            self.logger.error(f"Error verifying file {file_path}: {e}")
            return False
    
    def _is_valid_media_type(self, media_type: str) -> bool:
        """
        Check if media type is valid
        
        Args:
            media_type: Media type string
            
        Returns:
            True if valid media type
        """
        return media_type in self.valid_media_types
    
    def get_storage_stats(self) -> Dict:
        """
        Get storage statistics
        
        Returns:
            Dictionary with storage statistics
        """
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0.0,
            'by_type': {}
        }
        
        if not os.path.exists(self.media_storage_path):
            return stats
        
        # Walk through all files
        for root, dirs, files in os.walk(self.media_storage_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    stats['total_files'] += 1
                    stats['total_size_bytes'] += file_size
                    
                    # Categorize by directory (media type)
                    rel_path = os.path.relpath(root, self.media_storage_path)
                    media_type = rel_path.split(os.sep)[0] if os.sep in rel_path else rel_path
                    
                    if media_type not in stats['by_type']:
                        stats['by_type'][media_type] = {'files': 0, 'size_bytes': 0}
                    
                    stats['by_type'][media_type]['files'] += 1
                    stats['by_type'][media_type]['size_bytes'] += file_size
                    
                except Exception as e:
                    self.logger.warning(f"Error processing file {file_path}: {e}")
        
        # Convert to MB
        stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
        
        for media_type in stats['by_type']:
            stats['by_type'][media_type]['size_mb'] = stats['by_type'][media_type]['size_bytes'] / (1024 * 1024)
        
        return stats
    
    def cleanup_old_files(self, days_to_keep: int = 90) -> int:
        """
        Clean up old media files
        
        Args:
            days_to_keep: Number of days to keep files
            
        Returns:
            Number of files removed
        """
        if not os.path.exists(self.media_storage_path):
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        removed_count = 0
        
        self.logger.info(f"Cleaning up files older than {days_to_keep} days (before {cutoff_date.date()})")
        
        # Walk through all files
        for root, dirs, files in os.walk(self.media_storage_path, topdown=False):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_date:
                        os.remove(file_path)
                        removed_count += 1
                        self.logger.debug(f"Removed old file: {file_path}")
                        
                except Exception as e:
                    self.logger.warning(f"Error removing file {file_path}: {e}")
            
            # Remove empty directories
            try:
                if not os.listdir(root):
                    os.rmdir(root)
                    self.logger.debug(f"Removed empty directory: {root}")
            except:
                pass  # Directory not empty or other error
        
        self.logger.info(f"Cleanup completed: removed {removed_count} files")
        return removed_count

    def extract_media_from_tweet(self, tweet_data: Dict) -> List[Dict]:
        """Extract media URLs from tweet data"""
        media_items = []
        
        try:
            # Check if tweet has media
            if 'media' in tweet_data:
                for media_item in tweet_data['media']:
                    media_info = {
                        'type': media_item.get('type', 'unknown'),
                        'url': media_item.get('url'),
                        'width': media_item.get('width'),
                        'height': media_item.get('height'),
                        'duration': media_item.get('duration_ms')
                    }
                    media_items.append(media_info)
            
            # Also check for images in extended_entities
            if 'extended_entities' in tweet_data and 'media' in tweet_data['extended_entities']:
                for media_item in tweet_data['extended_entities']['media']:
                    media_info = {
                        'type': media_item.get('type', 'photo'),
                        'url': media_item.get('media_url_https') or media_item.get('media_url'),
                        'width': media_item.get('sizes', {}).get('large', {}).get('w'),
                        'height': media_item.get('sizes', {}).get('large', {}).get('h')
                    }
                    
                    # For videos, get the best quality URL
                    if media_item.get('type') == 'video' and 'video_info' in media_item:
                        variants = media_item['video_info'].get('variants', [])
                        best_variant = self._get_best_video_variant(variants)
                        if best_variant:
                            media_info['url'] = best_variant['url']
                            media_info['duration'] = media_item['video_info'].get('duration_millis')
                    
                    media_items.append(media_info)
            
            # Check for URLs that might contain media
            urls = self._extract_urls_from_text(tweet_data.get('content', ''))
            for url in urls:
                if self._is_media_url(url):
                    media_items.append({
                        'type': 'photo' if self._is_image_url(url) else 'video',
                        'url': url
                    })
                    
        except Exception as e:
            self.logger.error(f"Error extracting media from tweet: {e}")
        
        return media_items
    
    def _get_best_video_variant(self, variants: List[Dict]) -> Optional[Dict]:
        """Get the best quality video variant"""
        if not variants:
            return None
        
        # Filter for mp4 videos and sort by bitrate
        mp4_variants = [v for v in variants if v.get('content_type') == 'video/mp4']
        if mp4_variants:
            return max(mp4_variants, key=lambda x: x.get('bitrate', 0))
        
        # Fallback to any variant
        return variants[0] if variants else None
    
    def _extract_urls_from_text(self, text: str) -> List[str]:
        """Extract URLs from tweet text"""
        import re
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    def _is_media_url(self, url: str) -> bool:
        """Check if URL points to media content"""
        return self._is_image_url(url) or self._is_video_url(url)
    
    def _is_image_url(self, url: str) -> bool:
        """Check if URL points to an image"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        return any(url.lower().endswith(ext) for ext in image_extensions)
    
    def _is_video_url(self, url: str) -> bool:
        """Check if URL points to a video"""
        video_extensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
        return any(url.lower().endswith(ext) for ext in video_extensions)
    
    def download_media(self, tweet_id: str, media_items: List[Dict]) -> List[Dict]:
        """Download media files and return file information"""
        downloaded_media = []
        
        for i, media_item in enumerate(media_items):
            try:
                media_url = media_item.get('url')
                if not media_url:
                    continue
                
                # Generate filename
                filename = self._generate_filename(tweet_id, i, media_item)
                filepath = os.path.join(self.media_storage_path, filename)
                
                # Download the file
                success, file_info = self._download_file(media_url, filepath)
                
                if success:
                    media_data = {
                        'tweet_id': tweet_id,
                        'media_type': media_item.get('type', 'unknown'),
                        'original_url': media_url,
                        'local_path': filepath,
                        'file_size': file_info.get('size'),
                        'width': media_item.get('width') or file_info.get('width'),
                        'height': media_item.get('height') or file_info.get('height'),
                        'duration': media_item.get('duration'),
                        'download_status': 'completed',
                        'downloaded_at': datetime.now()
                    }
                    downloaded_media.append(media_data)
                    self.logger.info(f"Downloaded media: {filename}")
                else:
                    self.logger.error(f"Failed to download media from {media_url}")
                    
            except Exception as e:
                self.logger.error(f"Error downloading media item: {e}")
        
        return downloaded_media
    
    def _generate_filename(self, tweet_id: str, index: int, media_item: Dict) -> str:
        """Generate filename for media file"""
        media_type = media_item.get('type', 'unknown')
        url = media_item.get('url', '')
        
        # Get file extension from URL or type
        parsed_url = urlparse(url)
        _, ext = os.path.splitext(parsed_url.path)
        
        if not ext:
            if media_type == 'photo':
                ext = '.jpg'
            elif media_type == 'video':
                ext = '.mp4'
            else:
                ext = '.bin'
        
        return f"{tweet_id}_{index}{ext}"
    
    def _download_file(self, url: str, filepath: str) -> tuple:
        """Download file from URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Write file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Get file info
            file_info = self._get_file_info(filepath)
            
            return True, file_info
            
        except Exception as e:
            self.logger.error(f"Error downloading file from {url}: {e}")
            # Clean up partial file
            if os.path.exists(filepath):
                os.remove(filepath)
            return False, {}
    
    def _get_file_info(self, filepath: str) -> Dict:
        """Get information about downloaded file"""
        try:
            file_info = {
                'size': os.path.getsize(filepath)
            }
            
            # Try to get image dimensions
            if self._is_image_file(filepath):
                try:
                    with Image.open(filepath) as img:
                        file_info['width'] = img.width
                        file_info['height'] = img.height
                except Exception:
                    pass
            
            return file_info
            
        except Exception as e:
            self.logger.error(f"Error getting file info for {filepath}: {e}")
            return {}
    
    def _is_image_file(self, filepath: str) -> bool:
        """Check if file is an image"""
        try:
            mime_type, _ = mimetypes.guess_type(filepath)
            return mime_type and mime_type.startswith('image/')
        except Exception:
            return False
    
    def get_media_url_for_display(self, local_path: str) -> str:
        """Get URL for displaying media in web interface"""
        if not local_path:
            return None
        
        # Convert absolute path to relative web path
        if local_path.startswith(self.media_storage_path):
            relative_path = os.path.relpath(local_path, self.media_storage_path)
            return f"/media/{relative_path}"
        
        return local_path
    
    def cleanup_old_media(self, days_old: int = 30):
        """Clean up media files older than specified days"""
        try:
            cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            for filename in os.listdir(self.media_storage_path):
                filepath = os.path.join(self.media_storage_path, filename)
                if os.path.isfile(filepath):
                    file_time = os.path.getmtime(filepath)
                    if file_time < cutoff_time:
                        os.remove(filepath)
                        self.logger.info(f"Cleaned up old media file: {filename}")
                        
        except Exception as e:
            self.logger.error(f"Error cleaning up old media: {e}") 