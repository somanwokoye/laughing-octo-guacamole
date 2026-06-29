import math
from collections import defaultdict

MILES_PER_DEGREE_LAT = 69.0
OFF_ROUTE_THRESHOLD_MILES = 15.0

# Grid cell size in degrees, sized to the off-route threshold so a station only
# ever needs to look at its own cell + the 8 neighbours to find every route
# segment that could possibly be within range.
_CELL_DEG = OFF_ROUTE_THRESHOLD_MILES / MILES_PER_DEGREE_LAT  # ≈ 0.217°


def haversine(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance in miles."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _point_to_segment_t(px, py, ax, ay, bx, by) -> float:
    """Parameter t (0–1) of the nearest point on segment AB to point P."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return 0.0
    return max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))


def _cell(lat: float, lng: float) -> tuple[int, int]:
    return (int(math.floor(lat / _CELL_DEG)), int(math.floor(lng / _CELL_DEG)))


def get_stations_on_route(stations: list, route_coords: list) -> list:
    """
    For each station, find whether it lies within OFF_ROUTE_THRESHOLD_MILES of the
    route and, if so, attach its 'mile_marker' (distance along the route) and
    'dist_from_route'. Results are sorted by mile_marker.

    route_coords: list of [lng, lat] from OSRM GeoJSON geometry.

    Performance: a uniform spatial grid indexes every route segment into the cells
    its endpoints fall in. Each station then only tests the handful of segments in
    its own cell plus the 8 neighbouring cells, turning a national-scale route from
    O(stations × segments) into ~O(stations + segments). Because OSRM 'full'
    geometry is dense (segments far shorter than the 15-mile threshold), indexing by
    endpoint cells captures every segment that can be in range.
    """
    n = len(route_coords)
    if n < 2:
        return []

    # Cumulative mile markers at each route vertex.
    cumulative = [0.0] * n
    seg_len = [0.0] * (n - 1)
    for i in range(1, n):
        lng1, lat1 = route_coords[i - 1]
        lng2, lat2 = route_coords[i]
        d = haversine(lat1, lng1, lat2, lng2)
        seg_len[i - 1] = d
        cumulative[i] = cumulative[i - 1] + d

    # Index each segment (by its start index i) into the cells of both endpoints.
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i in range(n - 1):
        lng1, lat1 = route_coords[i]
        lng2, lat2 = route_coords[i + 1]
        c1 = _cell(lat1, lng1)
        grid[c1].append(i)
        c2 = _cell(lat2, lng2)
        if c2 != c1:
            grid[c2].append(i)

    result = []
    for station in stations:
        slat, slng = station['lat'], station['lng']
        cy, cx = _cell(slat, slng)

        # Gather candidate segments from the 3x3 block of cells around the station.
        candidates = set()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                bucket = grid.get((cy + dy, cx + dx))
                if bucket:
                    candidates.update(bucket)

        if not candidates:
            continue

        min_dist = float('inf')
        best_mile_marker = 0.0
        for i in candidates:
            lng1, lat1 = route_coords[i]
            lng2, lat2 = route_coords[i + 1]
            t = _point_to_segment_t(slng, slat, lng1, lat1, lng2, lat2)
            proj_lat = lat1 + t * (lat2 - lat1)
            proj_lng = lng1 + t * (lng2 - lng1)
            dist = haversine(slat, slng, proj_lat, proj_lng)
            if dist < min_dist:
                min_dist = dist
                best_mile_marker = cumulative[i] + t * seg_len[i]

        if min_dist <= OFF_ROUTE_THRESHOLD_MILES:
            result.append({
                **station,
                'mile_marker': round(best_mile_marker, 2),
                'dist_from_route': round(min_dist, 2),
            })

    return sorted(result, key=lambda s: s['mile_marker'])
