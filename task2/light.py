#!/usr/bin/env python3

import csv
import math
import sys

EARTH_RADIUS_M = 6371000.0
ARRIVAL_DISTANCE_M = 3.0
STOPPED_SPEED_MS = 0.5
GREEN_DURATION_S = 5.
def to_number(text):
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def is_valid_fix(lat, lon):
    if lat is None or lon is None:
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return not (lat == 0.0 and lon == 0.0)  


def haversine_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    a = min(1.0, max(0.0, a))  
    return 2.0 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def read_rows(path):
    
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            return [row for row in csv.reader(f) if any(c.strip() for c in row)]
    except OSError as err:
        print("warning: cannot read %s (%s)" % (path, err), file=sys.stderr)
        return []


def load_targets(path):
    
    rows = read_rows(path)
    lat_col = lon_col = None
    if rows and to_number(rows[0][0]) is None:      
        for i, name in enumerate(c.strip().lower() for c in rows[0]):
            if name.startswith("lat"):
                lat_col = i
            elif name.startswith(("lon", "lng")):
                lon_col = i
        rows = rows[1:]

    targets = []
    for row in rows:
        if lat_col is not None and lon_col is not None:
            if max(lat_col, lon_col) >= len(row):
                continue
            lat, lon = to_number(row[lat_col]), to_number(row[lon_col])
        else:  
            nums = [n for n in map(to_number, row) if n is not None]
            if len(nums) < 2:
                continue
        
            lat, lon = nums[-2], nums[-1]
        if is_valid_fix(lat, lon):
            targets.append((lat, lon))
    return targets


def load_log(path):

    log = []
    for row in read_rows(path):
        cells = [c.strip() for c in row]
        time_s = to_number(cells[0])
        if time_s is None:                         
            continue
        log.append({
            "order": len(log),
            "time": time_s,
            "time_text": cells[0],
            "mode": cells[1].upper() if len(cells) > 1 else "",
            "lat": to_number(cells[2]) if len(cells) > 2 else None,
            "lon": to_number(cells[3]) if len(cells) > 3 else None,
        })
    return log


def parse_mode(text):
    if text.startswith("AUTO"):
        return "AUTO"
    if text.startswith("MAN"):
        return "MANUAL"
    return None                                     


def format_time(row):
    t = row["time"]
    return str(int(t)) if t == int(t) else row["time_text"]



def compute_lights(log, targets):

    lights = {}
    mode = "MANUAL"            
    last_fix = None            
    target_index = 0          
    green_until = None        

    for row in sorted(log, key=lambda r: (r["time"], r["order"])):
        t = row["time"]

        known = parse_mode(row["mode"])
        if known is not None:
            mode = known

        has_fix = is_valid_fix(row["lat"], row["lon"])

        if green_until is not None and t >= green_until:
            green_until = None                    

        if green_until is not None:
            light = "green"
        else:
            light = "red" if mode == "AUTO" else "blue"

            can_check = (mode == "AUTO" and has_fix
                         and target_index < len(targets)
                         and last_fix is not None and t > last_fix[0])
            if can_check:
                t_lat, t_lon = targets[target_index]
                distance = haversine_m(row["lat"], row["lon"], t_lat, t_lon)
                moved = haversine_m(last_fix[1], last_fix[2], row["lat"], row["lon"])
                speed = moved / (t - last_fix[0])
                if distance <= ARRIVAL_DISTANCE_M and speed < STOPPED_SPEED_MS:
                    light = "green"
                    green_until = t + GREEN_DURATION_S
                    target_index += 1

        lights[row["order"]] = light

        if has_fix and (last_fix is None or t > last_fix[0]):
            last_fix = (t, row["lat"], row["lon"])

    return lights


def main(argv):
    if len(argv) != 3:
        print("usage: python light.py mission_log.csv targets.csv", file=sys.stderr)
        return 1
    log = load_log(argv[1])
    targets = load_targets(argv[2])
    lights = compute_lights(log, targets)
    for row in log:
        print("%s,%s" % (format_time(row), lights[row["order"]]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
