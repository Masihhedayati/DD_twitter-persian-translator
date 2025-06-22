# Tests for main Flask application
import pytest
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_check(client):
    """Test health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data
    assert 'version' in data

def test_dashboard_route(client):
    """Test dashboard route"""
    response = client.get('/')
    assert response.status_code == 200
    # Note: This will fail until we create templates, which is expected

def test_api_tweets_route(client):
    """Test API tweets endpoint"""
    response = client.get('/api/tweets')
    assert response.status_code == 200
    data = response.get_json()
    assert 'tweets' in data
    assert 'count' in data
    assert 'status' in data
    assert data['status'] == 'success'

if __name__ == '__main__':
    pytest.main([__file__]) 