#!/usr/bin/env python3
"""
Demo Data Generator - Creates sample ADS-B data and sightings for testing.
Run this script to populate the database with demo data when dump1090 is not available.
"""

import sys
import os
import random
import json
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import init_db, insert_adsb_position, insert_sighting

# Omaha, NE area
CENTER_LAT = 41.25
CENTER_LON = -95.95
RADIUS = 0.5  # degrees (~35 miles)

# Sample aircraft
SAMPLE_AIRCRAFT = [
    {'icao': 'A12345', 'callsign': 'UAL1234'},
    {'icao': 'B67890', 'callsign': 'SWA5678'},
    {'icao': 'C24680', 'callsign': 'AAL9012'},
    {'icao': 'D13579', 'callsign': 'DAL3456'},
    {'icao': 'E97531', 'callsign': 'FDX7890'},
    {'icao': 'F86420', 'callsign': 'N12345'},
    {'icao': 'G75319', 'callsign': 'N67890'},
    {'icao': 'H64208', 'callsign': 'SKW2345'},
]

def generate_aircraft_path(start_lat, start_lon, heading, num_points=120):
    """Generate a realistic flight path."""
    positions = []
    lat, lon = start_lat, start_lon
    altitude = random.randint(25000, 35000)
    speed = random.randint(350, 500)

    for i in range(num_points):
        # Add some variation to heading
        heading_var = heading + random.uniform(-5, 5)
        heading_rad = math.radians(heading_var)

        # Move aircraft
        distance = 0.01  # degrees per iteration
        lat += distance * math.cos(heading_rad)
        lon += distance * math.sin(heading_rad) / math.cos(math.radians(lat))

        # Vary altitude slightly
        altitude += random.randint(-100, 100)
        altitude = max(20000, min(40000, altitude))

        positions.append({
            'lat': lat,
            'lon': lon,
            'altitude': altitude,
            'speed': speed + random.randint(-20, 20),
            'heading': heading_var % 360
        })

    return positions

def seed_adsb_data():
    """Generate historical ADS-B position data."""
    import math

    print("Generating ADS-B position data...")

    # Generate data for the past 2 hours
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=2)

    positions_added = 0

    for aircraft in SAMPLE_AIRCRAFT:
        # Random starting position
        start_lat = CENTER_LAT + random.uniform(-RADIUS, RADIUS)
        start_lon = CENTER_LON + random.uniform(-RADIUS, RADIUS)
        heading = random.uniform(0, 360)

        # Generate path
        path = generate_aircraft_path(start_lat, start_lon, heading)

        # Add positions with timestamps
        for i, pos in enumerate(path):
            timestamp = start_time + timedelta(seconds=i * 60)  # One position per minute
            if timestamp > end_time:
                break

            insert_adsb_position(
                icao_hex=aircraft['icao'],
                callsign=aircraft['callsign'],
                lat=pos['lat'],
                lon=pos['lon'],
                altitude=pos['altitude'],
                ground_speed=pos['speed'],
                track=pos['heading'],
                squawk=random.choice(['1200', '1234', '7700', None])
            )
            positions_added += 1

    print(f"Added {positions_added} ADS-B positions")

def seed_sightings():
    """Generate sample sighting reports."""
    print("Generating sample sightings...")

    sightings_data = [
        {
            'reporter_name': 'John Smith',
            'location_text': 'Near Memorial Park',
            'bearing': 270,
            'elevation': 45,
            'description': 'Bright light moving steadily westward, no sound heard',
            'duration': '2 minutes'
        },
        {
            'reporter_name': 'Sarah Johnson',
            'location_text': 'Downtown Omaha',
            'bearing': 180,
            'elevation': 30,
            'description': 'Red and green lights, appeared to be descending',
            'duration': '30 seconds'
        },
        {
            'reporter_name': 'Mike Davis',
            'location_text': 'Near Eppley Airfield',
            'bearing': 90,
            'elevation': 60,
            'description': 'Multiple white lights in formation, moving north',
            'duration': '5 minutes'
        }
    ]

    for i, sighting in enumerate(sightings_data):
        # Random time in the past hour
        sighting_time = datetime.utcnow() - timedelta(minutes=random.randint(10, 60))

        # Random location near center
        lat = CENTER_LAT + random.uniform(-0.1, 0.1)
        lon = CENTER_LON + random.uniform(-0.1, 0.1)

        insert_sighting(
            reporter_name=sighting['reporter_name'],
            sighting_time=sighting_time.isoformat(),
            lat=lat,
            lon=lon,
            location_text=sighting['location_text'],
            bearing=sighting['bearing'],
            elevation=sighting['elevation'],
            description=sighting['description'],
            duration=sighting['duration'],
            photo_path=None
        )

    print(f"Added {len(sightings_data)} sightings")

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

    data = {'aircraft': aircraft_list, 'now': datetime.utcnow().timestamp()}

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

    seed_adsb_data()
    seed_sightings()
    generate_mock_aircraft_json()

    print("\n✓ Demo data generated successfully!")
    print("\nYou can now:")
    print("1. Start the web server: python backend/app.py")
    print("2. Visit http://localhost:5000")
    print("3. View the Live, Report, and Rewind features")

if __name__ == '__main__':
    main()
