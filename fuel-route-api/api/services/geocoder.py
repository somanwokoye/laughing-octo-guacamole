import requests
from django.conf import settings
from django.core.cache import cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "FuelRouteAPI/1.0 (your@email.com)"}  # Required by Nominatim ToS


def geocode(location: str) -> tuple[float, float]:
    """
    Returns (lat, lng) for a US location string.
    Results are cached for 1 hour — repeated queries cost nothing.
    """
    cache_key = f"geocode:{location.lower().strip()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    resp = requests.get(
        NOMINATIM_URL,
        params={"q": location, "format": "json", "limit": 1, "countrycodes": "us"},
        headers=HEADERS,
        timeout=10,
        verify=settings.EXTERNAL_SSL_VERIFY,
    )
    resp.raise_for_status()
    results = resp.json()

    if not results:
        raise ValueError(f"Location not found: '{location}'")

    lat = float(results[0]['lat'])
    lng = float(results[0]['lon'])
    cache.set(cache_key, (lat, lng))
    return lat, lng
