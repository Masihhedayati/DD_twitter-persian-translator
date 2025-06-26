#!/usr/bin/env python3

import sqlite3
import re
import os
import asyncio
from core.database import Database
from core.media_extractor import MediaExtractor

def fix_video_urls():
    """Fix video thumbnail URLs to proper video URLs"""
    
    db_path = './dev_tweets.db'
    media_storage_path = './media'
    
    # Initialize database
    database = Database(db_path)
    
    # Get all video entries with thumbnail URLs
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, tweet_id, media_type, original_url, local_path 
            FROM media 
            WHERE media_type IN ('video', 'animated_gif') 
            AND (original_url LIKE '%amplify_video_thumb%' OR original_url LIKE '%.jpg')
        """)
        
        video_entries = cursor.fetchall()
        
    print(f"🔍 Found {len(video_entries)} video entries with thumbnail URLs")
    
    for entry in video_entries:
        media_id = entry['id']
        tweet_id = entry['tweet_id']
        original_url = entry['original_url']
        local_path = entry['local_path']
        
        print(f"\n📹 Processing video {tweet_id}:")
        print(f"   Current URL: {original_url}")
        print(f"   Local path: {local_path}")
        
        # Check if local file exists and what type it is
        if local_path and os.path.exists(local_path):
            # Check if it's actually a thumbnail (JPEG)
            import subprocess
            result = subprocess.run(['file', local_path], capture_output=True, text=True)
            print(f"   File type: {result.stdout.strip()}")
            
            if 'JPEG' in result.stdout:
                print(f"   ❌ File is a thumbnail JPEG, needs re-download")
                
                # Mark for re-download by clearing local path
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE media 
                        SET local_path = NULL, download_status = 'pending' 
                        WHERE id = ?
                    """, (media_id,))
                    conn.commit()
                
                # Remove the thumbnail file
                try:
                    os.remove(local_path)
                    print(f"   🗑️  Removed thumbnail file")
                except Exception as e:
                    print(f"   ⚠️  Could not remove file: {e}")
                
                # Try to construct a proper video URL
                # For amplify_video_thumb URLs, we need to construct the video URL
                if 'amplify_video_thumb' in original_url:
                    # Extract the video ID from the thumbnail URL
                    # Example: https://pbs.twimg.com/amplify_video_thumb/1936941726616166400/img/bPOozUjgxy9JbjUx.jpg
                    # Should become: https://video.twimg.com/amplify_video/1936941726616166400/pl/640x480_1_400.mp4
                    
                    video_id_match = re.search(r'/amplify_video_thumb/(\d+)/', original_url)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                        # Construct potential video URLs (different resolutions/bitrates)
                        potential_urls = [
                            f"https://video.twimg.com/amplify_video/{video_id}/pl/640x360_1_400.mp4",
                            f"https://video.twimg.com/amplify_video/{video_id}/pl/480x270_1_300.mp4",
                            f"https://video.twimg.com/amplify_video/{video_id}/pl/320x180_1_200.mp4",
                        ]
                        
                        print(f"   🔄 Trying to construct video URLs for video ID: {video_id}")
                        
                        # Test which URL works (simple HTTP head request)
                        import requests
                        working_url = None
                        for url in potential_urls:
                            try:
                                response = requests.head(url, timeout=5)
                                if response.status_code == 200:
                                    working_url = url
                                    print(f"   ✅ Found working video URL: {url}")
                                    break
                            except:
                                continue
                        
                        if working_url:
                            # Update the database with the new URL
                            with sqlite3.connect(db_path) as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE media 
                                    SET original_url = ? 
                                    WHERE id = ?
                                """, (working_url, media_id))
                                conn.commit()
                            print(f"   ✅ Updated database with video URL")
                        else:
                            print(f"   ❌ Could not find working video URL")
            else:
                print(f"   ✅ File appears to be a valid video")
        else:
            print(f"   ❌ Local file does not exist")
    
    print(f"\n🎯 Video URL fixing complete!")
    print(f"💡 Now the background worker should be able to download actual videos")

if __name__ == "__main__":
    fix_video_urls() 