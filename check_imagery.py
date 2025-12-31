import os
import requests
from PIL import Image
import imagehash
from io import BytesIO
from datetime import datetime
import math

def deg2tile(lat, lon, zoom):
    """Convert latitude/longitude to tile coordinates"""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)

# Configuration
LAT = float(os.environ['LATITUDE'])
LON = float(os.environ['LONGITUDE'])
ZOOM = int(os.environ.get('ZOOM_LEVEL', '18'))

# Get tile coordinates
x, y = deg2tile(LAT, LON, ZOOM)

# Esri World Imagery tile URL - NO API KEY NEEDED
url = f"https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{ZOOM}/{y}/{x}"

print(f"📍 Monitoring location: {LAT}, {LON}")
print(f"🗺️ Tile coordinates: zoom={ZOOM}, x={x}, y={y}")
print(f"🔗 URL: {url}")

# Download current image
response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
response.raise_for_status()
current_image = Image.open(BytesIO(response.content))

# Calculate hash of current image
current_hash = imagehash.average_hash(current_image)

# Read previous hash
hash_file = 'last_image.txt'
changed = False
should_save = False

if os.path.exists(hash_file):
    with open(hash_file, 'r') as f:
        previous_hash = imagehash.hex_to_hash(f.read().strip())
    
    # Compare hashes
    if current_hash != previous_hash:
        print(f"🚨 IMAGERY CHANGED! Previous: {previous_hash}, Current: {current_hash}")
        changed = True
        should_save = True
        
        # Save with timestamp for historical tracking
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        current_image.save(f'imagery_{timestamp}.jpg')
        print(f"✅ Saved new imagery as imagery_{timestamp}.jpg")
    else:
        print(f"✓ No change detected. Hash: {current_hash}")
        print(f"🗑️ Duplicate image not saved (identical to previous)")
        should_save = False
else:
    print(f"📸 First run. Storing initial hash: {current_hash}")
    should_save = True
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    current_image.save(f'imagery_{timestamp}.jpg')
    print(f"✅ Saved initial imagery as imagery_{timestamp}.jpg")

# Update hash file only if there was a change or first run
if should_save or not os.path.exists(hash_file):
    with open(hash_file, 'w') as f:
        f.write(str(current_hash))

# Set output for GitHub Actions
with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
    f.write(f"changed={'true' if changed else 'false'}\n")
    f.write(f"should_commit={'true' if should_save else 'false'}\n")