"""Build a names/paths-only county navigation map from the pinned Census KML.

Maintainer-only public download; standard library only, no live app/mail access.
Never includes KML descriptions, executable markup, contacts or request data.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www2.census.gov/geo/tiger/GENZ2025/kml/cb_2025_us_county_20m.zip'
PAGE = 'https://www.census.gov/geographies/mapping-files/2025/geo/carto-boundary-file.html'
MEMBER = 'cb_2025_us_county_20m.kml'


def build(raw, inventory, collected_on):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info = archive.getinfo(MEMBER)
        if info.file_size > 20_000_000:
            raise ValueError('Unexpected KML size.')
        xml = archive.read(MEMBER)
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
        raise ValueError('KML declarations are not supported.')
    counties = {c['fips']: c for c in inventory['counties']}
    shapes = {}
    for item in ET.fromstring(xml).iterfind('.//{*}Placemark'):
        fields = {x.get('name'): x.text for x in item.iterfind('.//{*}SimpleData')}
        code = fields.get('GEOID')
        if code not in counties:
            continue  # Territories are outside the existing directory scope.
        c = counties[code]
        if fields.get('STUSPS') != c['state'] or fields.get('NAMELSAD') != c['name'] or code in shapes:
            raise ValueError('County identity mismatch or duplicate: ' + str(code))
        rings = []
        for coords in item.iterfind('.//{*}Polygon//{*}LinearRing/{*}coordinates'):
            ring = []
            for token in (coords.text or '').split():
                lon, lat = [float(n) for n in token.split(',')[:2]]
                if not math.isfinite(lon + lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ValueError('Invalid coordinates.')
                # Keep the Aleutian islands contiguous across the antimeridian.
                ring.append([lon - 360 if c['state'] == 'AK' and lon > 0 else lon, lat])
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('Expected closed polygon rings.')
            rings.append(ring)
        if not rings:
            raise ValueError('County has no polygon: ' + code)
        shapes[code] = rings
    states = {}
    for state in sorted({c['state'] for c in counties.values()}):
        rows = [c for c in counties.values() if c['state'] == state]
        points = [p for c in rows for ring in shapes.get(c['fips'], []) for p in ring]
        if not points:
            raise ValueError('State has no geometry: ' + state)
        mid_lat = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
        ratio = math.cos(math.radians(mid_lat))
        left, right = min(p[0] for p in points) * ratio, max(p[0] for p in points) * ratio
        top, bottom = -max(p[1] for p in points), -min(p[1] for p in points)
        scale = min(852 / (right - left), 552 / (bottom - top))
        dx, dy = (900 - (right - left) * scale) / 2, (600 - (bottom - top) * scale) / 2
        mapped = []
        for c in rows:
            parts = []
            for ring in shapes.get(c['fips'], []):
                p = [(round((lon * ratio - left) * scale + dx, 2), round((-lat - top) * scale + dy, 2)) for lon, lat in ring]
                parts.append('M' + 'L'.join(f'{x:g},{y:g}' for x, y in p) + 'Z')
            mapped.append({'id': c['id'], 'name': c['name'], 'path': ''.join(parts)})
        states[state] = mapped
    missing = sorted('county:' + code for code in set(counties) - set(shapes))
    if len(counties) != 3144 or len(states) != 51 or len(missing) > 15:
        raise ValueError('Unexpected inventory coverage; review the source before writing.')
    return {'schema_version': 1, 'source_authority': 'U.S. Census Bureau', 'source_url': URL,
            'source_page': PAGE, 'vintage': 2025, 'scale': '1:20,000,000', 'collected_on': collected_on,
            'archive_sha256': hashlib.sha256(raw).hexdigest(), 'count': len(counties),
            'geometry_count': len(shapes), 'missing_geometry': missing, 'view_box': '0 0 900 600',
            'projection': 'State-fitted equirectangular; longitude scaled at each state midpoint latitude. Alaska longitudes unwrapped.',
            'caveat': 'Simplified county/equivalent navigation shapes, not legal or election boundaries. Some equivalents have no county government. All inventory entries remain in the list even if their shape is unavailable.',
            'states': states}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    with urllib.request.urlopen(URL, timeout=45) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError('Unexpected archive size.')
    inventory = json.loads((ROOT / 'app/counties.json').read_text(encoding='utf-8'))
    value = build(raw, inventory, datetime.now(timezone.utc).date().isoformat())
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n'
    if len(encoded.encode('utf-8')) > 2_000_000:
        raise ValueError('Generated asset exceeds publication size budget.')
    if args.write:
        (ROOT / 'app/static/county-map.json').write_text(encoded, encoding='utf-8')
        print(json.dumps({k: v for k, v in value.items() if k != 'states'}))
    else:
        print(encoded, end='')
