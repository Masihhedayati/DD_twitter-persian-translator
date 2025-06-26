#!/usr/bin/env python3
"""
Test script for free video URL resolution system
Tests the VideoUrlResolver and MediaExtractor without requiring Twitter API credentials
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Add the project root to Python path
sys.path.append('.')

from core.video_url_resolver import VideoUrlResolver
from core.media_extractor import MediaExtractor
from core.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_video_url_resolver():
    """Test the VideoUrlResolver class independently"""
    
    print("🧪 Testing VideoUrlResolver...")
    print("=" * 60)
    
    # Test tweet IDs with known videos
    test_tweet_ids = [
        "1894435805071835267",  # A tweet with video from our database
        "1234567890123456789",  # A hypothetical tweet ID
    ]
    
    async with VideoUrlResolver() as resolver:
        for tweet_id in test_tweet_ids:
            print(f"\n🔍 Testing tweet ID: {tweet_id}")
            
            try:
                # Test video URL resolution
                best_url, variants = await resolver.resolve_video_url(tweet_id)
                
                if best_url:
                    print(f"✅ Success! Resolved video URL:")
                    print(f"   Best URL: {best_url}")
                    print(f"   Available variants: {len(variants)}")
                    
                    for i, variant in enumerate(variants[:3]):  # Show first 3 variants
                        print(f"     {i+1}. {variant.quality} ({variant.bitrate} bps): {variant.url[:80]}...")
                else:
                    print(f"❌ Could not resolve video URL for tweet {tweet_id}")
                    
            except Exception as e:
                print(f"❌ Error resolving tweet {tweet_id}: {e}")
    
    # Test thumbnail detection
    print(f"\n🔍 Testing thumbnail URL detection...")
    
    test_urls = [
        "https://pbs.twimg.com/amplify_video_thumb/1234567890123456789/img/abc123.jpg",  # Thumbnail
        "https://video.twimg.com/amplify_video/1234567890123456789/vid/720x720/abc123.mp4",  # Real video
        "https://pbs.twimg.com/media/abc123.jpg",  # Image
    ]
    
    async with VideoUrlResolver() as resolver:
        for url in test_urls:
            is_thumbnail = resolver.is_thumbnail_url(url)
            print(f"   {url[:60]}... -> {'Thumbnail' if is_thumbnail else 'Not thumbnail'}")

async def test_media_extractor_integration():
    """Test MediaExtractor with video URL resolution"""
    
    print(f"\n🎬 Testing MediaExtractor Integration...")
    print("=" * 60)
    
    # Create media extractor
    media_dir = "./media"
    os.makedirs(media_dir, exist_ok=True)
    
    extractor = MediaExtractor(media_dir)
    
    # Test with a sample tweet containing video
    test_tweet = {
        'id': '1894435805071835267',
        'created_at': datetime.now().isoformat(),
        'media': [
            {
                'type': 'video',
                'url': 'https://pbs.twimg.com/amplify_video_thumb/1894435805071835267/img/abc123.jpg'  # Thumbnail URL
            }
        ]
    }
    
    print(f"📥 Testing download for tweet: {test_tweet['id']}")
    print(f"   Original URL: {test_tweet['media'][0]['url']}")
    
    try:
        # Test the download process
        results = await extractor.download_tweet_media_async(test_tweet)
        
        print(f"\n📊 Download Results:")
        for i, result in enumerate(results):
            print(f"   Media {i+1}:")
            print(f"     Status: {result.get('status', 'unknown')}")
            print(f"     Local Path: {result.get('local_path', 'none')}")
            print(f"     Error: {result.get('error_message', 'none')}")
            
    except Exception as e:
        print(f"❌ Error in media extraction: {e}")

def test_database_video_entries():
    """Check our database for video entries that need resolution"""
    
    print(f"\n💾 Testing Database Video Entries...")
    print("=" * 60)
    
    try:
        db = Database("./dev_tweets.db")
        
        # Get pending video items
        pending_media = db.get_tweet_media(completed_only=False)
        
        video_items = [
            item for item in pending_media 
            if item.get('media_type') in ['video', 'animated_gif'] 
            and item.get('download_status') == 'pending'
        ]
        
        print(f"📊 Found {len(video_items)} pending video items in database")
        
        # Show first few examples
        for i, item in enumerate(video_items[:3]):
            print(f"\n   Video {i+1}:")
            print(f"     Tweet ID: {item.get('tweet_id')}")
            print(f"     Type: {item.get('media_type')}")
            print(f"     URL: {item.get('original_url', '')[:80]}...")
            print(f"     Status: {item.get('download_status')}")
            
            # Test if it's a thumbnail
            url = item.get('original_url', '')
            if url:
                import re
                is_thumbnail = any(
                    re.search(pattern, url) for pattern in [
                        r'pbs\.twimg\.com.*thumb.*\.jpg',
                        r'pbs\.twimg\.com/amplify_video_thumb.*\.jpg',
                        r'pbs\.twimg\.com.*\.jpg.*video'
                    ]
                )
                print(f"     Is Thumbnail: {'Yes' if is_thumbnail else 'No'}")
        
    except Exception as e:
        print(f"❌ Error accessing database: {e}")

async def main():
    """Run all tests"""
    
    print("🚀 FREE VIDEO URL RESOLUTION TEST SUITE")
    print("=" * 60)
    print("Testing our system that resolves video URLs without Twitter API")
    print()
    
    # Test 1: VideoUrlResolver
    await test_video_url_resolver()
    
    # Test 2: MediaExtractor Integration
    await test_media_extractor_integration()
    
    # Test 3: Database Video Entries
    test_database_video_entries()
    
    print(f"\n✅ Test suite completed!")
    print("=" * 60)
    print("If the tests passed, you can now:")
    print("1. Run cleanup_video_thumbnails.py to reset pending videos")
    print("2. Restart your application")
    print("3. Monitor background worker logs for video resolution")

if __name__ == "__main__":
    asyncio.run(main()) 