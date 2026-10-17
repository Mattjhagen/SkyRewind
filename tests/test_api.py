import pytest
import os
import tempfile
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend import database
from backend.app import app


@pytest.fixture
def client(monkeypatch):
    """Create a test client with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        upload_path = os.path.join(tmpdir, 'uploads')
        os.makedirs(upload_path)

        monkeypatch.setattr(database, 'DB_PATH', db_path)

        database.init_db()
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = upload_path

        with app.test_client() as client:
            yield client


def test_sighting_missing_required_field(client):
    """Test that missing required fields return 400."""
    # Missing reporter_name
    response = client.post('/api/sightings', json={
        'sighting_time': datetime.now(timezone.utc).isoformat(),
        'lat': 41.25,
        'lon': -95.95,
        'description': 'Test sighting'
    })
    assert response.status_code == 400
    assert b'reporter_name' in response.data

    # Missing sighting_time
    response = client.post('/api/sightings', json={
        'reporter_name': 'Test User',
        'lat': 41.25,
        'lon': -95.95,
        'description': 'Test sighting'
    })
    assert response.status_code == 400
    assert b'sighting_time' in response.data

    # Missing lat
    response = client.post('/api/sightings', json={
        'reporter_name': 'Test User',
        'sighting_time': datetime.now(timezone.utc).isoformat(),
        'lon': -95.95,
        'description': 'Test sighting'
    })
    assert response.status_code == 400
    assert b'lat' in response.data

    # Missing lon
    response = client.post('/api/sightings', json={
        'reporter_name': 'Test User',
        'sighting_time': datetime.now(timezone.utc).isoformat(),
        'lat': 41.25,
        'description': 'Test sighting'
    })
    assert response.status_code == 400
    assert b'lon' in response.data

    # Missing description
    response = client.post('/api/sightings', json={
        'reporter_name': 'Test User',
        'sighting_time': datetime.now(timezone.utc).isoformat(),
        'lat': 41.25,
        'lon': -95.95
    })
    assert response.status_code == 400
    assert b'description' in response.data


def test_sighting_invalid_lat_lon(client):
    """Test that invalid lat/lon values return 400."""
    response = client.post('/api/sightings', json={
        'reporter_name': 'Test User',
        'sighting_time': datetime.now(timezone.utc).isoformat(),
        'lat': 'invalid',
        'lon': -95.95,
        'description': 'Test sighting'
    })
    assert response.status_code == 400
    assert b'Invalid data' in response.data


def test_sighting_valid_submission(client):
    """Test successful sighting submission."""
    response = client.post('/api/sightings', json={
        'reporter_name': 'Test User',
        'sighting_time': datetime.now(timezone.utc).isoformat(),
        'lat': 41.25,
        'lon': -95.95,
        'description': 'Bright light moving westward',
        'bearing': 270,
        'elevation': 45,
        'duration': '2 minutes'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['success'] is True
    assert 'id' in data


def test_sighting_oversized_photo(client, tmp_path):
    """Test that oversized photos return 413."""
    # Create a fake 11MB file
    large_file = tmp_path / "large.jpg"
    large_file.write_bytes(b'0' * (11 * 1024 * 1024))

    with open(large_file, 'rb') as f:
        response = client.post('/api/sightings', data={
            'reporter_name': 'Test User',
            'sighting_time': datetime.now(timezone.utc).isoformat(),
            'lat': '41.25',
            'lon': '-95.95',
            'description': 'Test sighting',
            'photo': (f, 'large.jpg')
        }, content_type='multipart/form-data')

    assert response.status_code == 413
    assert b'exceeds 10MB' in response.data


def test_match_aircraft_sorting(client):
    """Test that match results are sorted by closest distance."""
    # Insert test data using the temp database
    now = datetime.now(timezone.utc)
    sighting_id = database.insert_sighting(
        reporter_name='Test User',
        sighting_time=now.isoformat(),
        lat=41.25,
        lon=-95.95,
        location_text='Test location',
        bearing=None,
        elevation=None,
        description='Test sighting',
        duration=None,
        photo_path=None
    )

    # Insert aircraft at various distances
    # Close aircraft (about 5 miles away)
    database.insert_adsb_position(
        icao_hex='CLOSE1',
        callsign='NEAR',
        lat=41.32,  # ~5 miles north
        lon=-95.95,
        altitude=30000,
        ground_speed=400,
        track=90,
        squawk='1200',
        timestamp=now.isoformat()
    )

    # Far aircraft (about 15 miles away)
    database.insert_adsb_position(
        icao_hex='FAR123',
        callsign='DISTANT',
        lat=41.45,  # ~15 miles north
        lon=-95.95,
        altitude=35000,
        ground_speed=450,
        track=180,
        squawk='1234',
        timestamp=now.isoformat()
    )

    # Medium aircraft (about 10 miles away)
    database.insert_adsb_position(
        icao_hex='MED456',
        callsign='MIDDLE',
        lat=41.38,  # ~10 miles north
        lon=-95.95,
        altitude=32000,
        ground_speed=420,
        track=270,
        squawk='1200',
        timestamp=now.isoformat()
    )

    # Query matches using the test client
    response = client.get(f'/api/positions/match?sighting_id={sighting_id}&radius=20')
    assert response.status_code == 200

    matches = response.get_json()
    assert len(matches) == 3

    # Verify sorted by closest distance
    assert matches[0]['icao_hex'] == 'CLOSE1'
    assert matches[1]['icao_hex'] == 'MED456'
    assert matches[2]['icao_hex'] == 'FAR123'

    # Verify distances are increasing
    assert matches[0]['closest_distance'] < matches[1]['closest_distance']
    assert matches[1]['closest_distance'] < matches[2]['closest_distance']
