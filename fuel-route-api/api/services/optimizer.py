MAX_RANGE_MILES = 500
MPG = 10


def plan_fuel_stops(stations_on_route: list, total_miles: float) -> tuple[list, float]:
    """
    Greedy lookahead algorithm:
    - Start with a full tank (500 miles of range)
    - At each decision point, pick the cheapest reachable station
    - If a cheaper station exists ahead (within full-tank range), buy only
      enough fuel to reach it rather than filling up now
    - Otherwise fill up completely

    Returns (stops, total_cost_usd)
    """
    tank_miles = MAX_RANGE_MILES   # 500 miles capacity
    current_mile = 0.0
    current_fuel = tank_miles      # start full
    stops = []
    visited = set()

    sorted_stations = sorted(stations_on_route, key=lambda s: s['mile_marker'])

    while current_fuel < (total_miles - current_mile) - 0.01:
        # All stations reachable from current position
        reachable = [
            s for s in sorted_stations
            if current_mile < s['mile_marker'] <= current_mile + current_fuel
            and s['mile_marker'] not in visited
        ]

        if not reachable:
            raise ValueError(
                f"Route infeasible: no fuel station reachable from mile "
                f"{current_mile:.0f} with {current_fuel:.0f} miles of range. "
                f"Check that fuel data covers this corridor."
            )

        # Pick cheapest reachable station
        best = min(reachable, key=lambda s: s['price_per_gallon'])
        visited.add(best['mile_marker'])

        # Drive to it
        miles_driven = best['mile_marker'] - current_mile
        current_fuel -= miles_driven
        current_mile = best['mile_marker']

        remaining_to_dest = total_miles - current_mile

        # Lookahead: is there a cheaper station within one full tank from here?
        cheaper_ahead = [
            s for s in sorted_stations
            if s['mile_marker'] > current_mile
            and s['mile_marker'] <= current_mile + tank_miles
            and s['price_per_gallon'] < best['price_per_gallon']
            and s['mile_marker'] not in visited
        ]

        if cheaper_ahead:
            # Buy only enough to reach nearest cheaper station plus a 10-mile buffer
            next_cheap = min(cheaper_ahead, key=lambda s: s['mile_marker'])
            needed_miles = next_cheap['mile_marker'] - current_mile + 10
            fuel_to_buy_miles = max(0.0, min(needed_miles - current_fuel, tank_miles - current_fuel))
        elif remaining_to_dest <= tank_miles:
            # Can reach destination — buy exactly what we need
            fuel_to_buy_miles = max(0.0, remaining_to_dest - current_fuel)
        else:
            # Fill up completely
            fuel_to_buy_miles = tank_miles - current_fuel

        gallons = fuel_to_buy_miles / MPG
        cost = gallons * best['price_per_gallon']
        current_fuel += fuel_to_buy_miles

        if gallons > 0.05:
            stops.append({
                'station_name': best.get('name', 'Unknown'),
                'address': best.get('address', ''),
                'city': best.get('city', ''),
                'state': best.get('state', ''),
                'lat': best['lat'],
                'lng': best['lng'],
                'price_per_gallon': round(best['price_per_gallon'], 3),
                'mile_marker': round(current_mile, 1),
                'dist_from_route_miles': best.get('dist_from_route', 0),
                'gallons_purchased': round(gallons, 2),
                'cost_usd': round(cost, 2),
            })

    total_cost = round(sum(s['cost_usd'] for s in stops), 2)
    return stops, total_cost
