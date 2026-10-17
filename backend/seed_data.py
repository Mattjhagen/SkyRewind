"""
Shared data seeding utilities for demo/preview environments.
"""

import random
import math
from datetime import datetime, timedelta, timezone

try:
    from database import insert_adsb_position, insert_sighting
except ImportError:
    from backend.database import insert_adsb_position, insert_sighting


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
    """Generate historical ADS-B position data (past 2 hours)."""
    end_time = datetime.now(timezone.utc)
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
                squawk=random.choice(['1200', '1234', '7700', None]),
                timestamp=timestamp.isoformat()
            )
            positions_added += 1

    return positions_added


def seed_sightings():
    """Generate sample sighting reports."""
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

    sightings_added = 0

    for sighting in sightings_data:
        # Random time in the past hour
        sighting_time = datetime.now(timezone.utc) - timedelta(minutes=random.randint(10, 60))

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
        sightings_added += 1

    return sightings_added


def seed_demo_data():
    """Seed both ADS-B positions and sightings."""
    positions = seed_adsb_data()
    sightings = seed_sightings()
    return positions, sightings
