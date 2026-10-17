from flask import Flask, request, jsonify, send_from_directory
import os
from datetime import datetime, timedelta, timezone
import math
from werkzeug.utils import secure_filename

from database import (
    init_db, get_sightings, get_sighting, insert_sighting,
    get_positions_in_timerange, get_latest_positions
)

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@app.route('/')
def index():
    """Serve the main frontend."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(frontend_path, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static frontend files."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(frontend_path, path)

@app.route('/api/sightings', methods=['GET', 'POST'])
def sightings():
    """Get all sightings or create a new one."""
    if request.method == 'GET':
        return jsonify(get_sightings())

    # POST - create new sighting
    data = request.form if request.files else request.json

    # Validate required fields
    required_fields = ['reporter_name', 'sighting_time', 'lat', 'lon', 'description']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Handle photo upload
    photo_path = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename:
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > MAX_FILE_SIZE:
                return jsonify({'error': 'File size exceeds 10MB limit'}), 413

            if allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now(timezone.utc).timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = filename

    try:
        sighting_id = insert_sighting(
            reporter_name=data.get('reporter_name'),
            sighting_time=data.get('sighting_time'),
            lat=float(data.get('lat')),
            lon=float(data.get('lon')),
            location_text=data.get('location_text'),
            bearing=float(data.get('bearing')) if data.get('bearing') else None,
            elevation=float(data.get('elevation')) if data.get('elevation') else None,
            description=data.get('description'),
            duration=data.get('duration'),
            photo_path=photo_path
        )
    except (ValueError, TypeError) as e:
        return jsonify({'error': f'Invalid data: {str(e)}'}), 400

    return jsonify({'id': sighting_id, 'success': True}), 201

@app.route('/api/sightings/<int:sighting_id>')
def get_sighting_detail(sighting_id):
    """Get a specific sighting."""
    sighting = get_sighting(sighting_id)
    if not sighting:
        return jsonify({'error': 'Sighting not found'}), 404
    return jsonify(sighting)

@app.route('/api/positions/rewind')
def rewind_positions():
    """Get ADS-B positions for a time range and location."""
    try:
        center_time = request.args.get('time')
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        radius = float(request.args.get('radius', 25))  # miles
        time_window = int(request.args.get('time_window', 10))  # minutes

        # Parse center time
        center_dt = datetime.fromisoformat(center_time.replace('Z', '+00:00'))

        # Get positions within time window
        start_time = (center_dt - timedelta(minutes=time_window)).isoformat()
        end_time = (center_dt + timedelta(minutes=time_window)).isoformat()

        all_positions = get_positions_in_timerange(start_time, end_time)

        # Filter by distance
        filtered_positions = []
        for pos in all_positions:
            distance = haversine_distance(lat, lon, pos['lat'], pos['lon'])
            if distance <= radius:
                pos['distance_miles'] = round(distance, 2)
                filtered_positions.append(pos)

        return jsonify(filtered_positions)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/positions/match')
def match_aircraft():
    """Find candidate aircraft for a sighting."""
    try:
        sighting_id = request.args.get('sighting_id')
        if not sighting_id:
            return jsonify({'error': 'sighting_id required'}), 400

        sighting = get_sighting(int(sighting_id))
        if not sighting:
            return jsonify({'error': 'Sighting not found'}), 404

        # Parse sighting time
        sighting_time = datetime.fromisoformat(sighting['sighting_time'].replace('Z', '+00:00'))

        # Get positions within ±10 minutes
        start_time = (sighting_time - timedelta(minutes=10)).isoformat()
        end_time = (sighting_time + timedelta(minutes=10)).isoformat()

        all_positions = get_positions_in_timerange(start_time, end_time)

        # Default radius: 25 miles
        radius = float(request.args.get('radius', 25))

        # Find closest approach for each aircraft
        candidates = {}
        for pos in all_positions:
            icao = pos['icao_hex']
            distance = haversine_distance(
                sighting['lat'], sighting['lon'],
                pos['lat'], pos['lon']
            )

            if distance <= radius:
                if icao not in candidates or distance < candidates[icao]['closest_distance']:
                    candidates[icao] = {
                        'icao_hex': icao,
                        'callsign': pos['callsign'],
                        'altitude': pos['altitude'],
                        'ground_speed': pos['ground_speed'],
                        'track': pos['track'],
                        'closest_distance': round(distance, 2),
                        'closest_time': pos['timestamp'],
                        'lat': pos['lat'],
                        'lon': pos['lon']
                    }

        # Sort by closest distance
        result = sorted(candidates.values(), key=lambda x: x['closest_distance'])

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/positions/live')
def live_positions():
    """Get current live ADS-B positions."""
    positions = get_latest_positions()
    return jsonify(positions)

@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded photos."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
