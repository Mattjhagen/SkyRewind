#!/usr/bin/env python3
"""
ADS-B Logger - Polls aircraft.json and stores positions in SQLite.
Runs continuously, polling every 10 seconds.
"""

import json
import time
import sys
import os
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import init_db, insert_adsb_position, prune_old_positions

# Path to dump1090 aircraft.json
AIRCRAFT_JSON_PATH = '/var/run/dump1090-mutability/aircraft.json'

# Polling interval in seconds
POLL_INTERVAL = 10

# Prune old data daily
LAST_PRUNE = None
PRUNE_INTERVAL_HOURS = 24

def read_aircraft_json(path):
    """Read and parse aircraft.json file."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return data.get('aircraft', [])
    except FileNotFoundError:
        print(f"Warning: {path} not found. Is dump1090 running?")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return []
    except Exception as e:
        print(f"Error reading aircraft data: {e}")
        return []

def log_aircraft(aircraft_list):
    """Store aircraft positions in database."""
    count = 0

    for aircraft in aircraft_list:
        # Only log if we have position data
        if 'lat' not in aircraft or 'lon' not in aircraft:
            continue

        icao_hex = aircraft.get('hex', '').upper()
        if not icao_hex:
            continue

        callsign = aircraft.get('flight', '').strip() or None
        lat = aircraft.get('lat')
        lon = aircraft.get('lon')
        altitude = aircraft.get('altitude')
        ground_speed = aircraft.get('speed')
        track = aircraft.get('track')
        squawk = aircraft.get('squawk')

        try:
            insert_adsb_position(
                icao_hex=icao_hex,
                callsign=callsign,
                lat=lat,
                lon=lon,
                altitude=altitude,
                ground_speed=ground_speed,
                track=track,
                squawk=squawk
            )
            count += 1
        except Exception as e:
            print(f"Error inserting position for {icao_hex}: {e}")

    return count

def should_prune():
    """Check if it's time to prune old data."""
    global LAST_PRUNE

    if LAST_PRUNE is None:
        return True

    elapsed = datetime.now(timezone.utc) - LAST_PRUNE
    return elapsed.total_seconds() >= PRUNE_INTERVAL_HOURS * 3600

def main():
    """Main logger loop."""
    global LAST_PRUNE

    print("Initializing SkyRewind ADS-B Logger...")
    init_db()
    print(f"Polling {AIRCRAFT_JSON_PATH} every {POLL_INTERVAL} seconds")
    print("Press Ctrl+C to stop\n")

    iteration = 0

    try:
        while True:
            iteration += 1
            start_time = time.time()

            # Read aircraft data
            aircraft_list = read_aircraft_json(AIRCRAFT_JSON_PATH)

            # Log positions
            count = log_aircraft(aircraft_list)

            # Prune old data if needed
            if should_prune():
                print(f"Pruning data older than 30 days...")
                deleted = prune_old_positions(days=30)
                print(f"Pruned {deleted} old positions")
                LAST_PRUNE = datetime.now(timezone.utc)

            elapsed = time.time() - start_time
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            print(f"[{timestamp}] Iteration {iteration}: Logged {count} aircraft in {elapsed:.2f}s")

            # Sleep until next poll
            sleep_time = max(0, POLL_INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nLogger stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
