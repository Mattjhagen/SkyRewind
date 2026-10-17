#!/usr/bin/env python3
"""
Demo Data Generator - Creates sample ADS-B data and sightings for testing.
Run this script to populate the database with demo data when dump1090 is not available.
"""

import sys
import os
import random
import json
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import init_db
from backend.seed_data import seed_demo_data, SAMPLE_AIRCRAFT, CENTER_LAT, CENTER_LON, RADIUS

def generate_mock_aircraft_json():
    """Generate a mock aircraft.json file for testing the logger without dump1090."""
    print("Generating mock aircraft.json...")

    aircraft_list = []

    for aircraft in SAMPLE_AIRCRAFT[:4]:  # Use subset for live data
        lat = CENTER_LAT + random.uniform(-RADIUS, RADIUS)
        lon = CENTER_LON + random.uniform(-RADIUS, RADIUS)

        aircraft_list.append({
            'hex': aircraft['icao'].lower(),
            'flight': aircraft['callsign'],
            'lat': lat,
            'lon': lon,
            'altitude': random.randint(25000, 35000),
            'speed': random.randint(350, 500),
            'track': random.randint(0, 359),
            'squawk': random.choice(['1200', '1234', None])
        })

    data = {'aircraft': aircraft_list, 'now': datetime.now(timezone.utc).timestamp()}

    # Write to a local mock file
    mock_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'mock_aircraft.json')
    with open(mock_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Mock aircraft.json written to {mock_path}")
    print("To test the logger with this file, edit logger/adsb_logger.py")
    print(f"and change AIRCRAFT_JSON_PATH to: {mock_path}")

def main():
    """Seed all demo data."""
    print("SkyRewind Demo Data Generator")
    print("=" * 50)

    init_db()

    print("Generating ADS-B position data and sightings...")
    positions, sightings = seed_demo_data()
    print(f"Added {positions} ADS-B positions")
    print(f"Added {sightings} sightings")

    generate_mock_aircraft_json()

    print("\n✓ Demo data generated successfully!")
    print("\nYou can now:")
    print("1. Start the web server: python backend/app.py")
    print("2. Visit http://localhost:5000")
    print("3. View the Live, Report, and Rewind features")

if __name__ == '__main__':
    main()
