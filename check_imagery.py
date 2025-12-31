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

def download_tile(zoom, x, y):
    """Download a single tile from Esri"""
    url = f"https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"⚠️ Failed to download tile {x},{y}: {e}")
        return None

def stitch_tiles(lat, lon, zoom, tiles_across=3):
    """Download and stitch multiple tiles together for higher resolution"""
    center_x, center_y = deg2tile(lat, lon, zoom)
    half = tiles_across // 2
    
    # Create blank canvas (each tile is 256x256)
    tile_size = 256
    stitched = Image.new('RGB', (tiles_across * tile_size, tiles_across * tile_size))
    
    print(f"📥 Downloading {tiles_across}x{tiles_across} tile grid...")
    
    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            x = center_x + dx
            y = center_y + dy
            
            img = download_tile(zoom, x, y)
            if img:
                paste_x = (dx + half) * tile_size
                paste_y = (dy + half) * tile_size
                stitched.paste(img, (paste_x, paste_y))
                print(f"  ✓ Tile ({x},{y}) downloaded")
            else:
                print(f"  ✗ Tile ({x},{y}) failed")
    
    return stitched

# Configuration
LAT = float(os.environ['LATITUDE'])
LON = float(os.environ['LONGITUDE'])
ZOOM = int(os.environ.get('ZOOM_LEVEL', '17'))
TILES_ACROSS = int(os.environ.get('TILES_ACROSS', '3'))

print(f"📍 Monitoring location: {LAT}, {LON}")
print(f"🔍 Zoom level: {ZOOM}")
print(f"📐 Grid size: {TILES_ACROSS}x{TILES_ACROSS} tiles ({TILES_ACROSS * 256}x{TILES_ACROSS * 256} pixels)")

# Download and stitch tiles
current_image = stitch_tiles(LAT, LON, ZOOM, TILES_ACROSS)

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
        current_image.save(f'imagery_{timestamp}.jpg', quality=95)
        print(f"✅ Saved new imagery as imagery_{timestamp}.jpg")
    else:
        print(f"✓ No change detected. Hash: {current_hash}")
        print(f"🗑️ Duplicate image not saved (identical to previous)")
        should_save = False
else:
    print(f"📸 First run. Storing initial hash: {current_hash}")
    should_save = True
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    current_image.save(f'imagery_{timestamp}.jpg', quality=95)
    print(f"✅ Saved initial imagery as imagery_{timestamp}.jpg")

# Update hash file only if there was a change or first run
if should_save or not os.path.exists(hash_file):
    with open(hash_file, 'w') as f:
        f.write(str(current_hash))

# Set output for GitHub Actions
with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
    f.write(f"changed={'true' if changed else 'false'}\n")
    f.write(f"should_commit={'true' if should_save else 'false'}\n")
