import glob, json, math, os
from datetime import datetime
import xml.etree.ElementTree as ET

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

files = sorted(glob.glob('/home/gcpvm/3DTracker/gpx/*.gpx'))
all_tracks = []

for filepath in files:
    tree = ET.parse(filepath)
    root = tree.getroot()
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    trkpts = root.findall('.//gpx:trkpt', ns)
    name_el = root.find('.//gpx:name', ns)
    name = name_el.text if name_el is not None else '轨迹'
    
    if not trkpts:
        continue
    
    points = []
    prev_lat, prev_lon, prev_time = None, None, None
    cum_dist = 0.0
    
    for pt in trkpts:
        lat = float(pt.attrib['lat'])
        lon = float(pt.attrib['lon'])
        ele_el = pt.find('gpx:ele', ns)
        ele = round(float(ele_el.text), 1) if ele_el is not None and ele_el.text else 0.0
        time_el = pt.find('gpx:time', ns)
        t_str = time_el.text if time_el is not None else ''
        dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
        epoch = int(dt.timestamp())
        
        speed = 0.0
        if prev_lat is not None:
            d = haversine(prev_lat, prev_lon, lat, lon)
            dt_sec = epoch - prev_time
            cum_dist += d
            if dt_sec > 0:
                speed = (d / dt_sec) * 3.6 # km/h
        
        # Round lon/lat to 6 decimals (~0.1m precision)
        points.append({
            'lat': round(lat, 6),
            'lon': round(lon, 6),
            'ele': ele,
            'time': epoch,
            'time_iso': t_str,
            'dist_km': round(cum_dist / 1000.0, 3),
            'speed': round(speed, 1)
        })
        prev_lat, prev_lon, prev_time = lat, lon, epoch

    all_tracks.append({
        'id': os.path.splitext(os.path.basename(filepath))[0],
        'file': os.path.basename(filepath),
        'name': name,
        'points_count': len(points),
        'start_time': points[0]['time'],
        'end_time': points[-1]['time'],
        'start_iso': points[0]['time_iso'],
        'end_iso': points[-1]['time_iso'],
        'dist_km': round(cum_dist / 1000.0, 2),
        'points': points
    })

all_tracks.sort(key=lambda x: x['start_time'])

print(f"Loaded {len(all_tracks)} tracks.")
for i, trk in enumerate(all_tracks):
    print(f"Track {i+1}: {trk['name']} - {trk['dist_km']} km - {trk['start_iso']} to {trk['end_iso']}")

