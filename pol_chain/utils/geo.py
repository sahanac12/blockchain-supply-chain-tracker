import math
from datetime import datetime

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def estimate_max_speed_kmh(transport: str) -> float:
    t = transport.lower()
    if t == "truck":
        return 120.0
    elif t == "air":
        return 900.0
    elif t == "ground":
        return 80.0
    return 120.0  # Default to truck if unknown

def is_plausible(prev_lat: float, prev_lon: float, prev_timestamp: str,
                 curr_lat: float, curr_lon: float, curr_timestamp: str,
                 transport: str = "truck"):
    # Timestamps in ISO 8601 UTC
    try:
        t1 = datetime.fromisoformat(prev_timestamp.replace('Z', '+00:00'))
        t2 = datetime.fromisoformat(curr_timestamp.replace('Z', '+00:00'))
    except ValueError:
        return False, "Invalid timestamp format"
        
    time_diff_hours = (t2 - t1).total_seconds() / 3600.0
    
    if time_diff_hours <= 0:
        return False, "Current timestamp must be after previous timestamp"
        
    distance_km = haversine_km(prev_lat, prev_lon, curr_lat, curr_lon)
    speed_kmh = distance_km / time_diff_hours
    
    max_speed = estimate_max_speed_kmh(transport)
    
    # Ground transport check > 200 km/h
    if transport.lower() in ["truck", "ground"]:
        if speed_kmh > 200.0:
            return False, f"Implausible speed: {speed_kmh:.1f} km/h > 200 km/h for ground transport"
            
    if speed_kmh > max_speed:
        return False, f"Implausible speed: {speed_kmh:.1f} km/h > max speed {max_speed} km/h for {transport}"
        
    return True, "Plausible"
