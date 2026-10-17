import sqlite3
from datetime import datetime, timedelta, timezone
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'skyrewind.db')

def get_db():
    """Get database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema."""
    conn = get_db()
    cursor = conn.cursor()

    # ADS-B position history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS adsb_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            icao_hex TEXT NOT NULL,
            callsign TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            altitude INTEGER,
            ground_speed REAL,
            track REAL,
            squawk TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # Index for efficient time-range queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON adsb_positions(timestamp)
    ''')

    # Index for ICAO hex lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_icao
        ON adsb_positions(icao_hex)
    ''')

    # Sighting reports
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_name TEXT NOT NULL,
            sighting_time TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            location_text TEXT,
            bearing REAL,
            elevation REAL,
            description TEXT NOT NULL,
            duration TEXT,
            photo_path TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sighting_time
        ON sightings(sighting_time)
    ''')

    conn.commit()
    conn.close()

def prune_old_positions(days=30):
    """Remove ADS-B positions older than specified days."""
    conn = get_db()
    cursor = conn.cursor()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor.execute('DELETE FROM adsb_positions WHERE timestamp < ?', (cutoff,))
    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    return deleted

def insert_adsb_position(icao_hex, callsign, lat, lon, altitude, ground_speed, track, squawk, timestamp=None):
    """Insert a new ADS-B position snapshot."""
    conn = get_db()
    cursor = conn.cursor()

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    cursor.execute('''
        INSERT INTO adsb_positions
        (icao_hex, callsign, lat, lon, altitude, ground_speed, track, squawk, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (icao_hex, callsign, lat, lon, altitude, ground_speed, track, squawk, timestamp))

    conn.commit()
    conn.close()

def insert_sighting(reporter_name, sighting_time, lat, lon, location_text,
                   bearing, elevation, description, duration, photo_path):
    """Insert a new sighting report."""
    conn = get_db()
    cursor = conn.cursor()

    created_at = datetime.now(timezone.utc).isoformat()

    cursor.execute('''
        INSERT INTO sightings
        (reporter_name, sighting_time, lat, lon, location_text, bearing,
         elevation, description, duration, photo_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (reporter_name, sighting_time, lat, lon, location_text, bearing,
          elevation, description, duration, photo_path, created_at))

    sighting_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return sighting_id

def get_sightings():
    """Get all sighting reports."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM sightings
        ORDER BY sighting_time DESC
    ''')

    sightings = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return sightings

def get_sighting(sighting_id):
    """Get a specific sighting by ID."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM sightings WHERE id = ?', (sighting_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None

def get_positions_in_timerange(start_time, end_time):
    """Get all ADS-B positions within a time range."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM adsb_positions
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
    ''', (start_time, end_time))

    positions = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return positions

def get_latest_positions():
    """Get the most recent position for each aircraft."""
    conn = get_db()
    cursor = conn.cursor()

    # Get positions from the last 2 minutes
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()

    cursor.execute('''
        SELECT * FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY icao_hex ORDER BY timestamp DESC) as rn
            FROM adsb_positions
            WHERE timestamp >= ?
        ) WHERE rn = 1
    ''', (cutoff,))

    positions = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return positions
