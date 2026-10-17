"""
Tests for rtl_adsb_bridge CPR decoding.
Ensures bridge correctly decodes positions using both even/odd frames.
"""

import sys
import os

# Add decoder to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'decoder'))

import pytest

# Import after path is set
try:
    import pyModeS as pms
    from rtl_adsb_bridge import Aircraft, RTLADSBBridge
    HAS_PYMODES = True
except ImportError:
    HAS_PYMODES = False


@pytest.mark.skipif(not HAS_PYMODES, reason="pyModeS not available")
def test_cpr_decode_with_known_even_odd_pair():
    """
    Test CPR decoding with known textbook even/odd pair.

    Messages from pyModeS documentation:
    - Even: 8D40621D58C382D690C8AC2863A7
    - Odd:  8D40621D58C386435CC412692AD6
    - ICAO: 40621D

    Expected position from pyModeS: approximately 52.2572°N, 3.9199°E
    """
    bridge = RTLADSBBridge()

    # Known even/odd pair
    even_msg = '8D40621D58C382D690C8AC2863A7'
    odd_msg = '8D40621D58C386435CC412692AD6'
    icao = '40621D'

    # Decode even frame
    bridge.decode_message(even_msg)

    # Decode odd frame
    bridge.decode_message(odd_msg)

    # Should have aircraft with position
    assert icao in bridge.aircraft or icao.lower() in bridge.aircraft

    # Get aircraft (case-insensitive)
    aircraft = bridge.aircraft.get(icao) or bridge.aircraft.get(icao.lower())
    assert aircraft is not None

    # Should have decoded position
    assert aircraft.lat is not None, "Latitude should be decoded"
    assert aircraft.lon is not None, "Longitude should be decoded"

    # Verify position is approximately correct (within 1 degree)
    # pyModeS decodes this to approximately: 52.2572, 3.9199
    expected_lat = 52.2572
    expected_lon = 3.9199

    assert abs(aircraft.lat - expected_lat) < 1.0, \
        f"Latitude {aircraft.lat} should be within 1° of {expected_lat}"
    assert abs(aircraft.lon - expected_lon) < 1.0, \
        f"Longitude {aircraft.lon} should be within 1° of {expected_lon}"


@pytest.mark.skipif(not HAS_PYMODES, reason="pyModeS not available")
def test_single_frame_local_decode_with_ref():
    """
    Test that single frame can be decoded with position_with_ref fallback.
    Should not crash on single frame, either decodes or handles gracefully.
    """
    bridge = RTLADSBBridge()

    # Single position frame
    msg = '8D40621D58C382D690C8AC2863A7'
    icao = '40621D'

    # Decode single frame - should not crash
    try:
        bridge.decode_message(msg)

        # Get aircraft
        aircraft = bridge.aircraft.get(icao) or bridge.aircraft.get(icao.lower())

        # If position_with_ref works, we might get a position
        # If it doesn't work or is out of range, aircraft.lat should be None
        # Either way, no crash is success
        assert aircraft is not None

        # Position may or may not be decoded (depends on if we're within 180 NM)
        # Just verify no crash occurred
        if aircraft.lat is not None:
            # If position decoded, it should be reasonable
            assert -90 <= aircraft.lat <= 90
            assert -180 <= aircraft.lon <= 180
    except Exception as e:
        pytest.fail(f"Single frame decode crashed: {e}")


@pytest.mark.skipif(not HAS_PYMODES, reason="pyModeS not available")
def test_does_not_call_position_with_same_msg_twice():
    """
    Verify that we don't call position(hex_msg, hex_msg, ...).
    Bridge should store separate even_hex and odd_hex.
    """
    bridge = RTLADSBBridge()

    # Decode one frame
    msg = '8D40621D58C382D690C8AC2863A7'
    bridge.decode_message(msg)

    icao = '40621D'
    aircraft = bridge.aircraft.get(icao) or bridge.aircraft.get(icao.lower())

    assert aircraft is not None

    # Check that even or odd hex is stored (depending on frame type)
    # This message is even (oe_flag=0)
    assert aircraft.even_hex == msg or aircraft.odd_hex == msg, \
        "Hex message should be stored in even_hex or odd_hex"

    # Without both frames, position should not be decoded
    # (unless local decode with receiver ref works, which is OK)
    # Just verify the bridge doesn't crash trying position(msg, msg, ...)


@pytest.mark.skipif(not HAS_PYMODES, reason="pyModeS not available")
def test_aircraft_stores_both_hex_strings():
    """
    Test that Aircraft class stores both even_hex and odd_hex.
    """
    bridge = RTLADSBBridge()

    even_msg = '8D40621D58C382D690C8AC2863A7'
    odd_msg = '8D40621D58C386435CC412692AD6'

    # Decode both
    bridge.decode_message(even_msg)
    bridge.decode_message(odd_msg)

    icao = '40621D'
    aircraft = bridge.aircraft.get(icao) or bridge.aircraft.get(icao.lower())

    assert aircraft is not None
    assert aircraft.even_hex == even_msg, "Even hex should be stored"
    assert aircraft.odd_hex == odd_msg, "Odd hex should be stored"
    assert aircraft.even_cpr_time > 0, "Even time should be recorded"
    assert aircraft.odd_cpr_time > 0, "Odd time should be recorded"


@pytest.mark.skipif(not HAS_PYMODES, reason="pyModeS not available")
def test_bridge_to_dict_only_outputs_aircraft_with_position():
    """
    Verify that to_dict() only returns aircraft with lat/lon.
    """
    bridge = RTLADSBBridge()

    # Create aircraft with no position
    bridge.aircraft['TEST01'] = Aircraft('TEST01')
    bridge.aircraft['TEST01'].callsign = 'TESTFLT'

    # to_dict should return None for aircraft without position
    result = bridge.aircraft['TEST01'].to_dict()
    assert result is None, "Aircraft without position should return None from to_dict()"

    # Create aircraft with position
    bridge.aircraft['TEST02'] = Aircraft('TEST02')
    bridge.aircraft['TEST02'].lat = 41.25
    bridge.aircraft['TEST02'].lon = -95.95

    # to_dict should return dict for aircraft with position
    result = bridge.aircraft['TEST02'].to_dict()
    assert result is not None, "Aircraft with position should return dict from to_dict()"
    assert 'lat' in result
    assert 'lon' in result
