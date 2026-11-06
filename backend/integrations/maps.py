"""Read-only map tools for agents with the `maps` mechanism: place search and routes for training runs.

Uses free, keyless OpenStreetMap-based services (all public data, nothing is written anywhere):
- Nominatim (NOMINATIM_URL) for geocoding and place search. Its usage policy requires an
  identifying User-Agent (MAPS_USER_AGENT) and at most 1 request/second, so every Nominatim call
  goes through a module-level throttle.
- OSRM on routing.openstreetmap.de (OSRM_URL), which hosts one server per profile:
  /routed-foot, /routed-bike, /routed-car. The path segment after /v1/ is always `driving`.
- Open-Meteo elevation (ELEVATION_URL), up to 100 points per call.

Privacy: user-supplied places and coordinates are never logged, cached or stored.
Results are kept short (<~1500 chars) for Groq's free-tier tokens-per-minute cap.
CLI: `uv run python -m backend.integrations.maps places "park" --near "Indiranagar, Bengaluru"`
     `uv run python -m backend.integrations.maps route "Cubbon Park, Bengaluru" "Lalbagh, Bengaluru" running`
"""

import re
import sys
import threading
import time
from collections.abc import Callable

import httpx

from backend import config

MAX_PLACES = 10
NEAR_BOX_DEG = 0.05  # ~5 km around the `near` place
ELEVATION_SAMPLES = 50
WAYPOINTS = 6
RUN_PACE_MIN_PER_KM = 6.0

# mode -> OSRM profile (routing.openstreetmap.de server name)
MODES = {
    "walking": "foot", "walk": "foot", "running": "foot", "run": "foot", "foot": "foot",
    "hiking": "foot", "jogging": "foot",
    "cycling": "bike", "bike": "bike", "bicycle": "bike", "biking": "bike",
    "driving": "car", "car": "car", "drive": "car",
}

_LATLON = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")

_nominatim_lock = threading.Lock()
_nominatim_last = 0.0


def _get(url: str, params: dict | None = None) -> dict | list:
    try:
        resp = httpx.get(
            url, params=params, headers={"User-Agent": config.MAPS_USER_AGENT}, timeout=config.MAPS_TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Map service unavailable: HTTP {e.response.status_code}") from None
    except (httpx.HTTPError, ValueError) as e:
        raise RuntimeError(f"Map service unavailable: {type(e).__name__}") from None


def _nominatim(**params) -> list[dict]:
    """Nominatim /search, throttled to 1 request/second across threads (usage policy)."""
    global _nominatim_last
    with _nominatim_lock:
        wait = 1.0 - (time.monotonic() - _nominatim_last)
        if wait > 0:
            time.sleep(wait)
        try:
            return _get(f"{config.NOMINATIM_URL}/search", {"format": "jsonv2", **params})
        finally:
            _nominatim_last = time.monotonic()


def _geocode(place: str) -> tuple[float, float, str]:
    """'lat,lon' or a place name -> (lat, lon, display name)."""
    if m := _LATLON.match(place):
        lat, lon = float(m[1]), float(m[2])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"'{place}' is not a valid 'lat,lon'.")
        return lat, lon, f"{lat:.5f},{lon:.5f}"
    if not place.strip():
        raise ValueError("Empty place name. Give a place name or 'lat,lon'.")
    found = _nominatim(q=place, limit=1)
    if not found:
        raise ValueError(f"No place found for '{place}'. Try a more specific name or 'lat,lon'.")
    hit = found[0]
    return float(hit["lat"]), float(hit["lon"]), _short(hit.get("display_name", place), 4)


def _short(display_name: str, parts: int = 3) -> str:
    return ", ".join(display_name.split(", ")[:parts])


def find_places(query: str, near: str | None = None, max_results: int = 5) -> str:
    limit = min(max(int(max_results), 1), MAX_PLACES)
    params: dict = {"q": query, "limit": limit}
    if near:
        lat, lon, _ = _geocode(near)
        d = NEAR_BOX_DEG
        params |= {"viewbox": f"{lon - d},{lat + d},{lon + d},{lat - d}", "bounded": 1}
    found = _nominatim(**params)
    if not found:
        where = f" near '{near}'" if near else ""
        raise ValueError(f"No places found for '{query}'{where}. Try a different or broader query.")
    lines = []
    for p in found:
        name = p.get("name") or _short(p.get("display_name", ""), 1)
        parts = p.get("display_name", "").split(", ")
        addr = ", ".join(parts[1:4] if parts and parts[0] == name else parts[:3])
        lines.append(
            f"{name} | {addr} | {float(p['lat']):.5f},{float(p['lon']):.5f} | "
            f"{p.get('category', '')}/{p.get('type', '')}"
        )
    return "\n".join(lines)


def _sample(coords: list, n: int) -> list:
    """n evenly spaced points from coords, always including both ends."""
    if len(coords) <= n:
        return coords
    return [coords[round(i * (len(coords) - 1) / (n - 1))] for i in range(n)]


def _elevation(coords: list) -> str:
    """'gain X m, loss Y m, min A m, max B m' for [lon, lat] points; 'unavailable' on failure."""
    pts = _sample(coords, ELEVATION_SAMPLES)
    try:
        data = _get(config.ELEVATION_URL, {
            "latitude": ",".join(f"{p[1]:.5f}" for p in pts),
            "longitude": ",".join(f"{p[0]:.5f}" for p in pts),
        })
        elev = [e for e in data["elevation"] if e is not None]
    except (RuntimeError, KeyError, TypeError):
        return "unavailable"
    if not elev:
        return "unavailable"
    diffs = [b - a for a, b in zip(elev, elev[1:])]
    gain = sum(d for d in diffs if d > 0)
    loss = -sum(d for d in diffs if d < 0)
    return f"gain {gain:.0f} m, loss {loss:.0f} m, min {min(elev):.0f} m, max {max(elev):.0f} m"


def _duration(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def get_route(origin: str, destination: str, mode: str = "running") -> str:
    mode = (mode or "running").strip().lower()
    profile = MODES.get(mode)
    if not profile:
        raise ValueError(f"Unknown mode '{mode}'. Use one of: walking, running, hiking, cycling, driving.")
    lat1, lon1, name1 = _geocode(origin)
    lat2, lon2, name2 = _geocode(destination)
    data = _get(
        f"{config.OSRM_URL}/routed-{profile}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}",
        {"overview": "simplified", "geometries": "geojson", "steps": "false"},
    )
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"No {mode} route found between those points ({data.get('code', 'no route')}).")
    route = data["routes"][0]
    coords = route["geometry"]["coordinates"]  # [lon, lat] pairs
    km = route["distance"] / 1000

    duration = _duration(route["duration"])
    if mode in ("running", "run", "jogging"):
        duration = f"{_duration(km * RUN_PACE_MIN_PER_KM * 60)} at a 6:00 min/km pace (walking: {duration})"
    waypoints = "; ".join(f"{p[1]:.5f},{p[0]:.5f}" for p in _sample(coords, WAYPOINTS))
    link = (
        f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_{profile}"
        f"&route={lat1:.5f}%2C{lon1:.5f}%3B{lat2:.5f}%2C{lon2:.5f}"
    )
    return (
        f"From: {name1}\nTo: {name2}\nMode: {mode} ({profile})\n"
        f"Distance: {km:.2f} km\nEstimated time: {duration}\n"
        f"Elevation: {_elevation(coords)}\n"
        f"Path waypoints (lat,lon): {waypoints}\n"
        f"Map: {link}"
    )


# name -> (function spec, python fn), the LocalTools format mcp_client.run expects.
TOOLS: dict[str, tuple[dict, Callable]] = {
    "find_places": ({
        "name": "find_places",
        "description": "Search OpenStreetMap for places such as parks, running tracks, stadiums or a named "
        "landmark. Returns name, address, lat,lon and type per result. Use `near` to search around a "
        "neighbourhood or city. For planning a run (e.g. 3 km), first find a park or track here, then "
        "call get_route between two places.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for, e.g. 'park', 'running track', 'Cubbon Park'"},
                "near": {"type": "string", "description": "Optional area to search within (~5 km), e.g. 'Indiranagar, Bengaluru'"},
                "max_results": {"type": "integer", "description": f"1-{MAX_PLACES}, default 5"},
            },
            "required": ["query"],
        },
    }, find_places),
    "get_route": ({
        "name": "get_route",
        "description": "Get a route between two points with distance (km), estimated time, elevation "
        "gain/loss/min/max (m), waypoints along the path and an OpenStreetMap link. Origin and "
        "destination are place names (include the city) or 'lat,lon'. Use it to check a training-run "
        "route's length and hilliness.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Start: place name or 'lat,lon'"},
                "destination": {"type": "string", "description": "End: place name or 'lat,lon'"},
                "mode": {"type": "string", "description": "running (default), walking, hiking, cycling or driving"},
            },
            "required": ["origin", "destination"],
        },
    }, get_route),
}


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or [""]
    try:
        if cmd == "places" and rest:
            near = None
            if "--near" in rest:
                i = rest.index("--near")
                near = rest[i + 1] if i + 1 < len(rest) else None
                rest = rest[:i] + rest[i + 2:]
            print(find_places(" ".join(rest), near))
        elif cmd == "route" and len(rest) >= 2:
            print(get_route(rest[0], rest[1], rest[2] if len(rest) > 2 else "running"))
        else:
            sys.exit('usage: python -m backend.integrations.maps places "<query>" [--near "<place>"] '
                     '| route "<origin>" "<destination>" [mode]')
    except (ValueError, RuntimeError) as e:
        sys.exit(f"Tool error: {e}")
