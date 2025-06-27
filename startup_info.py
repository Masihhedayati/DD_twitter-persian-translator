"""
Startup Information Display for Twitter Monitor
Shows webhook configuration and deployment instructions
"""
import os
import sys
import logging

def display_startup_info():
    """Display startup information and webhook configuration"""
    
    # Import here to avoid circular imports
    try:
        from core.webhook_config import WebhookConfig
    except ImportError:
        print("⚠️  Warning: Could not import WebhookConfig")
        return
    
    print("\n" + "=" * 70)
    print("🚀 TWITTER MONITOR STARTING UP")
    print("=" * 70)
    
    # Environment detection
    is_production = WebhookConfig._detect_koyeb_url() is not None
    environment = "PRODUCTION (Koyeb)" if is_production else "DEVELOPMENT"
    
    print(f"🎯 Environment: {environment}")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print(f"📁 Working Directory: {os.getcwd()}")
    
    # Webhook configuration
    print("\n🔗 WEBHOOK CONFIGURATION")
    print("-" * 50)
    
    try:
        base_url = WebhookConfig.get_public_webhook_url()
        if base_url:
            endpoints = WebhookConfig.get_webhook_endpoints()
            instructions = WebhookConfig.get_rss_app_instructions()
            
            print(f"🌍 Base URL: {base_url}")
            print(f"📍 RSS Webhook: {endpoints.get('rss_webhook', 'Not available')}")
            print(f"🏥 Health Check: {endpoints.get('health_check', 'Not available')}")
            print(f"📊 Dashboard: {endpoints.get('dashboard', 'Not available')}")
            
            # RSS.app setup instructions
            print(f"\n📋 RSS.app Setup:")
            if is_production:
                print("✅ Production webhook URL (permanent)")
            else:
                print("⚠️  Development webhook URL (may change)")
            
            print(f"   Webhook URL: {endpoints.get('rss_webhook', 'Error')}")
            print(f"   Test Command: curl -X POST {endpoints.get('rss_webhook', '')}/test")
            
        else:
            print("❌ Could not determine webhook URL")
            print("📝 Troubleshooting:")
            if not is_production:
                print("   - Start ngrok: ./scripts/start-dev-tunnel.sh")
                print("   - Or set WEBHOOK_URL environment variable")
            else:
                print("   - Check Koyeb deployment status")
                print("   - Verify environment variables")
        
    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")
    
    # Environment variables check
    print(f"\n🔑 CONFIGURATION CHECK")
    print("-" * 50)
    
    required_vars = [
        'TWITTER_API_KEY',
        'OPENAI_API_KEY', 
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID'
    ]
    
    for var in required_vars:
        value = os.environ.get(var)
        status = "✅" if value else "❌"
        masked_value = f"{value[:8]}..." if value and len(value) > 8 else "Not set"
        print(f"   {status} {var}: {masked_value}")
    
    # Database check
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgresql'):
            print("   ✅ DATABASE: PostgreSQL (Production)")
        else:
            print("   ✅ DATABASE: SQLite (Development)")
    else:
        print("   ⚠️  DATABASE: Using default SQLite")
    
    # Webhook mode
    webhook_only = os.environ.get('WEBHOOK_ONLY_MODE', 'false').lower() == 'true'
    hybrid_mode = os.environ.get('HYBRID_MODE', 'true').lower() == 'true'
    
    print(f"\n⚙️  OPERATION MODE")
    print("-" * 50)
    if webhook_only:
        print("   📡 Mode: Webhook-only (Efficient)")
    elif hybrid_mode:
        print("   🔄 Mode: Hybrid (Initial scrape + webhooks)")
    else:
        print("   🔄 Mode: Continuous polling")
    
    monitored_users = os.environ.get('MONITORED_USERS', '')
    if monitored_users:
        users = monitored_users.split(',')
        print(f"   👥 Monitoring: {len(users)} users ({', '.join(users[:3])}{'...' if len(users) > 3 else ''})")
    else:
        print("   👥 Monitoring: Default users (elonmusk, naval, paulg)")
    
    print(f"\n🚀 APPLICATION READY!")
    print("=" * 70)
    
    # Final instructions based on environment
    if is_production:
        print("📝 Next Steps (Production):")
        print("   1. Configure RSS.app with the webhook URL above")
        print("   2. Monitor the dashboard for incoming tweets")
        print("   3. Check logs for any issues")
    else:
        print("📝 Next Steps (Development):")
        print("   1. Ensure ngrok is running for webhook access")
        print("   2. Configure RSS.app with the webhook URL above")
        print("   3. Test with the curl command above")
    
    print()

if __name__ == "__main__":
    display_startup_info() 