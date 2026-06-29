import csv
import io
import os
import re
import time
import zipfile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from api.models import FuelStation

# Outbound TLS verification (False behind a TLS-inspection proxy; see settings).
_VERIFY = getattr(settings, 'EXTERNAL_SSL_VERIFY', True)
if not _VERIFY:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#  Census Batch Geocoder (Tier 1)
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
CENSUS_BENCHMARK = "Public_AR_Current"
CENSUS_BATCH_SIZE = 9_000   # API max is 10k; leave headroom

#  Offline GeoNames city dump (Tier 2)
GEONAMES_URL = "https://download.geonames.org/export/dump/US.zip"
GEONAMES_ZIP = "US.zip"
GEONAMES_MEMBER = "US.txt"

#  Nominatim (Tier 3, residual only)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "FuelRouteAPI/1.0 (your@email.com)"}
#


def _norm(s: str) -> str:
    """Normalise a place name for fuzzy matching: lowercase, drop punctuation/spaces."""
    s = s.strip().lower().replace('&', 'and').replace('saint ', 'st ')
    return re.sub(r'[^a-z0-9]', '', s)


def batch_geocode_census(rows: list[dict]) -> dict[str, tuple[float, float]]:
    """
    Send a batch of rows to the Census geocoder.
    Returns { opis_id_str: (lat, lng) } for matched records.

    Census output coords field is "longitude,latitude".
    """
    results = {}

    buf = io.StringIO()
    for row in rows:
        opis_id = row['OPIS Truckstop ID']
        address = row['Address'].replace(',', ' ')
        city = row['City'].replace(',', ' ')
        state = row['State']
        buf.write(f'{opis_id},"{address}","{city}",{state},\n')

    payload = buf.getvalue().encode('utf-8')

    try:
        resp = requests.post(
            CENSUS_URL,
            data={"benchmark": CENSUS_BENCHMARK},
            files={"addressFile": ("addresses.csv", payload, "text/csv")},
            timeout=120,
            verify=_VERIFY,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [Census] Request failed: {e}")
        return results

    reader = csv.reader(io.StringIO(resp.text))
    for parts in reader:
        if len(parts) < 6:
            continue
        opis_id_str = parts[0].strip()
        match_status = parts[2].strip()
        coords_field = parts[5].strip()
        if match_status == "Match" and coords_field:
            try:
                lng_str, lat_str = coords_field.split(",")
                results[opis_id_str] = (float(lat_str), float(lng_str))
            except ValueError:
                pass

    return results


def build_offline_city_map(data_dir: str, stdout) -> dict[tuple[str, str], tuple[float, float]]:
    """
    Build a { (normalised_city, state): (lat, lng) } lookup from the free GeoNames
    US populated-places dump. Downloads the zip once if missing and streams the
    member file straight out of the archive (no 293 MB extraction on disk).

    For duplicate (city, state) names we keep the most populous match.
    """
    zip_path = os.path.join(data_dir, GEONAMES_ZIP)
    if not os.path.exists(zip_path):
        stdout.write(f"  Downloading GeoNames US dump (~68 MB) -> {zip_path} ...")
        resp = requests.get(GEONAMES_URL, stream=True, timeout=300, verify=_VERIFY)
        resp.raise_for_status()
        with open(zip_path, 'wb') as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        stdout.write("  Download complete.")

    city_map: dict[tuple[str, str], tuple[float, float]] = {}
    pop_map: dict[tuple[str, str], int] = {}

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(GEONAMES_MEMBER) as raw:
            for bline in raw:
                p = bline.decode('utf-8').rstrip('\n').split('\t')
                if len(p) < 15 or p[6] != 'P':   # feature class 'P' = populated place
                    continue
                state = p[10].strip()
                try:
                    lat = float(p[4])
                    lng = float(p[5])
                    pop = int(p[14] or 0)
                except ValueError:
                    continue
                for raw_name in {p[1], p[2]}:     # name + asciiname
                    nm = _norm(raw_name)
                    if not nm:
                        continue
                    key = (nm, state)
                    if key not in pop_map or pop > pop_map[key]:
                        pop_map[key] = pop
                        city_map[key] = (lat, lng)

    return city_map


def geocode_city_state(city: str, state: str) -> tuple[float, float] | None:
    """Nominatim city-level fallback. Sleeps 1.1s to respect the 1 req/sec ToS."""
    time.sleep(1.1)
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": f"{city}, {state}, USA", "format": "json", "limit": 1, "countrycodes": "us"},
            headers=NOMINATIM_HEADERS,
            timeout=10,
            verify=_VERIFY,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = 'Load fuel station data from CSV, geocoding via Census → offline GeoNames → Nominatim.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)
        parser.add_argument(
            '--no-nominatim',
            action='store_true',
            help='Skip the Nominatim residual tier (fully offline after Census).',
        )

    def handle(self, *args, **options):
        data_dir = os.path.dirname(os.path.abspath(options['csv_path']))

        self.stdout.write("Reading CSV...")
        rows = []
        with open(options['csv_path'], encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                rows.append(row)
        self.stdout.write(f"  {len(rows)} stations loaded from CSV.")

        #  Tier 1: Census batch geocoding
        self.stdout.write("\nStep 1/4 — Census batch geocoding...")
        coord_map: dict[str, tuple[float, float]] = {}
        for i in range(0, len(rows), CENSUS_BATCH_SIZE):
            batch = rows[i: i + CENSUS_BATCH_SIZE]
            self.stdout.write(f"  Sending batch {i}–{i + len(batch)}...")
            matched = batch_geocode_census(batch)
            coord_map.update(matched)
            self.stdout.write(f"  Matched {len(matched)}/{len(batch)} in this batch.")
        census_hits = len(coord_map)
        self.stdout.write(f"Census total: {census_hits}/{len(rows)} matched.")

        #  Tier 2: Offline GeoNames city map
        self.stdout.write("\nStep 2/4 — Building offline GeoNames city map...")
        city_map = build_offline_city_map(data_dir, self.stdout)
        self.stdout.write(f"  Offline map ready: {len(city_map)} (city, state) entries.")

        unmatched = [r for r in rows if str(r['OPIS Truckstop ID']) not in coord_map]
        still_unmatched = []
        offline_hits = 0
        for row in unmatched:
            coords = city_map.get((_norm(row['City']), row['State'].strip()))
            if coords:
                coord_map[str(row['OPIS Truckstop ID'])] = coords
                offline_hits += 1
            else:
                still_unmatched.append(row)
        self.stdout.write(f"  Offline resolved {offline_hits} stations. {len(still_unmatched)} remain.")

        #  Tier 3: Nominatim residual (tiny)
        nominatim_hits = 0
        if options['no_nominatim']:
            self.stdout.write("\nStep 3/4 — Skipping Nominatim (--no-nominatim).")
        else:
            residual_cities = sorted({(r['City'].strip(), r['State'].strip()) for r in still_unmatched})
            self.stdout.write(
                f"\nStep 3/4 — Nominatim residual for {len(residual_cities)} unique cities "
                f"(~{len(residual_cities) * 1.1:.0f}s)..."
            )
            nom_cache: dict[tuple, tuple[float, float] | None] = {}
            for city, state in residual_cities:
                nom_cache[(city, state)] = geocode_city_state(city, state)
            for row in still_unmatched:
                coords = nom_cache.get((row['City'].strip(), row['State'].strip()))
                if coords:
                    coord_map[str(row['OPIS Truckstop ID'])] = coords
                    nominatim_hits += 1
            self.stdout.write(f"  Nominatim resolved an additional {nominatim_hits} stations.")

        #  Step 4: Bulk insert into DB
        self.stdout.write("\nStep 4/4 — Writing to database...")
        FuelStation.objects.all().delete()

        stations = []
        skipped = 0
        seen_ids = set()

        for row in rows:
            opis_id = str(row['OPIS Truckstop ID'])

            # CSV contains duplicate OPIS IDs (e.g. renamed stations);
            # keep the first occurrence to honour the unique constraint.
            if opis_id in seen_ids:
                continue

            coords = coord_map.get(opis_id)
            if not coords:
                skipped += 1
                continue

            lat, lng = coords

            # Continental USA bounding box sanity check (drops Canada / bad coords)
            if not (24.0 < lat < 49.5 and -125.0 < lng < -66.0):
                skipped += 1
                continue

            try:
                price = float(row['Retail Price'])
            except (ValueError, KeyError):
                skipped += 1
                continue

            seen_ids.add(opis_id)
            stations.append(FuelStation(
                opis_id=int(row['OPIS Truckstop ID']),
                name=row['Truckstop Name'].strip(),
                address=row['Address'].strip(),
                city=row['City'].strip(),
                state=row['State'].strip(),
                lat=lat,
                lng=lng,
                price_per_gallon=price,
            ))

        FuelStation.objects.bulk_create(stations, batch_size=500)
        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Loaded {len(stations)} stations '
            f'(Census {census_hits}, offline {offline_hits}, Nominatim {nominatim_hits}). '
            f'Skipped {skipped} (no coords or out of bounds).'
        ))
