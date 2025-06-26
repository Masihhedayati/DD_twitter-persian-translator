#!/usr/bin/env python3
"""
Video URL Resolver for Twitter/X
Implements free methods to resolve actual video URLs without official API
"""

import asyncio
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VideoVariant:
    """Represents a video variant with different quality/bitrate"""
    url: str
    bitrate: int
    content_type: str = "video/mp4"
    
    @property
    def quality(self) -> str:
        """Get quality label based on bitrate"""
        if self.bitrate >= 2176000:
            return "1080p"
        elif self.bitrate >= 832000:
            return "720p"
        elif self.bitrate >= 320000:
            return "480p"
        else:
            return "360p"

class VideoUrlResolver:
    """
    Resolves actual video URLs from Twitter/X without using official API
    Uses Twitter's syndication API and browser automation as fallback
    """
    
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def extract_tweet_id(self, url: str) -> Optional[str]:
        """Extract tweet ID from various Twitter URL formats"""
        patterns = [
            r'twitter\.com/\w+/status/(\d+)',
            r'x\.com/\w+/status/(\d+)',
            r'mobile\.twitter\.com/\w+/status/(\d+)',
            r'/status/(\d+)',
            r'(\d{10,})'  # Direct tweet ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, str(url))
            if match:
                return match.group(1)
        return None
    
    def is_thumbnail_url(self, url: str) -> bool:
        """Check if URL is a thumbnail instead of actual video"""
        thumbnail_indicators = [
            '/img/',
            '/amplify_video_thumb/',
            '_thumb',
            '.jpg',
            '.jpeg',
            '.png',
            '/ext_tw_video_thumb/'
        ]
        
        return any(indicator in url.lower() for indicator in thumbnail_indicators)
    
    async def resolve_via_syndication_api(self, tweet_id: str) -> List[VideoVariant]:
        """
        Method 1: Use Twitter's Syndication API (most reliable, free)
        This is the same API used by embedded tweets
        """
        try:
            # Build syndication API URL
            # This is Twitter's internal API used for tweet embeds
            syndication_url = f"https://cdn.syndication.twimg.com/tweet-result"
            
            params = {
                'id': tweet_id,
                'lang': 'en',
                'features': 'tfw_timeline_list:;tfw_follower_count_sunset:true;tfw_tweet_edit_backend:on;tfw_refsrc_session:on;tfw_fosnr_soft_interventions_enabled:on;tfw_show_birdwatch_pivot_enabled:on;tfw_show_business_verified_badge:on;tfw_duplicate_scribes_to_settings:on;tfw_use_profile_image_shape_enabled:on;tfw_show_blue_verified_badge:on;tfw_legacy_timeline_sunset:true;tfw_show_gov_verified_badge:on;tfw_show_business_affiliate_badge:on;tfw_tweet_edit_frontend:on',
                'token': 'a'  # Basic token that usually works
            }
            
            logger.info(f"Trying syndication API for tweet {tweet_id}")
            
            async with self.session.get(syndication_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._extract_video_variants_from_syndication(data)
                else:
                    logger.warning(f"Syndication API returned status {response.status}")
                    
        except Exception as e:
            logger.error(f"Syndication API failed: {e}")
            
        return []
    
    def _extract_video_variants_from_syndication(self, data: dict) -> List[VideoVariant]:
        """Extract video variants from syndication API response"""
        variants = []
        
        try:
            # Navigate through the response structure
            # Syndication API returns nested media objects
            video_info = None
            
            # Try different paths in the response
            if 'mediaDetails' in data:
                for media in data['mediaDetails']:
                    if media.get('type') == 'video':
                        video_info = media
                        break
            
            elif 'video' in data:
                video_info = data['video']
            
            elif 'extended_entities' in data:
                media_list = data['extended_entities'].get('media', [])
                for media in media_list:
                    if media.get('type') == 'video':
                        video_info = media
                        break
            
            if video_info and 'video_info' in video_info:
                video_variants = video_info['video_info'].get('variants', [])
                
                for variant in video_variants:
                    if variant.get('content_type') == 'video/mp4':
                        variants.append(VideoVariant(
                            url=variant['url'],
                            bitrate=variant.get('bitrate', 0),
                            content_type=variant.get('content_type', 'video/mp4')
                        ))
                        
                logger.info(f"Found {len(variants)} video variants via syndication API")
                
        except Exception as e:
            logger.error(f"Error extracting video variants: {e}")
            
        return variants
    
    async def resolve_via_guest_token(self, tweet_id: str) -> List[VideoVariant]:
        """
        Method 2: Use Twitter's GraphQL API with guest token
        More complex but sometimes necessary for newer tweets
        """
        try:
            # Step 1: Get guest token
            guest_token = await self._get_guest_token()
            if not guest_token:
                return []
                
            # Step 2: Get tweet data using GraphQL
            graphql_url = "https://twitter.com/i/api/graphql/VWxGj2thWALXK1t4EcAEcw/TweetResultByRestId"
            
            params = {
                'variables': json.dumps({
                    'tweetId': tweet_id,
                    'withCommunity': False,
                    'includePromotedContent': False,
                    'withVoice': False
                }),
                'features': json.dumps({
                    'creator_subscriptions_tweet_preview_api_enabled': True,
                    'tweetypie_unmention_optimization_enabled': True,
                    'responsive_web_edit_tweet_api_enabled': True,
                    'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                    'view_counts_everywhere_api_enabled': True,
                    'longform_notetweets_consumption_enabled': True,
                    'responsive_web_twitter_article_tweet_consumption_enabled': False,
                    'tweet_awards_web_tipping_enabled': False,
                    'freedom_of_speech_not_reach_fetch_enabled': True,
                    'standardized_nudges_misinfo': True,
                    'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                    'longform_notetweets_rich_text_read_enabled': True,
                    'longform_notetweets_inline_media_enabled': True,
                    'responsive_web_media_download_video_enabled': False,
                    'responsive_web_enhance_cards_enabled': False
                })
            }
            
            headers = {
                'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
                'x-guest-token': guest_token,
                'x-twitter-client-language': 'en',
                'x-twitter-active-user': 'yes',
                'x-csrf-token': guest_token[:32],  # Use part of guest token as CSRF
            }
            
            logger.info(f"Trying GraphQL API for tweet {tweet_id}")
            
            async with self.session.get(graphql_url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._extract_video_variants_from_graphql(data)
                else:
                    logger.warning(f"GraphQL API returned status {response.status}")
                    
        except Exception as e:
            logger.error(f"Guest token method failed: {e}")
            
        return []
    
    async def _get_guest_token(self) -> Optional[str]:
        """Get a guest token from Twitter"""
        try:
            token_url = "https://api.twitter.com/1.1/guest/activate.json"
            headers = {
                'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'
            }
            
            async with self.session.post(token_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('guest_token')
                    
        except Exception as e:
            logger.error(f"Failed to get guest token: {e}")
            
        return None
    
    def _extract_video_variants_from_graphql(self, data: dict) -> List[VideoVariant]:
        """Extract video variants from GraphQL API response"""
        variants = []
        
        try:
            # Navigate GraphQL response structure
            tweet_result = data.get('data', {}).get('tweetResult', {}).get('result', {})
            legacy = tweet_result.get('legacy', {})
            extended_entities = legacy.get('extended_entities', {})
            media_list = extended_entities.get('media', [])
            
            for media in media_list:
                if media.get('type') == 'video':
                    video_info = media.get('video_info', {})
                    video_variants = video_info.get('variants', [])
                    
                    for variant in video_variants:
                        if variant.get('content_type') == 'video/mp4':
                            variants.append(VideoVariant(
                                url=variant['url'],
                                bitrate=variant.get('bitrate', 0),
                                content_type=variant.get('content_type', 'video/mp4')
                            ))
                            
            logger.info(f"Found {len(variants)} video variants via GraphQL API")
            
        except Exception as e:
            logger.error(f"Error extracting video variants from GraphQL: {e}")
            
        return variants
    
    async def resolve_video_url(self, url_or_id: str) -> Tuple[Optional[str], List[VideoVariant]]:
        """
        Main method to resolve video URL
        Returns (best_quality_url, all_variants)
        """
        # Extract tweet ID
        tweet_id = self.extract_tweet_id(url_or_id)
        if not tweet_id:
            logger.error(f"Could not extract tweet ID from: {url_or_id}")
            return None, []
        
        # Check if input is already a video URL that's not a thumbnail
        if url_or_id.startswith('http') and not self.is_thumbnail_url(url_or_id):
            # Input is already a video URL, return as-is
            return url_or_id, [VideoVariant(url=url_or_id, bitrate=0)]
        
        # Try method 1: Syndication API (most reliable)
        variants = await self.resolve_via_syndication_api(tweet_id)
        
        # Try method 2: GraphQL with guest token (fallback)
        if not variants:
            variants = await self.resolve_via_guest_token(tweet_id)
        
        if not variants:
            logger.warning(f"No video variants found for tweet {tweet_id}")
            return None, []
        
        # Sort by bitrate to get best quality
        variants.sort(key=lambda v: v.bitrate, reverse=True)
        best_url = variants[0].url if variants else None
        
        logger.info(f"Resolved {len(variants)} video variants for tweet {tweet_id}")
        logger.info(f"Best quality: {variants[0].quality} ({variants[0].bitrate} bitrate)" if variants else "No variants")
        
        return best_url, variants


# Standalone async function for easy use
async def resolve_twitter_video_url(url_or_id: str) -> Optional[str]:
    """
    Simple function to get the best quality video URL
    Usage: video_url = await resolve_twitter_video_url('https://twitter.com/user/status/123')
    """
    async with VideoUrlResolver() as resolver:
        best_url, variants = await resolver.resolve_video_url(url_or_id)
        return best_url


# Test function
async def test_resolver():
    """Test the video URL resolver"""
    test_urls = [
        "https://twitter.com/TwitterDev/status/1293593516040269825",  # Sample video tweet
        "1293593516040269825",  # Direct ID
    ]
    
    async with VideoUrlResolver() as resolver:
        for url in test_urls:
            print(f"\n🧪 Testing: {url}")
            best_url, variants = await resolver.resolve_video_url(url)
            
            if best_url:
                print(f"✅ Best video URL: {best_url}")
                print(f"📊 Found {len(variants)} variants:")
                for variant in variants:
                    print(f"   {variant.quality}: {variant.url[:80]}...")
            else:
                print("❌ No video URL found")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_resolver()) 