import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from api.services import get_cached_stations
from api.services.geocoder import geocode
from api.services.router import get_route
from api.services.proximity import get_stations_on_route
from api.services.optimizer import plan_fuel_stops, MPG


def build_map_geojson(route_feature: dict, start: str, end: str, fuel_stops: list) -> dict:
    """
    Combine the route line and every fuel stop into one GeoJSON FeatureCollection
    that can be pasted directly into https://geojson.io to see the route plus a
    labelled marker for each stop.
    """
    route_line = {
        "type": "Feature",
        "geometry": route_feature["geometry"],
        "properties": {"name": f"Route: {start} → {end}", "stroke": "#2563eb", "stroke-width": 4},
    }

    features = [route_line]
    for i, s in enumerate(fuel_stops, start=1):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
            "properties": {
                "name": f"Stop {i}: {s['station_name']}",
                "marker-color": "#16a34a",
                "city": s["city"],
                "state": s["state"],
                "mile_marker": s["mile_marker"],
                "price_per_gallon": s["price_per_gallon"],
                "gallons_purchased": s["gallons_purchased"],
                "cost_usd": s["cost_usd"],
            },
        })

    return {"type": "FeatureCollection", "features": features}


class RouteView(APIView):

    def post(self, request):
        start = request.data.get('start', '').strip()
        end = request.data.get('end', '').strip()

        if not start or not end:
            return Response(
                {"error": "'start' and 'end' fields are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        t0 = time.time()

        try:
            # 1. Geocode start/end (2 Nominatim calls, cached after first hit)
            start_lat, start_lng = geocode(start)
            end_lat, end_lng = geocode(end)

            # 2. Get route — 1 OSRM call, cached
            route = get_route(start_lat, start_lng, end_lat, end_lng)

            # 3. Filter stations near route — in-memory, no I/O
            stations = get_cached_stations()
            stations_on_route = get_stations_on_route(stations, route['coordinates'])

            # 4. Optimal fuel plan
            fuel_stops, total_cost = plan_fuel_stops(stations_on_route, route['distance_miles'])

            total_gallons = round(route['distance_miles'] / MPG, 2)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        map_geojson = build_map_geojson(route['geojson'], start, end, fuel_stops)

        elapsed = round(time.time() - t0, 3)

        return Response({
            "meta": {
                "query_time_seconds": elapsed,
                "start": start,
                "end": end,
            },
            "route": {
                "distance_miles": route['distance_miles'],
                "geojson": route['geojson'],
                "map_geojson": map_geojson,
                "map_preview_hint": "Paste route.map_geojson into https://geojson.io to see the route AND every fuel stop"
            },
            "fuel_stops": fuel_stops,
            "summary": {
                "total_fuel_cost_usd": total_cost,
                "total_gallons_consumed": total_gallons,
                "number_of_stops": len(fuel_stops),
                "avg_price_per_gallon": round(total_cost / total_gallons, 3) if total_gallons else 0,
            }
        })
