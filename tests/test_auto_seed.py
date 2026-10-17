import pytest
import os
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend import database
from backend.app import auto_seed_if_needed


def test_auto_seed_with_env_var(monkeypatch):
    """Test that SEED_DEMO=1 auto-seeds when database is empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        monkeypatch.setattr(database, 'DB_PATH', db_path)
        monkeypatch.setenv('SEED_DEMO', '1')

        # Initialize empty database
        database.init_db()

        # Call auto_seed - should seed
        auto_seed_if_needed()

        # Verify database was seeded
        conn = database.get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM adsb_positions')
        position_count = cursor.fetchone()[0]
        assert position_count == 960, f"Expected 960 positions, got {position_count}"

        cursor.execute('SELECT COUNT(DISTINCT icao_hex) FROM adsb_positions')
        aircraft_count = cursor.fetchone()[0]
        assert aircraft_count == 8, f"Expected 8 aircraft, got {aircraft_count}"

        cursor.execute('SELECT COUNT(*) FROM sightings')
        sighting_count = cursor.fetchone()[0]
        assert sighting_count == 3, f"Expected 3 sightings, got {sighting_count}"

        conn.close()


def test_no_auto_seed_without_env_var(monkeypatch):
    """Test that auto-seed does not run without SEED_DEMO=1."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        monkeypatch.setattr(database, 'DB_PATH', db_path)
        monkeypatch.delenv('SEED_DEMO', raising=False)

        # Initialize empty database
        database.init_db()

        # Call auto_seed - should NOT seed
        auto_seed_if_needed()

        # Verify tables exist but are empty
        conn = database.get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM adsb_positions')
        position_count = cursor.fetchone()[0]
        assert position_count == 0, f"Expected 0 positions without SEED_DEMO, got {position_count}"

        cursor.execute('SELECT COUNT(*) FROM sightings')
        sighting_count = cursor.fetchone()[0]
        assert sighting_count == 0, f"Expected 0 sightings without SEED_DEMO, got {sighting_count}"

        conn.close()


def test_auto_seed_idempotent(monkeypatch):
    """Test that calling auto_seed twice doesn't duplicate rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        monkeypatch.setattr(database, 'DB_PATH', db_path)
        monkeypatch.setenv('SEED_DEMO', '1')

        # Initialize and seed
        database.init_db()
        auto_seed_if_needed()

        # Check initial count
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM adsb_positions')
        first_count = cursor.fetchone()[0]
        assert first_count == 960

        # Call auto_seed again - should do nothing since table is not empty
        auto_seed_if_needed()

        # Verify count hasn't changed
        cursor.execute('SELECT COUNT(*) FROM adsb_positions')
        second_count = cursor.fetchone()[0]
        assert second_count == first_count, "auto_seed_if_needed should be idempotent"

        conn.close()
