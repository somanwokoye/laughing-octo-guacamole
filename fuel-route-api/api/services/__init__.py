from django.conf import settings

# When TLS verification is disabled (corporate TLS-inspection proxy), silence the
# noisy per-request urllib3 InsecureRequestWarning exactly once.
if not getattr(settings, 'EXTERNAL_SSL_VERIFY', True):
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_STATIONS_CACHE = []


def get_cached_stations():
    return _STATIONS_CACHE


def warm_station_cache():
    from api.models import FuelStation
    global _STATIONS_CACHE
    _STATIONS_CACHE = list(
        FuelStation.objects.values(
            'name', 'address', 'city', 'state', 'lat', 'lng', 'price_per_gallon'
        )
    )
    print(f"[Cache] Warmed {len(_STATIONS_CACHE)} fuel stations into memory.")
