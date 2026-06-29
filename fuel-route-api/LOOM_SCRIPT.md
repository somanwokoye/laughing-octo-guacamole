# Loom Demo Script — Fuel Route API

> Target length: **5:00 max**. Narration is in quotes; `[SHOW: …]` cues tell you what to have on screen.
> The script is ~720 words, which lands just under 5 minutes at a natural pace with the on-screen pauses.

---

## Pre-record checklist (do this before hitting record)

- Server running: `cd fuel-route-api && .venv/bin/python manage.py runserver`
- Postman open with a saved `POST http://127.0.0.1:8000/api/v1/route/` request, body `{"start":"New York, NY","end":"Los Angeles, CA"}`
- A second tab ready with `{"start":"Chicago, IL","end":"Miami, FL"}`
- Editor open with these files in tabs: `optimizer.py`, `proximity.py`, `load_fuel_data.py`, `views.py`
- A browser tab on https://geojson.io, and `ny_to_la.geojson` handy to drag in
- **Fire the NY→LA request once before recording** so geocode/route are cached and the live demo is fast

---

## Script (~5:00)

### 0:00 – 0:30 — Intro & what it does

> "Hi, I'm Sochukwuma. This is my Backend Django Engineer assessment: a REST API that takes a US start and end location, returns the driving route, the cost-optimal fuel stops along it, and the total fuel cost. It's built on the latest stable Django 5.1 with Django REST Framework. Let me show it working first, then walk through the code."

`[SHOW: project folder structure in the editor sidebar for 2–3 seconds]`

### 0:30 – 1:50 — Live Postman demo (the money shot)

> "I'll hit the single endpoint, `POST /api/v1/route/`, with New York to Los Angeles."

`[SHOW: click Send in Postman]`

> "It comes back in about a second. Walking through the response: `meta` shows the query time. `route` gives the total distance — about 2,800 miles — plus the route geometry as GeoJSON. Then `fuel_stops`: the vehicle has a 500-mile range at 10 miles per gallon, so for a 2,800-mile trip it plans multiple stops — here 17 — each with the station name, location, price per gallon, how many gallons to buy there, and the cost."

`[SHOW: scroll through fuel_stops array]`

> "And `summary` gives the bottom line: total fuel cost of about $695, total gallons consumed, and number of stops. The key design choice is that the optimizer doesn't just stop at the nearest station — it buys cheap fuel early and only enough expensive fuel to reach the next cheaper one."

`[SHOW: highlight summary block]`

### 1:50 – 2:25 — Speed + map visualization

> "On performance: the assignment asked for speed and minimal external calls. Per request I make exactly three external calls — two geocodes for start and end, and a single routing call. Everything is cached, so a repeat is basically instant."

`[SHOW: click Send again on NY→LA — point at the faster query_time]`

> "The response also includes a GeoJSON FeatureCollection of the route plus every fuel stop. Pasting it into geojson.io, you can see the route line and a marker for each stop — clicking one shows its price and cost."

`[SHOW: drag ny_to_la.geojson onto geojson.io, click a green marker]`

### 2:25 – 2:55 — Architecture & the "free API" choice

> "Quick architecture: for the free routing API I used OSRM's public server — no API key, and one call returns the full route geometry and distance. For geocoding I used Nominatim, also free. On startup I load all ~6,700 fuel stations into an in-memory list, so the request hot path never touches the database — proximity filtering is pure in-memory math."

`[SHOW: views.py — the post() method, point at geocode → get_route → proximity → optimizer flow]`

### 2:55 – 3:40 — Code: the optimizer

> "Here's the core: the fuel optimizer. It's a greedy algorithm with lookahead. The tank is 500 miles of range, starting full. At each step I look at every station reachable on the current tank and pick the cheapest. Then the lookahead: if there's an even cheaper station within range ahead, I buy just enough to reach it; otherwise I fill up. Near the destination I buy only what's needed to finish. That's O(n log n) and near-optimal — explainable and fast, versus full dynamic programming which is overkill here."

`[SHOW: optimizer.py — point at the reachable list, the min() cheapest pick, and the cheaper_ahead lookahead block]`

### 3:40 – 4:10 — Code: proximity

> "To know which stations are 'on the route', proximity.py measures each station's distance to the route using haversine and point-to-segment math. The important part for speed: I index the route segments into a spatial grid, so each station only checks the handful of segments in its own grid cell instead of all of them. That turned a coast-to-coast query from minutes down to a fraction of a second."

`[SHOW: proximity.py — point at the grid build and the 3x3 cell lookup]`

### 4:10 – 4:45 — Code: the data load

> "One challenge: the provided fuel CSV has prices and addresses but no coordinates — and 8,000-plus rows. My load command geocodes them in three tiers: first the free US Census batch geocoder, then an offline GeoNames city dataset that resolves the vast majority instantly, and Nominatim only for the small remainder. That brought the load from hours down to a few minutes, and a continental-US bounding box filters out bad coordinates."

`[SHOW: load_fuel_data.py — scroll past the three tiers]`

### 4:45 – 5:00 — Wrap

> "So: latest Django, one routing call per request, sub-second cached responses, a cost-optimal multi-stop plan with total cost, and a map you can visualize. The code is on GitHub at the link I'm sharing. Thanks for watching!"

`[SHOW: GitHub repo page briefly]`

---

## Delivery tips

- **Practice once** — at 5:00 max, you want ~145 words/min. The script is ~720 words, which fits with the on-screen pauses.
- If you're running long, the trimmable section is **4:10–4:45 (data load)** — shorten to one sentence.
- Don't read robotically; the `[SHOW]` cues are where you naturally pause to point/scroll.

---

## How the requirements map to the demo

Tick each of these off as you go — they're exactly what the email asked for:

| Requirement (from the email) | Where it's covered |
|---|---|
| Inputs: US start & finish | 0:30 — Postman request body |
| Return route map | 0:30 + 1:50 — `route.geojson` / geojson.io |
| Optimal (cost-effective) fuel stops | 0:30 + 2:55 — `fuel_stops` + optimizer |
| 500-mile range, multiple fuel-ups | 0:30 — 17 stops for ~2,800 mi |
| Total money spent, 10 MPG | 0:30 — `summary.total_fuel_cost_usd` |
| Use the provided fuel-prices file | 4:10 — load command reads the CSV |
| Find a free map/routing API | 2:25 — OSRM + Nominatim, no API key |
| Latest stable Django | 0:00 — Django 5.1 |
| Return results quickly | 1:50 — sub-second cached response |
| Minimal calls to the routing API | 2:25 — exactly 1 OSRM call per request |
| Postman demo + code overview | whole video |

---

## Q&A prep — be ready to explain these in follow-up

**"How many times do you call the routing API?"**
Exactly **one** OSRM call per request — it returns the full geometry and distance in a single response. Start/end geocoding is two separate Nominatim calls. All three are cached for an hour, so repeated queries cost zero external calls. That meets the "one call ideal, two-three acceptable" requirement.

**"The CSV has no latitude/longitude — how did you handle it?"**
The OPIS data only has address strings, and many are highway-exit descriptions that don't geocode as street addresses. I use a three-tier strategy: (1) the free US Census **batch** geocoder for precise hits, (2) an **offline GeoNames** US city dataset to resolve the bulk instantly by city+state, and (3) **Nominatim** only for the small residual. City-level precision is fine because stations more than 15 miles off-route are filtered out anyway.

**"Why was the offline dataset worth it?"**
Nominatim's usage policy is 1 request/second. Geocoding ~3,900 unique cities sequentially would take 2–4 hours. The offline GeoNames lookup resolves them in seconds with ~97% coverage, so the load dropped from hours to a few minutes — and it's a one-time load anyway.

**"Why OSRM and Nominatim?"**
Both are completely free with no API key. OSRM returns the full route geometry plus distance in one call, which keeps the external-call count minimal.

**"Why load stations into memory?"**
Hitting the database for ~6,700 rows on every request is slow. I warm an in-memory list once at startup, so proximity filtering on the hot path is pure arithmetic with no I/O.

**"How is proximity fast for a coast-to-coast route?"**
The OSRM `full` geometry can be 30,000+ points. A naive distance check is O(stations × segments) — minutes for a national route. I index route segments into a uniform spatial grid sized to the 15-mile threshold, so each station only tests the segments in its own cell plus the 8 neighbours. That makes it roughly O(stations + segments) — a fraction of a second.

**"Why greedy with lookahead and not dynamic programming?"**
Greedy + lookahead is O(n log n), near-optimal, and easy to reason about live. It buys cheap fuel early and only enough expensive fuel to reach the next cheaper station. A full DP is provably optimal but overkill for this size and harder to defend on the spot.

**"Why does `avg_price_per_gallon` look lower than pump prices?"**
It's total cost divided by **all** gallons consumed over the trip — including the free starting tank — so it reads below the stations' actual prices. It's a summary metric, not a literal average of the prices paid. Easy to change to cost ÷ gallons *purchased* if a true paid-average is preferred.

**"What about an SSL / corporate-proxy note?"**
On a machine behind a TLS-inspection proxy (e.g. Zscaler), OpenSSL 3.x rejects the re-signed certificate. I added an `EXTERNAL_SSL_VERIFY` setting that defaults to `True` (secure) and can be set to `False` only in that environment — so the code stays secure by default and still runs behind such proxies.

**"What would you improve with more time?"**
Move cache-warming off the app-startup DB query (it currently triggers a benign Django warning), add automated tests around the optimizer and proximity, optionally cache the proximity grid per route, and add pagination/limits to the response payload size.
