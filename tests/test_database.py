import pytest
import os
import tempfile
from datetime import datetime, timedelta, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend import database


@pytest.fixture
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        monkeypatch.setattr(database, 'DB_PATH', db_path)
        database.init_db()
        yield db_path


def test_insert_and_query_adsb_position(temp_db):
    """Test inserting and querying ADS-B positions."""
    now = datetime.now(timezone.utc)

    database.insert_adsb_position(
        icao_hex='ABC123',
        callsign='TEST123',
        lat=40.7128,
        lon=-74.0060,
        altitude=35000,
        ground_speed=450,
        track=270,
        squawk='1200'
    )

    # Query recent positions
    start = (now - timedelta(minutes=5)).isoformat()
    end = (now + timedelta(minutes=5)).isoformat()
    positions = database.get_positions_in_timerange(start, end)

    assert len(positions) == 1
    assert positions[0]['icao_hex'] == 'ABC123'
    assert positions[0]['callsign'] == 'TEST123'
    assert positions[0]['lat'] == 40.7128
    assert positions[0]['altitude'] == 35000


def test_insert_with_custom_timestamp(temp_db):
    """Test inserting positions with custom timestamps."""
    past = datetime.now(timezone.utc) - timedelta(hours=1)

    database.insert_adsb_position(
        icao_hex='XYZ789',
        callsign='OLD123',
        lat=41.25,
        lon=-95.95,
        altitude=30000,
        ground_speed=400,
        track=180,
        squawk='1234',
        timestamp=past.isoformat()
    )

    # Should find it in the right time range
    start = (past - timedelta(minutes=5)).isoformat()
    end = (past + timedelta(minutes=5)).isoformat()
    positions = database.get_positions_in_timerange(start, end)

    assert len(positions) == 1
    assert positions[0]['icao_hex'] == 'XYZ789'


def test_prune_old_positions(temp_db):
    """Test pruning positions older than specified days."""
    now = datetime.now(timezone.utc)

    # Insert recent position
    database.insert_adsb_position(
        icao_hex='NEW123',
        callsign='RECENT',
        lat=40.0,
        lon=-74.0,
        altitude=30000,
        ground_speed=400,
        track=90,
        squawk='1200',
        timestamp=now.isoformat()
    )

    # Insert old position (31 days ago)
    old_time = now - timedelta(days=31)
    database.insert_adsb_position(
        icao_hex='OLD123',
        callsign='ANCIENT',
        lat=41.0,
        lon=-75.0,
        altitude=25000,
        ground_speed=350,
        track=180,
        squawk='1234',
        timestamp=old_time.isoformat()
    )

    # Prune positions older than 30 days
    deleted = database.prune_old_positions(days=30)

    assert deleted == 1

    # Verify only recent position remains
    start = (now - timedelta(hours=1)).isoformat()
    end = (now + timedelta(hours=1)).isoformat()
    positions = database.get_positions_in_timerange(start, end)

    assert len(positions) == 1
    assert positions[0]['icao_hex'] == 'NEW123'


def test_insert_and_get_sighting(temp_db):
    """Test inserting and retrieving sightings."""
    now = datetime.now(timezone.utc)

    sighting_id = database.insert_sighting(
        reporter_name='John Doe',
        sighting_time=now.isoformat(),
        lat=41.25,
        lon=-95.95,
        location_text='Near downtown',
        bearing=270,
        elevation=45,
        description='Bright light moving westward',
        duration='2 minutes',
        photo_path='photo.jpg'
    )

    assert sighting_id > 0

    # Retrieve by ID
    sighting = database.get_sighting(sighting_id)

    assert sighting is not None
    assert sighting['reporter_name'] == 'John Doe'
    assert sighting['bearing'] == 270
    assert sighting['description'] == 'Bright light moving westward'

    # Get all sightings
    all_sightings = database.get_sightings()
    assert len(all_sightings) == 1


def test_get_latest_positions(temp_db):
    """Test retrieving latest position for each aircraft."""
    now = datetime.now(timezone.utc)

    # Insert multiple positions for same aircraft
    database.insert_adsb_position(
        icao_hex='ABC123',
        callsign='TEST',
        lat=40.0,
        lon=-74.0,
        altitude=30000,
        ground_speed=400,
        track=90,
        squawk='1200',
        timestamp=(now - timedelta(minutes=2)).isoformat()
    )

    database.insert_adsb_position(
        icao_hex='ABC123',
        callsign='TEST',
        lat=40.1,
        lon=-74.1,
        altitude=31000,
        ground_speed=410,
        track=95,
        squawk='1200',
        timestamp=(now - timedelta(seconds=30)).isoformat()
    )

    # Insert position for different aircraft
    database.insert_adsb_position(
        icao_hex='XYZ789',
        callsign='OTHER',
        lat=41.0,
        lon=-75.0,
        altitude=25000,
        ground_speed=350,
        track=180,
        squawk='1234',
        timestamp=now.isoformat()
    )

    # Get latest positions
    latest = database.get_latest_positions()

    # Should get one position per aircraft (2 total)
    assert len(latest) == 2

    # ABC123 should have the more recent position
    abc_pos = [p for p in latest if p['icao_hex'] == 'ABC123'][0]
    assert abc_pos['lat'] == 40.1
    assert abc_pos['altitude'] == 31000
