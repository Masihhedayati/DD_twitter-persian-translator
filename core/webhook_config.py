"""
Webhook Configuration for Twitter Monitor
Automatically handles local development vs production webhook URLs
"""
import os
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class WebhookConfig:
    """Webhook configuration management for development and production"""
    
    @staticmethod
    def get_public_webhook_url() -> Optional[str]:
        """
        Get the public webhook URL for RSS.app configuration
        Automatically detects environment and returns appropriate URL
        """
        # 1. Check if explicitly set (production)
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            return webhook_url.rstrip('/')
        
        # 2. Check if running on Koyeb (production)
        koyeb_url = WebhookConfig._detect_koyeb_url()
        if koyeb_url:
            return koyeb_url
        
        # 3. Check for ngrok (development)
        ngrok_url = WebhookConfig._detect_ngrok_url()
        if ngrok_url:
            return ngrok_url
        
        # 4. Fallback to localhost (development without ngrok)
        port = os.environ.get('PORT', '5001')
        return f"http://localhost:{port}"
    
    @staticmethod
    def _detect_koyeb_url() -> Optional[str]:
        """Detect if running on Koyeb and get public URL"""
        try:
            # Koyeb sets these environment variables
            koyeb_app_name = os.environ.get('KOYEB_APP_NAME')
            koyeb_service_name = os.environ.get('KOYEB_SERVICE_NAME')
            koyeb_deployment_id = os.environ.get('KOYEB_DEPLOYMENT_ID')
            
            # Check for common Koyeb indicators
            if any([koyeb_app_name, koyeb_service_name, koyeb_deployment_id]):
                # Try to get URL from environment or construct it
                public_url = os.environ.get('KOYEB_PUBLIC_URL')
                if public_url:
                    return public_url.rstrip('/')
                
                # Try to construct URL pattern (Koyeb format)
                if koyeb_app_name:
                    return f"https://{koyeb_app_name}.koyeb.app"
            
            # Check if we're running on a .koyeb.app domain
            hostname = os.environ.get('HOSTNAME', '')
            if '.koyeb.app' in hostname:
                return f"https://{hostname}"
                
        except Exception as e:
            logger.debug(f"Could not detect Koyeb environment: {e}")
        
        return None
    
    @staticmethod
    def _detect_ngrok_url() -> Optional[str]:
        """Detect ngrok tunnel URL for local development"""
        try:
            # Check if ngrok URL file exists (from tunnel scripts)
            ngrok_url_file = '.ngrok_url'
            if os.path.exists(ngrok_url_file):
                with open(ngrok_url_file, 'r') as f:
                    url = f.read().strip()
                    if url and url.startswith('http'):
                        return url.rstrip('/')
            
            # Try to get from ngrok API (localhost:4040)
            try:
                response = requests.get('http://localhost:4040/api/tunnels', timeout=2)
                if response.status_code == 200:
                    tunnels = response.json().get('tunnels', [])
                    for tunnel in tunnels:
                        if tunnel.get('proto') == 'https':
                            return tunnel.get('public_url', '').rstrip('/')
            except:
                pass  # ngrok not running or not accessible
                
        except Exception as e:
            logger.debug(f"Could not detect ngrok URL: {e}")
        
        return None
    
    @staticmethod
    def get_webhook_endpoints() -> Dict[str, str]:
        """Get all webhook endpoint URLs"""
        base_url = WebhookConfig.get_public_webhook_url()
        if not base_url:
            return {}
        
        return {
            'rss_webhook': f"{base_url}/webhook/rss",
            'rss_webhook_test': f"{base_url}/webhook/rss/test",
            'twitter_webhook': f"{base_url}/webhook/twitter",
            'health_check': f"{base_url}/health",
            'dashboard': f"{base_url}/",
        }
    
    @staticmethod
    def validate_webhook_access() -> Dict[str, Any]:
        """Validate that webhook endpoints are accessible"""
        endpoints = WebhookConfig.get_webhook_endpoints()
        results = {}
        
        for name, url in endpoints.items():
            try:
                if name == 'health_check':
                    # Test health endpoint
                    response = requests.get(url, timeout=10)
                    results[name] = {
                        'url': url,
                        'accessible': response.status_code == 200,
                        'status_code': response.status_code
                    }
                else:
                    # For webhook endpoints, just check if they respond (even with 405 Method Not Allowed)
                    response = requests.get(url, timeout=10)
                    # Webhook endpoints might return 405 for GET requests, which is fine
                    accessible = response.status_code in [200, 405, 404]
                    results[name] = {
                        'url': url,
                        'accessible': accessible,
                        'status_code': response.status_code
                    }
            except Exception as e:
                results[name] = {
                    'url': url,
                    'accessible': False,
                    'error': str(e)
                }
        
        return results
    
    @staticmethod
    def get_rss_app_instructions() -> Dict[str, str]:
        """Get instructions for configuring RSS.app with current webhook URL"""
        base_url = WebhookConfig.get_public_webhook_url()
        
        if not base_url:
            return {
                'error': 'Could not determine public webhook URL',
                'suggestion': 'Set WEBHOOK_URL environment variable or ensure ngrok is running'
            }
        
        webhook_url = f"{base_url}/webhook/rss"
        
        environment = 'production' if WebhookConfig._detect_koyeb_url() else 'development'
        
        instructions = {
            'environment': environment,
            'webhook_url': webhook_url,
            'rss_app_config': f"""
RSS.app Configuration:
1. Go to RSS.app dashboard
2. Create/edit your Twitter feed
3. Set webhook URL to: {webhook_url}
4. Set HTTP method to: POST
5. Add your 9 monitored users to the feed
6. Save and test the configuration
            """.strip(),
            'test_command': f"curl -X POST {webhook_url}/test",
            'monitoring_dashboard': f"{base_url}/",
        }
        
        if environment == 'development':
            instructions['note'] = "⚠️  Development mode: ngrok URL may change on restart"
        else:
            instructions['note'] = "✅ Production mode: URL is permanent"
        
        return instructions
    
    @staticmethod
    def print_webhook_info():
        """Print webhook configuration information for setup"""
        print("\n🔗 WEBHOOK CONFIGURATION")
        print("=" * 50)
        
        base_url = WebhookConfig.get_public_webhook_url()
        if not base_url:
            print("❌ Could not determine public webhook URL")
            print("📝 Solutions:")
            print("   - Set WEBHOOK_URL environment variable")
            print("   - Start ngrok tunnel for development")
            print("   - Deploy to Koyeb for production")
            return
        
        endpoints = WebhookConfig.get_webhook_endpoints()
        
        print(f"🌍 Base URL: {base_url}")
        print(f"🎯 Environment: {'Production' if WebhookConfig._detect_koyeb_url() else 'Development'}")
        print("\n📍 Webhook Endpoints:")
        for name, url in endpoints.items():
            print(f"   {name}: {url}")
        
        print("\n📋 RSS.app Configuration:")
        instructions = WebhookConfig.get_rss_app_instructions()
        print(f"   Webhook URL: {instructions['webhook_url']}")
        print(f"   Test Command: {instructions['test_command']}")
        print(f"   Dashboard: {instructions['monitoring_dashboard']}")
        print(f"   Note: {instructions['note']}")
        print()

if __name__ == "__main__":
    # Test the webhook configuration
    WebhookConfig.print_webhook_info()
    
    print("\n🔍 TESTING WEBHOOK ACCESS...")
    results = WebhookConfig.validate_webhook_access()
    for name, result in results.items():
        status = "✅" if result.get('accessible') else "❌"
        print(f"{status} {name}: {result['url']} (Status: {result.get('status_code', 'Error')})") 