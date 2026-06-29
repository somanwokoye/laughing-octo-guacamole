# Fuel Route API — Backend Django Assessment

A Django REST API that takes a US start and end location and returns the driving route, the cost-optimal fuel stops along it (500-mile range, 10 MPG), and the total fuel cost.

The project lives in [`fuel-route-api/`](fuel-route-api/) — see its [README](fuel-route-api/README.md) for full setup, data-loading, and API documentation.

## Quick start

```bash
cd fuel-route-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit SECRET_KEY
python manage.py migrate
python manage.py load_fuel_data data/fuel-prices-for-be-assessment.csv
python manage.py runserver
```

Then `POST http://127.0.0.1:8000/api/v1/route/` with `{"start": "New York, NY", "end": "Los Angeles, CA"}`.

**Stack:** Django 5.1 · Django REST Framework · OSRM (routing) · Nominatim (geocoding) · SQLite
