"""Rebuild the public names-only county baseline from a pinned Census release.

No contacts, mailbox access, GIS boundaries, credentials, or private inputs.
Writes the generated JSON only with --write; otherwise prints it for review.
"""
import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

URL = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip'
PAGE = 'https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2025.html'
STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())


def build(raw, collected_on):
    if len(raw) > 2_000_000:
        raise ValueError('Unexpected archive size.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = [x for x in archive.infolist() if x.filename.lower().endswith('.txt')]
        if len(files) != 1 or files[0].file_size > 3_000_000:
            raise ValueError('Unexpected Census archive contents.')
        contents = archive.read(files[0]).decode('utf-8-sig')
    delimiter = '|' if '|' in contents.splitlines()[0] else '\t'
    rows = csv.DictReader(io.StringIO(contents), delimiter=delimiter)
    counties = sorted([{'id': 'county:' + r['GEOID'].strip(), 'fips': r['GEOID'].strip(),
                        'state': r['USPS'].strip(), 'name': r['NAME'].strip()}
                       for r in rows if r['USPS'].strip() in STATES], key=lambda x: x['id'])
    if len(counties) != 3144 or len({x['id'] for x in counties}) != len(counties):
        raise ValueError('County count changed; review the source before updating this pinned release.')
    if {x['state'] for x in counties} != STATES or sum(x['state'] == 'MI' for x in counties) != 83:
        raise ValueError('Unexpected state coverage.')
    return {'schema_version': 1, 'vintage': 2025, 'source_authority': 'U.S. Census Bureau',
            'source_url': URL, 'source_page': PAGE, 'collected_on': collected_on,
            'archive_sha256': hashlib.sha256(raw).hexdigest(), 'count': len(counties),
            'scope': '50 states and DC; county equivalents included. Puerto Rico and other territories excluded.',
            'caveat': 'A geographic inventory, not a list of county governments or records custodians. Some equivalents have no county government; verify the actual authority. This is not a historical election-jurisdiction crosswalk.',
            'counties': counties}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    with urllib.request.urlopen(URL, timeout=45) as response:
        raw = response.read(2_000_001)
    result = build(raw, date.today().isoformat())
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.write:
        (Path(__file__).resolve().parents[1] / 'app' / 'counties.json').write_text(output, encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k != 'counties'}))
    else:
        print(output, end='')
