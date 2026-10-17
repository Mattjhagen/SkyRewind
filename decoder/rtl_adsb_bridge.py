#!/usr/bin/env python3
"""
RTL-ADS-B Bridge - Spawns rtl_adsb and decodes Mode-S messages into aircraft.json

Replaces dump1090-mutability on hardware where it decodes only noise while rtl_adsb
produces valid Mode-S frames.
"""

import subprocess
import json
import time
import sys
import os
import re
from datetime import datetime, timezone
from collections import defaultdict

try:
    import pyModeS as pms
    HAS_PYMODES = True
except ImportError:
    HAS_PYMODES = False
    print("Warning: pyModeS not available, CPR decoding disabled", file=sys.stderr)

# Receiver position for CPR local decode
RECEIVER_LAT = 41.25
RECEIVER_LON = -95.95

# Output path
OUTPUT_PATH = '/var/run/dump1090-mutability/aircraft.json'

# Aircraft state timeout
AIRCRAFT_TIMEOUT = 60  # seconds

class Aircraft:
    """State for a single aircraft."""
    def __init__(self, icao_hex):
        self.icao_hex = icao_hex
        self.callsign = None
        self.lat = None
        self.lon = None
        self.altitude = None
        self.speed = None
        self.track = None
        self.squawk = None
        self.last_seen = time.time()
        self.last_position_time = 0
        # CPR position data - need both even/odd frames + hex strings for global decode
        self.odd_cpr_lat = None
        self.odd_cpr_lon = None
        self.odd_cpr_time = 0
        self.odd_hex = None
        self.even_cpr_lat = None
        self.even_cpr_lon = None
        self.even_cpr_time = 0
        self.even_hex = None

    def update_seen(self):
        """Update last seen timestamp."""
        self.last_seen = time.time()

    def to_dict(self):
        """Convert to dict for JSON output (dump1090 format)."""
        if self.lat is None or self.lon is None:
            return None

        result = {
            'hex': self.icao_hex.lower(),
            'flight': self.callsign.strip() if self.callsign else None,
            'lat': self.lat,
            'lon': self.lon,
            'altitude': self.altitude,
            'speed': self.speed,
            'track': self.track,
            'squawk': self.squawk,
            'seen': int(time.time() - self.last_seen)
        }
        return result


class RTLADSBBridge:
    """Main bridge daemon."""

    def __init__(self):
        self.aircraft = {}  # ICAO hex -> Aircraft
        self.messages_received = 0
        self.start_time = time.time()
        self.rtl_adsb_process = None
        self.spawn_time = 0
        self.rapid_death_count = 0
        self.last_stderr_line = None

    def spawn_rtl_adsb(self):
        """Spawn rtl_adsb subprocess, capture stderr for error reporting."""
        try:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Spawning rtl_adsb...", file=sys.stderr)
            self.rtl_adsb_process = subprocess.Popen(
                ['rtl_adsb'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # Capture stderr to log critical errors
                bufsize=1,
                universal_newlines=True
            )
            self.spawn_time = time.time()
            print(f"[{datetime.now(timezone.utc).isoformat()}] rtl_adsb started (PID: {self.rtl_adsb_process.pid})", file=sys.stderr)
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR spawning rtl_adsb: {e}", file=sys.stderr)
            sys.exit(1)

    def read_rtl_adsb_output(self):
        """Generator that yields hex messages from rtl_adsb stdout."""
        if not self.rtl_adsb_process:
            return

        try:
            for line in self.rtl_adsb_process.stdout:
                line = line.strip()
                if line.startswith('*') and line.endswith(';'):
                    # Extract hex between * and ;
                    hex_msg = line[1:-1]
                    yield hex_msg
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR reading rtl_adsb: {e}", file=sys.stderr)

    def decode_message(self, hex_msg):
        """Decode a Mode-S hex message and update aircraft state."""
        if not HAS_PYMODES or len(hex_msg) < 2:
            return

        try:
            self.messages_received += 1

            # Get downlink format
            df = pms.df(hex_msg)

            # Extract ICAO address
            if df == 17 or df == 18:  # ADS-B
                icao = pms.adsb.icao(hex_msg)
            elif df == 5 or df == 21:  # Surveillance altitude reply
                icao = pms.icao(hex_msg)
            else:
                return  # Ignore other DF types

            if not icao:
                return

            icao = icao.upper()

            # Get or create aircraft
            if icao not in self.aircraft:
                self.aircraft[icao] = Aircraft(icao)

            aircraft = self.aircraft[icao]
            aircraft.update_seen()

            # Decode DF17/18 (ADS-B)
            if df == 17 or df == 18:
                tc = pms.adsb.typecode(hex_msg)

                # Callsign (TC 1-4)
                if 1 <= tc <= 4:
                    callsign = pms.adsb.callsign(hex_msg)
                    if callsign:
                        aircraft.callsign = callsign

                # Airborne position (TC 9-18)
                elif 9 <= tc <= 18:
                    # Get altitude
                    alt = pms.adsb.altitude(hex_msg)
                    if alt:
                        aircraft.altitude = alt

                    # CPR position decoding - need both even/odd frames + hex strings
                    oe_flag = pms.adsb.oe_flag(hex_msg)
                    lat_cpr = pms.adsb.cprlat(hex_msg)
                    lon_cpr = pms.adsb.cprlon(hex_msg)
                    now = time.time()

                    if oe_flag == 0:  # Even frame
                        aircraft.even_cpr_lat = lat_cpr
                        aircraft.even_cpr_lon = lon_cpr
                        aircraft.even_cpr_time = now
                        aircraft.even_hex = hex_msg
                    else:  # Odd frame
                        aircraft.odd_cpr_lat = lat_cpr
                        aircraft.odd_cpr_lon = lon_cpr
                        aircraft.odd_cpr_time = now
                        aircraft.odd_hex = hex_msg

                    # Try CPR decode if we have a recent pair
                    time_diff = abs(aircraft.even_cpr_time - aircraft.odd_cpr_time)
                    if (aircraft.even_hex is not None and
                        aircraft.odd_hex is not None and
                        time_diff < 10):  # Frames within 10 seconds

                        lat, lon = None, None

                        try:
                            # Try global decode first (needs both even and odd frames)
                            lat, lon = pms.adsb.position(
                                aircraft.even_hex,
                                aircraft.odd_hex,
                                aircraft.even_cpr_time,
                                aircraft.odd_cpr_time
                            )
                        except Exception:
                            pass  # Global decode failed

                        # Fall back to local decode with receiver reference
                        if lat is None or lon is None:
                            try:
                                # Local decode with receiver position (must be within 180 NM)
                                lat, lon = pms.adsb.position_with_ref(
                                    hex_msg,
                                    RECEIVER_LAT,
                                    RECEIVER_LON
                                )
                            except Exception:
                                pass  # Local decode failed

                        # Sanity check and update position
                        if lat is not None and lon is not None:
                            # Must be within reasonable range of receiver
                            if abs(lat - RECEIVER_LAT) < 10 and abs(lon - RECEIVER_LON) < 10:
                                aircraft.lat = lat
                                aircraft.lon = lon
                                aircraft.last_position_time = time.time()
                            # else: position outside expected range, ignore

                # Airborne velocity (TC 19)
                elif tc == 19:
                    try:
                        velocity = pms.adsb.velocity(hex_msg)
                        if velocity:
                            speed, track, _, _ = velocity
                            if speed:
                                aircraft.speed = int(speed)
                            if track:
                                aircraft.track = int(track)
                    except Exception:
                        pass

            # Decode DF5/21 (Squawk)
            elif df == 5 or df == 21:
                try:
                    # Try to extract squawk if available
                    # pyModeS doesn't have direct squawk decoder, skip for now
                    pass
                except Exception:
                    pass

        except Exception as e:
            # Silently ignore decode errors
            pass

    def prune_old_aircraft(self):
        """Remove aircraft not seen in AIRCRAFT_TIMEOUT seconds."""
        now = time.time()
        to_remove = [
            icao for icao, aircraft in self.aircraft.items()
            if now - aircraft.last_seen > AIRCRAFT_TIMEOUT
        ]
        for icao in to_remove:
            del self.aircraft[icao]

        if to_remove:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Pruned {len(to_remove)} stale aircraft", file=sys.stderr)

    def write_aircraft_json(self):
        """Write aircraft.json in dump1090 format."""
        try:
            # Prune old aircraft first
            self.prune_old_aircraft()

            # Build aircraft list (only those with position)
            aircraft_list = []
            for aircraft in self.aircraft.values():
                data = aircraft.to_dict()
                if data:
                    aircraft_list.append(data)

            # Build output structure
            output = {
                'now': time.time(),
                'messages': self.messages_received,
                'aircraft': aircraft_list
            }

            # Ensure output directory exists
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

            # Write atomically (write to temp, then rename)
            temp_path = OUTPUT_PATH + '.tmp'
            with open(temp_path, 'w') as f:
                json.dump(output, f)

            os.rename(temp_path, OUTPUT_PATH)

        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR writing aircraft.json: {e}", file=sys.stderr)

    def get_last_stderr_line(self):
        """Get last stderr line from rtl_adsb without blocking."""
        if not self.rtl_adsb_process or not self.rtl_adsb_process.stderr:
            return None

        try:
            # Non-blocking read of available stderr
            import select
            if select.select([self.rtl_adsb_process.stderr], [], [], 0)[0]:
                line = self.rtl_adsb_process.stderr.readline()
                if line:
                    self.last_stderr_line = line.strip()
        except Exception:
            pass

        return self.last_stderr_line

    def run(self):
        """Main daemon loop with backoff on rapid deaths."""
        print(f"[{datetime.now(timezone.utc).isoformat()}] RTL-ADS-B Bridge starting...", file=sys.stderr)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Receiver position: {RECEIVER_LAT}, {RECEIVER_LON}", file=sys.stderr)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Output: {OUTPUT_PATH}", file=sys.stderr)

        last_write_time = time.time()
        last_status_time = time.time()

        while True:
            try:
                # Spawn or respawn rtl_adsb
                if not self.rtl_adsb_process or self.rtl_adsb_process.poll() is not None:
                    if self.rtl_adsb_process:
                        # Check if death was rapid (<2s since spawn)
                        death_time = time.time()
                        uptime = death_time - self.spawn_time

                        # Try to get stderr for diagnostics
                        self.get_last_stderr_line()

                        if uptime < 2.0:
                            # Rapid death
                            self.rapid_death_count += 1
                            print(f"[{datetime.now(timezone.utc).isoformat()}] rtl_adsb died after {uptime:.1f}s "
                                  f"(rapid death #{self.rapid_death_count})", file=sys.stderr)

                            if self.rapid_death_count >= 3:
                                # Backoff after 3 rapid deaths
                                stderr_msg = self.last_stderr_line or "(no stderr captured)"
                                print(f"[{datetime.now(timezone.utc).isoformat()}] rtl_adsb dying rapidly, backing off 5s — "
                                      f"last stderr: {stderr_msg}", file=sys.stderr)
                                time.sleep(5)
                        else:
                            # Clean run, reset counter
                            if uptime > 10.0:
                                self.rapid_death_count = 0

                        print(f"[{datetime.now(timezone.utc).isoformat()}] rtl_adsb died, restarting...", file=sys.stderr)

                    self.spawn_rtl_adsb()

                # Process messages
                for hex_msg in self.read_rtl_adsb_output():
                    self.decode_message(hex_msg)

                    # Periodically check stderr without blocking
                    self.get_last_stderr_line()

                    # Write aircraft.json every 1 second
                    now = time.time()
                    if now - last_write_time >= 1.0:
                        self.write_aircraft_json()
                        last_write_time = now

                    # Log status every 30 seconds
                    if now - last_status_time >= 30.0:
                        aircraft_with_pos = sum(1 for a in self.aircraft.values() if a.lat is not None)
                        print(f"[{datetime.now(timezone.utc).isoformat()}] Status: {self.messages_received} msgs, "
                              f"{len(self.aircraft)} aircraft ({aircraft_with_pos} with position)", file=sys.stderr)
                        last_status_time = now

            except KeyboardInterrupt:
                print(f"\n[{datetime.now(timezone.utc).isoformat()}] Shutting down...", file=sys.stderr)
                if self.rtl_adsb_process:
                    self.rtl_adsb_process.terminate()
                    self.rtl_adsb_process.wait()
                break
            except Exception as e:
                print(f"[{datetime.now(timezone.utc).isoformat()}] ERROR in main loop: {e}", file=sys.stderr)
                time.sleep(1)


if __name__ == '__main__':
    if not HAS_PYMODES:
        print("ERROR: pyModeS is required. Install with: pip install pyModeS", file=sys.stderr)
        sys.exit(1)

    bridge = RTLADSBBridge()
    bridge.run()
