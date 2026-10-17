import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app import haversine_distance


def test_haversine_distance_same_point():
    """Test distance between same point is zero."""
    distance = haversine_distance(40.7128, -74.0060, 40.7128, -74.0060)
    assert distance < 0.01  # Essentially zero


def test_haversine_distance_new_york_to_boston():
    """Test distance between New York City and Boston (~190 miles)."""
    # NYC: 40.7128°N, 74.0060°W
    # Boston: 42.3601°N, 71.0589°W
    distance = haversine_distance(40.7128, -74.0060, 42.3601, -71.0589)

    # Should be approximately 190 miles
    assert 185 < distance < 195


def test_haversine_distance_omaha_to_kansas_city():
    """Test distance between Omaha, NE and Kansas City, MO (~165 miles)."""
    # Omaha: 41.2565°N, 95.9345°W
    # Kansas City: 39.0997°N, 94.5786°W
    distance = haversine_distance(41.2565, -95.9345, 39.0997, -94.5786)

    # Should be approximately 165 miles
    assert 160 < distance < 170


def test_haversine_distance_los_angeles_to_san_francisco():
    """Test distance between Los Angeles and San Francisco (~350 miles)."""
    # LA: 34.0522°N, 118.2437°W
    # SF: 37.7749°N, 122.4194°W
    distance = haversine_distance(34.0522, -118.2437, 37.7749, -122.4194)

    # Should be approximately 350 miles
    assert 340 < distance < 360


def test_haversine_distance_chicago_to_denver():
    """Test distance between Chicago and Denver (~920 miles)."""
    # Chicago: 41.8781°N, 87.6298°W
    # Denver: 39.7392°N, 104.9903°W
    distance = haversine_distance(41.8781, -87.6298, 39.7392, -104.9903)

    # Should be approximately 920 miles
    assert 900 < distance < 940
