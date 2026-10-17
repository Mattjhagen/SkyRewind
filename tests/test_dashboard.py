"""
Tests for server-dashboard application.
Ensures dashboard API returns correct structure and has no injection surfaces.
"""

import sys
import os

# Add server-dashboard to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server-dashboard'))

from app import app

import pytest


@pytest.fixture
def client():
    """Create test client for dashboard app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_dashboard_index_returns_html(client):
    """GET / should return HTML with r410 reference."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'r410' in response.data
    assert b'SkyRewind' in response.data


def test_api_status_returns_json(client):
    """GET /api/status should return valid JSON with expected structure."""
    response = client.get('/api/status')
    assert response.status_code == 200
    assert response.content_type == 'application/json'

    data = response.get_json()

    # Check all top-level keys exist
    assert 'time' in data
    assert 'services' in data
    assert 'pipeline' in data
    assert 'system' in data
    assert 'ports' in data
    assert 'bridge_log' in data

    # Check services is a list
    assert isinstance(data['services'], list)

    # Check pipeline structure
    assert 'aircraft_json_exists' in data['pipeline']
    assert 'messages' in data['pipeline']
    assert 'aircraft' in data['pipeline']

    # Check system structure
    assert 'uptime' in data['system']
    assert 'load' in data['system']

    # Check ports structure
    assert '5000_web' in data['ports']
    assert '3001_blog' in data['ports']
    assert '5001_dashboard' in data['ports']

    # Check bridge_log is a list
    assert isinstance(data['bridge_log'], list)


def test_api_status_takes_no_params(client):
    """API should ignore query params - no injection surface."""
    # Send various query params - should be ignored
    response1 = client.get('/api/status')
    response2 = client.get('/api/status?service=evil')
    response3 = client.get('/api/status?cmd=rm%20-rf')

    # All should return same structure
    data1 = response1.get_json()
    data2 = response2.get_json()
    data3 = response3.get_json()

    # Should have same keys (timestamps will differ)
    assert set(data1.keys()) == set(data2.keys())
    assert set(data1.keys()) == set(data3.keys())


def test_api_status_never_crashes_on_missing_resources(client, monkeypatch):
    """API should handle missing files/commands gracefully."""
    # Simulate missing aircraft.json and other failures
    def mock_safe_subprocess(cmd, timeout=3):
        # Always fail
        return '', 'error', -1

    import app as dashboard_app
    monkeypatch.setattr(dashboard_app, 'safe_subprocess', mock_safe_subprocess)

    response = client.get('/api/status')
    assert response.status_code == 200

    data = response.get_json()
    # Should still have all keys, values may be null/unknown
    assert 'services' in data
    assert 'pipeline' in data
    assert 'system' in data


def test_dashboard_services_include_expected_names(client):
    """Services list should include expected service names."""
    response = client.get('/api/status')
    data = response.get_json()

    service_names = [s['name'] for s in data['services']]

    # Expected services
    assert 'skyrewind-web' in service_names
    assert 'skyrewind-logger' in service_names
    assert 'skyrewind-adsb-bridge' in service_names
    assert any('cloudflared' in name for name in service_names)
    assert any('SDR Blog' in name for name in service_names)


def test_dashboard_ports_always_includes_self(client):
    """Dashboard should always report itself as 'up'."""
    response = client.get('/api/status')
    data = response.get_json()

    # Dashboard responding = port 5001 is up
    assert data['ports']['5001_dashboard'] == 'up'
