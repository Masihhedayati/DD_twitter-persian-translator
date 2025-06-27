#!/usr/bin/env python3
"""
Cleanup script for video thumbnails
Resets video/animated_gif entries so they can be re-downloaded with proper URLs
"""

import sys
import os
from datetime import datetime

sys.path.append('.')

def cleanup_video_thumbnails():
    """Clean up video thumbnail files and reset download status"""
    
    print("🧹 Cleaning up video thumbnails and resetting download status")
    print("=" * 60)
    
    # Import database configuration
    from core.database_config import DatabaseConfig
    
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
    
    try:
        # Find all video/animated_gif entries with JPG files
        cursor.execute('''
            SELECT id, tweet_id, local_path, original_url, media_type
            FROM media 
            WHERE media_type IN ('video', 'animated_gif')
            AND (local_path LIKE '%.jpg' OR original_url LIKE '%.jpg')
        ''')
        
        thumbnail_items = cursor.fetchall()
        
        print(f"📊 Found {len(thumbnail_items)} video/gif items with thumbnail files")
        
        cleaned_count = 0
        
        for item in thumbnail_items:
            if DatabaseConfig.is_postgresql():
                media_id, tweet_id, local_path, original_url, media_type = item
            else:
                media_id, tweet_id, local_path, original_url, media_type = item
            
            print(f"🔄 Processing {media_type} for tweet {tweet_id}")
            print(f"   URL: {original_url[:60]}...")
            
            # Remove local file if it exists
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    print(f"   ✅ Removed thumbnail file: {local_path}")
                except Exception as e:
                    print(f"   ⚠️  Could not remove file {local_path}: {e}")
            
            # Reset download status to pending
            if DatabaseConfig.is_postgresql():
                cursor.execute('''
                    UPDATE media 
                    SET download_status = 'pending',
                        local_path = NULL,
                        error_message = NULL
                    WHERE id = %s
                ''', (media_id,))
            else:
                cursor.execute('''
                    UPDATE media 
                    SET download_status = 'pending',
                        local_path = NULL,
                        error_message = NULL
                    WHERE id = ?
                ''', (media_id,))
            
            cleaned_count += 1
        
        # Commit changes
        conn.commit()
        
        print(f"\n✅ Cleanup completed successfully!")
        print(f"📊 Processed {cleaned_count} items")
        print(f"🔄 All video/gif items set to 'pending' status for re-download")
        
        # Show current status
        cursor.execute('''
            SELECT 
                media_type,
                download_status,
                COUNT(*) as count
            FROM media 
            WHERE media_type IN ('video', 'animated_gif')
            GROUP BY media_type, download_status
            ORDER BY media_type, download_status
        ''')
        
        print(f"\n📋 Current video/gif media status:")
        for row in cursor.fetchall():
            if DatabaseConfig.is_postgresql():
                media_type, status, count = row
            else:
                media_type, status, count = row
            print(f"  {media_type}: {status} = {count}")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        conn.rollback()
        return False
    
    finally:
        cursor.close()
        conn.close()
    
    print(f"\n🚀 Ready for background worker to retry downloads with new URL resolution!")
    return True

if __name__ == "__main__":
    success = cleanup_video_thumbnails()
    sys.exit(0 if success else 1) 