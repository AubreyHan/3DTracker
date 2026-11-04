import glob, json, math, os
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

cst = timezone(timedelta(hours=8))

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

from process_data import LEG_INFOS, POIS, raw_tracks

# Downsampling function preserving turns and elevation extrema
def downsample_smart(pts, min_sec=12, min_meters=250, turn_angle=5.0):
    if len(pts) <= 2:
        return pts
    
    result = [pts[0]]
    prev_heading = None
    
    for i in range(1, len(pts)-1):
        prev = result[-1]
        curr = pts[i]
        
        dt = curr[3] - prev[3]
        d_meters = haversine(prev[0], prev[1], curr[0], curr[1])
        
        # heading
        dlon = math.radians(curr[1] - prev[1])
        lat1 = math.radians(prev[0])
        lat2 = math.radians(curr[0])
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
        heading = (math.degrees(math.atan2(y, x)) + 360) % 360
        
        angle_diff = 0
        if prev_heading is not None:
            angle_diff = abs(heading - prev_heading)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
        
        ele_diff = abs(curr[2] - prev[2])
        
        # Check trigger: either enough distance & time, or bend/corner, or steep elevation change
        if (dt >= min_sec and d_meters >= min_meters) or (angle_diff >= turn_angle and d_meters >= 60) or (ele_diff >= 15 and d_meters >= 100):
            result.append(curr)
            prev_heading = heading
            
    result.append(pts[-1])
    return result

full_points = []
legs_list = []
total_cum_dist_m = 0.0
master_pt_index = 0

for leg_idx, trk in enumerate(raw_tracks):
    meta = trk['meta']
    pts_raw = trk['pts']
    
    # downsample
    pts_ds = downsample_smart(pts_raw)
    
    leg_start_index = master_pt_index
    leg_dist_m = 0.0
    leg_min_ele = 99999.0
    leg_max_ele = -99999.0
    leg_speeds = []
    
    min_lon, min_lat = 180.0, 90.0
    max_lon, max_lat = -180.0, -90.0
    
    for i, pt in enumerate(pts_ds):
        lat, lon, ele, epoch = pt
        min_lon = min(min_lon, lon)
        max_lon = max(max_lon, lon)
        min_lat = min(min_lat, lat)
        max_lat = max(max_lat, lat)
        
        leg_min_ele = min(leg_min_ele, ele)
        leg_max_ele = max(leg_max_ele, ele)
        
        speed = 0.0
        if i > 0:
            prev = pts_ds[i-1]
            dm = haversine(prev[0], prev[1], lat, lon)
            dt_s = epoch - prev[3]
            leg_dist_m += dm
            total_cum_dist_m += dm
            if dt_s > 0:
                speed = (dm / dt_s) * 3.6
                if speed > 150:
                    speed = 110.0
                leg_speeds.append(speed)
        
        # [lon, lat, ele, time_sec, cum_km, speed_kmh, leg_idx]
        full_points.append([
            round(lon, 5),
            round(lat, 5),
            round(ele, 1),
            epoch,
            round(total_cum_dist_m / 1000.0, 2),
            round(speed, 1),
            leg_idx
        ])
        master_pt_index += 1
        
    leg_end_index = master_pt_index - 1
    
    start_dt = datetime.fromtimestamp(pts_ds[0][3], tz=cst)
    end_dt = datetime.fromtimestamp(pts_ds[-1][3], tz=cst)
    dur_h = (pts_ds[-1][3] - pts_ds[0][3]) / 3600.0
    avg_spd = (leg_dist_m / 1000.0) / dur_h if dur_h > 0 else 0.0
    
    legs_list.append({
        "id": trk['id'],
        "leg_idx": leg_idx,
        "day": meta.get("day", leg_idx + 1),
        "date": start_dt.strftime("%Y年%m月%d日"),
        "date_short": start_dt.strftime("%m月%d日"),
        "time_span": f"{start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}",
        "title": meta.get("title", f"第{leg_idx+1}段 越野巡航"),
        "route": meta.get("route", ""),
        "highway": meta.get("highway", ""),
        "highlights": meta.get("highlights", ""),
        "desc": meta.get("desc", ""),
        "dist_km": round(leg_dist_m / 1000.0, 1),
        "duration_h": round(dur_h, 1),
        "avg_spd": round(avg_spd, 1),
        "max_spd": round(max(leg_speeds) if leg_speeds else 0, 1),
        "min_ele": round(leg_min_ele, 0),
        "max_ele": round(leg_max_ele, 0),
        "start_idx": leg_start_index,
        "end_idx": leg_end_index,
        "pts_count": len(pts_ds),
        "start_coord": [round(pts_ds[0][1], 5), round(pts_ds[0][0], 5)],
        "end_coord": [round(pts_ds[-1][1], 5), round(pts_ds[-1][0], 5)],
        "bounds": [round(min_lon, 4), round(min_lat, 4), round(max_lon, 4), round(max_lat, 4)]
    })

print(f"Total compact master points: {len(full_points)}")
print(f"Total distance: {total_cum_dist_m / 1000.0:.1f} km")

payload = {
    "summary": {
        "title": "2026暑期西北自驾大环线",
        "subtitle": "京新G7进 · 丝路长驱 · 柴达木腹地 · 青海湖天路",
        "date_range": "2026.08.08 - 2026.08.22 (共15天)",
        "total_km": round(total_cum_dist_m / 1000.0, 1),
        "total_legs": len(legs_list),
        "max_ele": 3779,
        "min_ele": -42,
        "provinces": ["北京市", "河北省", "内蒙古自治区", "新疆维吾尔自治区", "青海省", "宁夏回族自治区"],
        "total_pts": len(full_points)
    },
    "legs": legs_list,
    "pois": POIS,
    "points": full_points
}

with open('/home/gcpvm/3DTracker/data/trip_data.json', 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False)

# Also write to trip_data.js for standalone offline opening
with open('/home/gcpvm/3DTracker/trip_data.js', 'w', encoding='utf-8') as f:
    f.write('window.TRIP_DATA = ')
    json.dump(payload, f, ensure_ascii=False)
    f.write(';\n')

print("Generated compact trip_data.json and trip_data.js!")
