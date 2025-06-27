#!/usr/bin/env python3

import sqlite3
import re
import os
import asyncio
from core.database import Database
from core.media_extractor import MediaExtractor
import sys
sys.path.append('.')
from core.database_config import DatabaseConfig

def get_tweets_with_video_urls(db_path):
    """Get all tweets that contain video URLs"""
    print(f"📊 Analyzing tweets in database...")
    
    # Connect to database using configuration
    if DatabaseConfig.is_postgresql():
        import psycopg2
        params = DatabaseConfig.get_raw_connection_params()
        conn = psycopg2.connect(
            host=params['host'],
            port=params['port'],
            database=params['database'],
            user=params['user'],
            password=params['password']
        )
        conn.autocommit = False
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, content, created_at 
            FROM tweets 
            WHERE content ~* 'https?://[^\\s]*\\.(mp4|avi|mov|wmv|flv|webm|mkv)'
            ORDER BY created_at DESC
        """)
    else:
        import sqlite3
        params = DatabaseConfig.get_raw_connection_params()
        conn = sqlite3.connect(params['database'])
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, content, created_at 
            FROM tweets 
            WHERE content REGEXP 'https?://[^\\s]*\\.(mp4|avi|mov|wmv|flv|webm|mkv)'
            ORDER BY created_at DESC
        """)
    
    tweets = cursor.fetchall()
    
    print(f"Found {len(tweets)} tweets with video URLs")
    
    cursor.close()
    conn.close()
    return tweets

def extract_video_urls_from_content(content):
    """Extract video URLs from tweet content"""
    # Regex to match common video file extensions
    video_url_pattern = r'https?://[^\s]*\.(mp4|avi|mov|wmv|flv|webm|mkv)(?:\?[^\s]*)?'
    urls = re.findall(video_url_pattern, content, re.IGNORECASE)
    return [url[0] for url in re.finditer(video_url_pattern, content, re.IGNORECASE)]

def store_video_media(tweet_id, video_urls, db_path):
    """Store video URLs as media entries"""
    # Connect to database using configuration
    if DatabaseConfig.is_postgresql():
        import psycopg2
        params = DatabaseConfig.get_raw_connection_params()
        conn = psycopg2.connect(
            host=params['host'],
            port=params['port'],
            database=params['database'],
            user=params['user'],
            password=params['password']
        )
        conn.autocommit = False
        cursor = conn.cursor()
    else:
        import sqlite3
        params = DatabaseConfig.get_raw_connection_params()
        conn = sqlite3.connect(params['database'])
        cursor = conn.cursor()
    
    stored_count = 0
    
    for url in video_urls:
        try:
            # Check if this media entry already exists
            if DatabaseConfig.is_postgresql():
                cursor.execute("""
                    SELECT id FROM media 
                    WHERE tweet_id = %s AND original_url = %s
                """, (tweet_id, url))
            else:
                cursor.execute("""
                    SELECT id FROM media 
                    WHERE tweet_id = ? AND original_url = ?
                """, (tweet_id, url))
            
            if cursor.fetchone():
                print(f"   ⚠️  Media entry already exists for URL: {url[:50]}...")
                continue
            
            # Insert new media entry
            if DatabaseConfig.is_postgresql():
                cursor.execute("""
                    INSERT INTO media (tweet_id, media_type, original_url, download_status)
                    VALUES (%s, 'video', %s, 'pending')
                """, (tweet_id, url))
            else:
                cursor.execute("""
                    INSERT INTO media (tweet_id, media_type, original_url, download_status)
                    VALUES (?, 'video', ?, 'pending')
                """, (tweet_id, url))
            
            stored_count += 1
            print(f"   ✅ Stored video URL: {url[:50]}...")
            
        except Exception as e:
            print(f"   ❌ Error storing URL {url[:50]}...: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    return stored_count

def main():
    """Main function to fix video URLs"""
    print("🎬 Video URL Fix Tool")
    print("=" * 50)
    
    # Import database configuration
    from core.database_config import DatabaseConfig
    
    # Get database connection details
    if DatabaseConfig.is_postgresql():
        print("📊 Using PostgreSQL database")
    else:
        print("📊 Using SQLite database")
        params = DatabaseConfig.get_raw_connection_params()
        db_path = params['database']
        if not os.path.exists(db_path):
            print(f"❌ Database file not found: {db_path}")
            return
    
    # Step 1: Analyze existing tweets for video URLs
    tweets = get_tweets_with_video_urls(None)  # db_path no longer needed
    
    if not tweets:
        print("ℹ️  No tweets with video URLs found.")
        return
    
    # Step 2: Process each tweet
    total_stored = 0
    
    for tweet in tweets:
        tweet_id = tweet[0] if not hasattr(tweet, '_asdict') else tweet.id
        username = tweet[1] if not hasattr(tweet, '_asdict') else tweet.username
        content = tweet[2] if not hasattr(tweet, '_asdict') else tweet.content
        
        print(f"\n🐦 Processing tweet by @{username}")
        print(f"   ID: {tweet_id}")
        print(f"   Content: {content[:100]}...")
        
        # Extract video URLs
        video_urls = extract_video_urls_from_content(content)
        
        if video_urls:
            print(f"   🎬 Found {len(video_urls)} video URL(s)")
            stored = store_video_media(tweet_id, video_urls, None)  # db_path no longer needed
            total_stored += stored
        else:
            print("   ⚠️  No video URLs found in content")
    
    print(f"\n✅ Processing completed!")
    print(f"📊 Total video URLs stored: {total_stored}")
    print(f"🚀 Video URLs are now available for download by the background worker.")

if __name__ == "__main__":
    main() 