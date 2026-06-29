# Fuel Route API

A Django REST API that takes a **US start and end location**, returns the driving **route**, the **cost-optimal fuel stops** along it, and the **total fuel cost** — assuming a 500-mile vehicle range and 10 miles per gallon.

**Stack:** Django 5.1 · Django REST Framework · OSRM (routing) · Nominatim (geocoding) · SQLite

---

## How it meets the brief

| Requirement | How it's handled |
|---|---|
| Inputs: US start & finish | `POST /api/v1/route/` with `{"start": "...", "end": "..."}` |
| Return the route map | `route.geojson` (route only) and `route.map_geojson` (route + stops) — paste into [geojson.io](https://geojson.io) |
| Cost-optimal fuel stops | Greedy-with-lookahead optimizer that buys cheap fuel early |
| 500-mile range → multiple stops | Tank modelled as 500 miles of range; plans as many stops as needed |
| Total money spent (10 MPG) | `summary.total_fuel_cost_usd` |
| Use the provided fuel-price file | `load_fuel_data` management command ingests the CSV |
| Free routing/map API | OSRM + Nominatim — no API key required |
| Latest stable Django | Django 5.1 |
| Fast responses | In-memory station cache + spatial grid + 1-hour result caching |
| Minimal routing-API calls | **Exactly one** OSRM call per request (plus 2 geocodes); all cached |

---

## Architecture

Per request, the hot path is:

1. **Geocode** start & end → 2 Nominatim calls (cached 1h).
2. **Route** → **1 OSRM call** returning full geometry + distance (cached 1h).
3. **Proximity filter** → stations within 15 miles of the route, using a spatial grid index (pure in-memory, no DB).
4. **Optimize** → greedy + lookahead fuel plan and total cost.

All ~6,700 stations are loaded into an **in-memory list at startup**, so steps 3–4 never touch the database.

```
fuel-route-api/
├── core/                     # Django project (settings, urls, wsgi)
├── api/
│   ├── models.py             # FuelStation
│   ├── views.py              # RouteView + GeoJSON builder
│   ├── urls.py
│   ├── services/
│   │   ├── __init__.py       # in-memory station cache
│   │   ├── geocoder.py       # Nominatim (request-time)
│   │   ├── router.py         # OSRM
│   │   ├── proximity.py      # grid-indexed haversine / mile-markers
│   │   └── optimizer.py      # greedy + lookahead
│   └── management/commands/
│       └── load_fuel_data.py # 3-tier geocoding loader
└── data/
    └── fuel-prices-for-be-assessment.csv
```

---

## Setup

```bash
cd fuel-route-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit SECRET_KEY
python manage.py migrate
```

## Load the fuel data

The CSV has no coordinates, so the loader geocodes every station via three tiers:
**US Census batch** → **offline GeoNames city dump** (downloaded once, ~68 MB) → **Nominatim** for the small remainder.

```bash
python manage.py load_fuel_data data/fuel-prices-for-be-assessment.csv
```

This loads ~6,700 stations in a few minutes. Use `--no-nominatim` to skip the final (slow, rate-limited) tier and stay fully offline.

## Run

```bash
python manage.py runserver
```

---

## API usage

### `POST /api/v1/route/`

Request:

```json
{ "start": "New York, NY", "end": "Los Angeles, CA" }
```

Response (truncated):

```json
{
  "meta": { "query_time_seconds": 1.0, "start": "New York, NY", "end": "Los Angeles, CA" },
  "route": {
    "distance_miles": 2798.19,
    "geojson": { "type": "Feature", "geometry": { "type": "LineString", "coordinates": [] } },
    "map_geojson": { "type": "FeatureCollection", "features": [] },
    "map_preview_hint": "Paste route.map_geojson into https://geojson.io to see the route AND every fuel stop"
  },
  "fuel_stops": [
    {
      "station_name": "SHEETZ #639", "city": "Youngstown", "state": "OH",
      "lat": 41.09978, "lng": -80.64952,
      "price_per_gallon": 3.059, "mile_marker": 394.4,
      "dist_from_route_miles": 3.66, "gallons_purchased": 6.93, "cost_usd": 21.2
    }
  ],
  "summary": {
    "total_fuel_cost_usd": 694.91,
    "total_gallons_consumed": 279.82,
    "number_of_stops": 17,
    "avg_price_per_gallon": 2.483
  }
}
```

| Status | Meaning |
|---|---|
| `200` | Success |
| `400` | Missing `start` / `end` |
| `422` | Route infeasible (no reachable station in a corridor) |
| `500` | Upstream/geocoding failure |

### Visualizing the map

Copy the `route.map_geojson` object from the response into [geojson.io](https://geojson.io) (or drag in a saved `.geojson` file). You'll see the route line plus a labelled marker for every fuel stop showing its price and cost.

---

## Design notes

- **Greedy + lookahead optimizer** — at each reachable station pick the cheapest; if a cheaper station is within range ahead, buy only enough to reach it, otherwise fill up; near the destination buy only what's needed. O(n log n) and near-optimal, versus the overkill of full dynamic programming.
- **Grid-indexed proximity** — OSRM `full` geometry can exceed 30,000 points. Indexing route segments into a uniform grid (sized to the 15-mile threshold) lets each station test only nearby segments, turning a coast-to-coast query from minutes into a fraction of a second.
- **Three-tier geocoding** — Census batch is precise but only matches street addresses; the offline GeoNames dump resolves the bulk of city/state combos instantly (~97%); Nominatim (1 req/sec) handles only the small residual. This cut the load from hours to minutes.
- **`EXTERNAL_SSL_VERIFY`** — defaults to `True`. Set `False` only behind a TLS-inspection proxy (e.g. Zscaler) whose re-signing CA is rejected by OpenSSL 3.x.
- **`avg_price_per_gallon`** is total cost ÷ *all* gallons consumed (including the free starting tank), so it reads below pump prices — it's a summary figure, not the average price paid.

## Possible improvements

- Move cache-warming off the app-startup DB query (removes a benign Django warning).
- Automated tests around the optimizer and proximity math.
- Cap/paginate the GeoJSON payload for very long routes.
