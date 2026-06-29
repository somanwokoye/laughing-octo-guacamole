import requests
from django.conf import settings
from django.core.cache import cache

OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


def get_route(start_lat, start_lng, end_lat, end_lng) -> dict:
    """
    Single OSRM call. Returns:
      {
        distance_miles: float,
        geojson: dict (GeoJSON Feature),
        coordinates: [[lng, lat], ...]   ← for proximity math
      }
    Cached by coordinate pair for 1 hour.
    """
    cache_key = f"route:{start_lat:.4f},{start_lng:.4f}:{end_lat:.4f},{end_lng:.4f}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = f"{OSRM_URL}/{start_lng},{start_lat};{end_lng},{end_lat}"
    resp = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson"},
        timeout=15,
        verify=settings.EXTERNAL_SSL_VERIFY,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "Ok":
        raise ValueError(f"OSRM error: {data.get('message', 'Unknown error')}")

    leg = data["routes"][0]
    distance_miles = leg["distance"] / 1609.34
    coords = leg["geometry"]["coordinates"]  # list of [lng, lat]

    result = {
        "distance_miles": round(distance_miles, 2),
        "geojson": {
            "type": "Feature",
            "geometry": leg["geometry"],
            "properties": {}
        },
        "coordinates": coords,
    }

    cache.set(cache_key, result, timeout=3600)
    return result
