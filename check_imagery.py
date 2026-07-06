import os
import re
import sys
import glob
import math
from datetime import datetime, timezone

# The status messages below use emoji; make sure stdout can encode them even on
# a legacy Windows console (GitHub's Linux runners are already UTF-8).
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

# ---- Configuration ----
LOCATION_LABEL = "35°09'55.3\"N 106°44'46.4\"W"
HASH_FILE = 'last_image.txt'


def deg2tile(lat, lon, zoom):
    """Convert latitude/longitude to slippy-map tile coordinates."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)


def download_tile(zoom, x, y):
    """Download a single Esri World Imagery tile. Returns a PIL image or None."""
    import requests
    from PIL import Image
    from io import BytesIO

    url = (
        "https://services.arcgisonline.com/arcgis/rest/services/"
        f"World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
    )
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"⚠️ Failed to download tile {x},{y}: {e}")
        return None


def stitch_tiles(lat, lon, zoom, tiles_across=3):
    """Download and stitch a grid of tiles. Returns (image, failed_count)."""
    from PIL import Image

    center_x, center_y = deg2tile(lat, lon, zoom)
    half = tiles_across // 2
    tile_size = 256
    stitched = Image.new('RGB', (tiles_across * tile_size, tiles_across * tile_size))
    failed = 0

    print(f"\U0001f4e5 Downloading {tiles_across}x{tiles_across} tile grid...")
    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            x = center_x + dx
            y = center_y + dy
            img = download_tile(zoom, x, y)
            if img:
                stitched.paste(img, ((dx + half) * tile_size, (dy + half) * tile_size))
                print(f"  ✓ Tile ({x},{y}) downloaded")
            else:
                failed += 1
                print(f"  ✗ Tile ({x},{y}) failed")
    return stitched, failed


# ---- README generation -------------------------------------------------------

def _parse_timestamp(filename):
    """Extract the UTC datetime encoded in an imagery_YYYYMMDD_HHMMSS.jpg name."""
    m = re.search(r'imagery_(\d{8})_(\d{6})\.jpg$', filename)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M%S')
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fmt(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def list_captures():
    """Return [(datetime, filename), ...] for every imagery_*.jpg, newest first."""
    items = []
    for path in glob.glob('imagery_*.jpg'):
        name = os.path.basename(path)
        ts = _parse_timestamp(name)
        if ts:
            items.append((ts, name))
    items.sort(key=lambda pair: pair[0], reverse=True)
    return items


def generate_readme():
    """Rebuild README.md from the imagery files on disk.

    Shows the newest capture and the previous capture side by side with their
    dates, followed by a collapsible full history. The output is a pure function
    of the imagery files present, so it only changes when a new capture is added
    - keeping git history meaningful (no churn on 'no change' runs).
    """
    captures = list_captures()
    lines = [
        '# \U0001f6f0️ Satellite Imagery Monitor',
        '',
        'Automated weekly monitoring of satellite imagery for a *Pluribus* filming site.  ',
        f'Location: **{LOCATION_LABEL}**',
        '',
    ]

    if not captures:
        lines += ['_No imagery captured yet._', '']
    else:
        newest_t, newest_f = captures[0]
        lines += ['## Newest change vs. previous', '']
        if len(captures) >= 2:
            prev_t, prev_f = captures[1]
            lines += [
                f'| \U0001f195 Newest — {_fmt(newest_t)} | \U0001f552 Previous — {_fmt(prev_t)} |',
                '|:---:|:---:|',
                f'| ![Newest]({newest_f}) | ![Previous]({prev_f}) |',
                '',
            ]
        else:
            lines += [
                f'| \U0001f195 Newest — {_fmt(newest_t)} |',
                '|:---:|',
                f'| ![Newest]({newest_f}) |',
                '',
            ]
        lines += [
            '---',
            '',
            '## History',
            '',
            '<details>',
            '<summary>All captures (newest first)</summary>',
            '',
        ]
        for ts, name in captures:
            lines.append(f'- **{_fmt(ts)}** — [`{name}`]({name})')
        lines += ['', '</details>', '']

    with open('README.md', 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))

    newest_name = captures[0][1] if captures else 'none'
    print(f"\U0001f4dd README rebuilt — {len(captures)} capture(s), newest: {newest_name}")


# ---- Output helper -----------------------------------------------------------

def _write_output(changed, should_commit):
    out = os.environ.get('GITHUB_OUTPUT')
    if not out:
        return
    with open(out, 'a') as f:
        f.write(f"changed={'true' if changed else 'false'}\n")
        f.write(f"should_commit={'true' if should_commit else 'false'}\n")


# ---- Main --------------------------------------------------------------------

def main():
    # README-only mode: rebuild the README from existing files and exit. Handy
    # for local previews and needs none of the heavy imaging dependencies.
    if os.environ.get('README_ONLY', '').lower() == 'true':
        generate_readme()
        return

    import imagehash

    lat = float(os.environ['LATITUDE'])
    lon = float(os.environ['LONGITUDE'])
    zoom = int(os.environ.get('ZOOM_LEVEL', '17'))
    tiles_across = int(os.environ.get('TILES_ACROSS', '3'))
    force = os.environ.get('FORCE_CAPTURE', 'false').lower() == 'true'

    print(f"\U0001f4cd Monitoring location: {lat}, {lon}")
    print(f"\U0001f50d Zoom level: {zoom}")
    print(f"\U0001f4d0 Grid: {tiles_across}x{tiles_across} tiles "
          f"({tiles_across * 256}x{tiles_across * 256}px)")
    if force:
        print("⚙️ FORCE_CAPTURE enabled — a fresh capture will be saved regardless of change.")

    current_image, failed = stitch_tiles(lat, lon, zoom, tiles_across)

    # If any tile failed, the stitched image has black gaps that would corrupt
    # the hash and trigger a false "changed" alert. Bail out without saving.
    if failed:
        print(f"⚠️ {failed} tile(s) failed — skipping change detection this run to avoid a false alarm.")
        generate_readme()
        _write_output(changed=False, should_commit=False)
        return

    current_hash = imagehash.average_hash(current_image)

    previous_hash = None
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE) as f:
            raw = f.read().strip()
        if raw:
            previous_hash = imagehash.hex_to_hash(raw)

    first_run = previous_hash is None
    changed = (not first_run) and (current_hash != previous_hash)
    should_save = first_run or changed or force

    if changed:
        print(f"\U0001f6a8 IMAGERY CHANGED! Previous: {previous_hash}, Current: {current_hash}")
    elif first_run:
        print(f"\U0001f4f8 First run. Initial hash: {current_hash}")
    elif force:
        print(f"⚙️ No change (hash {current_hash}) — saving anyway because FORCE_CAPTURE is on.")
    else:
        print(f"✓ No change detected. Hash: {current_hash}")

    if should_save:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        outfile = f'imagery_{timestamp}.jpg'
        current_image.save(outfile, quality=95)
        print(f"✅ Saved {outfile}")
        with open(HASH_FILE, 'w') as f:
            f.write(str(current_hash))

    # README always reflects the current set of captures on disk. When nothing
    # was saved this collapses to an identical file, so git sees no change.
    generate_readme()

    _write_output(changed=changed, should_commit=should_save)


if __name__ == '__main__':
    main()
