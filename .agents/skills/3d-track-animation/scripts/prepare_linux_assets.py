#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-process map tiles, road overlays, activity icon, and Chinese/English title banners
into raw RGBA buffers for the Linux C++ 3D renderer (render_3d_track_linux.cpp).
"""

import argparse
import json
import math
import os
import struct
import subprocess
import sys


def write_rgba_file(path, width, height, rgba_bytes):
    with open(path, 'wb') as f:
        f.write(struct.pack('<II', int(width), int(height)))
        f.write(rgba_bytes)


def find_cjk_font(size):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    # Search /usr/share/fonts recursively for any CJK or Noto/WQY font
    if os.path.isdir("/usr/share/fonts"):
        for root, _, files in os.walk("/usr/share/fonts"):
            for fn in files:
                low = fn.lower()
                if any(k in low for k in ("cjk", "wqy", "zenhei", "microhei", "droidsansfallback", "noto")):
                    fp = os.path.join(root, fn)
                    try:
                        return ImageFont.truetype(fp, size)
                    except Exception:
                        pass
    return ImageFont.load_default()


def prepare_with_pil(td, res_dir, out_dir):
    from PIL import Image, ImageDraw, ImageEnhance

    z = int(td['z'])
    x_min, x_max = int(td['x_min']), int(td['x_max'])
    y_min, y_max = int(td['y_min']), int(td['y_max'])
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    mw, mh = cols * 256, rows * 256

    sat_dir = td['sat_tiles_dir']
    road_dir = td.get('road_tiles_dir', '')
    use_road = bool(td.get('use_road_overlay', False))

    mosaic = Image.new('RGBA', (mw, mh), (20, 26, 33, 255))
    for ty in range(y_min, y_max + 1):
        for tx in range(x_min, x_max + 1):
            p = os.path.join(sat_dir, f"{z}_{tx}_{ty}.jpg")
            if os.path.exists(p):
                try:
                    im = Image.open(p).convert('RGBA')
                    if im.size != (256, 256):
                        im = im.resize((256, 256), Image.Resampling.BILINEAR)
                    mosaic.paste(im, ((tx - x_min) * 256, (ty - y_min) * 256))
                except Exception:
                    pass

    # Save grayscale darkened minimap mosaic BEFORE compositing road labels
    gray = mosaic.convert('L')
    gray_rgb = Image.merge('RGBA', (
        gray.point(lambda v: int(v * 0.62)),
        gray.point(lambda v: int(v * 0.64)),
        gray.point(lambda v: int(v * 0.66)),
        Image.new('L', (mw, mh), 255)
    ))
    write_rgba_file(os.path.join(out_dir, "mosaic_gray.rgba"), mw, mh, gray_rgb.tobytes())

    # Composite road network overlay (highways, expressways, national routes)
    # Using clean road vectors (ArcGIS World_Transportation) preserves crisp roads on the 3D ground mesh
    # without baking any upside-down or rotating Chinese characters onto the satellite terrain.
    # All city place names remain screen-aligned upright billboard badges.
    if use_road and road_dir and os.path.exists(road_dir):
        for ty in range(y_min, y_max + 1):
            for tx in range(x_min, x_max + 1):
                rp = os.path.join(road_dir, f"{z}_{tx}_{ty}.png")
                if os.path.exists(rp):
                    try:
                        rim = Image.open(rp).convert('RGBA')
                        if rim.size != (256, 256):
                            rim = rim.resize((256, 256), Image.Resampling.BILINEAR)
                        mosaic.paste(rim, ((tx - x_min) * 256, (ty - y_min) * 256), mask=rim)
                    except Exception:
                        pass

    write_rgba_file(os.path.join(out_dir, "mosaic_color.rgba"), mw, mh, mosaic.tobytes())

    # Load activity icon
    icon_mode = int(td.get('icon_mode', 0))
    icon_name = "car_icon.png" if icon_mode == 2 else ("bike_icon.png" if icon_mode == 1 else "person_icon.png")
    icon_path = os.path.join(res_dir, icon_name)
    if os.path.exists(icon_path):
        ic = Image.open(icon_path).convert('RGBA')
        write_rgba_file(os.path.join(out_dir, "icon.rgba"), ic.width, ic.height, ic.tobytes())

    # Pre-render overview title banner for 16x9 (1280x110) and 9x16 (720x110)
    title_str = f"{td.get('name', '轨迹')}  {float(td.get('total_dist', 0))/1000.0:.2f}KM  {float(td.get('total_asc', 0)):.0f}m"
    for tag, bw, fsize in [("16x9", 1280, 38), ("9x16", 720, 28)]:
        bh = 110
        banner = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(banner)
        font = find_cjk_font(fsize)
        bbox = draw.textbbox((0, 0), title_str, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = max(12, (bw - tw) // 2)
        ty = (bh - th) // 2
        # Soft dark pill background
        pad_x, pad_y = 24, 12
        draw.rounded_rectangle(
            [tx - pad_x, ty - pad_y, tx + tw + pad_x, ty + th + pad_y],
            radius=18,
            fill=(10, 15, 22, 168)
        )
        # Drop shadow + white text
        draw.text((tx + 2, ty + 2), title_str, font=font, fill=(0, 0, 0, 210))
        draw.text((tx, ty), title_str, font=font, fill=(255, 255, 255, 255))
        write_rgba_file(os.path.join(out_dir, f"banner_{tag}.rgba"), bw, bh, banner.tobytes())

    # Generate Screen-Aligned Billboard Labels (upright, normal reading direction, compact font)
    generate_billboard_labels(td, out_dir)


def haversine_km(lat1, lon1, lat2, lon2):
    import math
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat * 0.5) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon * 0.5) ** 2
    return 2.0 * r * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def generate_billboard_labels(td, out_dir):
    from PIL import Image, ImageDraw

    pts = td.get('points', [])
    if not pts:
        return

    # Built-in comprehensive Chinese cities, prefectures, and iconic landmarks
    gazetteer = [
        # Provincial Capitals & Direct Municipalities (Tier 1)
        ("北京", 39.9042, 116.4074, 1),
        ("上海", 31.2304, 121.4737, 1),
        ("天津", 39.0842, 117.2008, 1),
        ("重庆", 29.5630, 106.5516, 1),
        ("广州", 23.1291, 113.2644, 1),
        ("深圳", 22.5431, 114.0579, 1),
        ("成都", 30.5728, 104.0668, 1),
        ("杭州", 30.2741, 120.1551, 1),
        ("武汉", 30.5928, 114.3054, 1),
        ("南京", 32.0603, 118.7969, 1),
        ("西安", 34.3416, 108.9398, 1),
        ("郑州", 34.7580, 113.6654, 1),
        ("长沙", 28.1941, 112.9823, 1),
        ("沈阳", 41.8057, 123.4315, 1),
        ("济南", 36.6758, 117.0009, 1),
        ("青岛", 36.0671, 120.3826, 1),
        ("哈尔滨", 45.7570, 126.6424, 1),
        ("长春", 43.8868, 125.3245, 1),
        ("石家庄", 38.0428, 114.5149, 1),
        ("太原", 37.8706, 112.5489, 1),
        ("合肥", 31.8206, 117.2272, 1),
        ("福州", 26.0753, 119.3062, 1),
        ("厦门", 24.4798, 118.0894, 1),
        ("南昌", 28.6765, 115.8921, 1),
        ("南宁", 22.8155, 108.3275, 1),
        ("海口", 20.0319, 110.3312, 1),
        ("三亚", 18.2528, 109.5120, 1),
        ("贵阳", 26.5783, 106.7135, 1),
        ("昆明", 24.8801, 102.8329, 1),
        ("拉萨", 29.6469, 91.1172, 1),
        ("兰州", 36.0611, 103.8343, 1),
        ("西宁", 36.6232, 101.7789, 1),
        ("银川", 38.4664, 106.2781, 1),
        ("乌鲁木齐", 43.7928, 87.6177, 1),
        ("呼和浩特", 40.8415, 111.7519, 1),
        ("台北", 25.0330, 121.5654, 1),
        ("香港", 22.3193, 114.1694, 1),
        ("澳门", 22.1987, 113.5439, 1),

        # Northwest & Northern Corridors (Tier 2)
        ("张家口", 40.8119, 114.8841, 2),
        ("乌兰察布", 41.0347, 113.1326, 2),
        ("包头", 40.6582, 109.8404, 2),
        ("巴彦淖尔", 40.7574, 107.4170, 2),
        ("乌拉特后旗", 41.0800, 107.0700, 2),
        ("额济纳旗", 41.9608, 101.0680, 2),
        ("哈密", 42.8190, 93.5152, 2),
        ("鄯善", 42.8680, 90.2140, 2),
        ("吐鲁番", 42.9513, 89.1895, 2),
        ("托克逊", 42.7930, 88.6580, 2),
        ("和硕", 42.2680, 86.8640, 2),
        ("库尔勒", 41.7640, 86.1590, 2),
        ("尉犁", 41.3440, 86.2590, 2),
        ("轮台", 41.7770, 84.2610, 2),
        ("库车", 41.7170, 82.9620, 2),
        ("若羌", 39.0202, 88.1657, 2),
        ("且末", 38.1450, 85.5300, 2),
        ("依吞布拉克", 37.8500, 89.2800, 2),
        ("茫崖", 38.2576, 90.8534, 2),
        ("冷湖", 38.7400, 93.3300, 2),
        ("大柴旦", 37.8500, 95.3400, 2),
        ("德令哈", 37.3695, 97.3708, 2),
        ("格尔木", 36.4023, 94.9033, 2),
        ("乌兰", 36.9300, 98.4800, 2),
        ("都兰", 36.3020, 98.0920, 2),
        ("共和", 36.2800, 100.6200, 2),
        ("湟源", 36.6820, 101.2560, 2),
        ("白银", 36.5457, 104.1736, 2),
        ("中卫", 37.5149, 105.1896, 2),
        ("吴忠", 37.9867, 106.1982, 2),
        ("乌海", 39.6737, 106.8256, 2),
        ("鄂尔多斯", 39.8171, 109.9903, 2),
        ("准格尔旗", 39.8650, 111.2380, 2),
        ("榆林", 38.2901, 109.7412, 2),
        ("延安", 36.5854, 109.4897, 2),
        ("大同", 40.0768, 113.3001, 2),
        ("酒泉", 39.7323, 98.4944, 2),
        ("嘉峪关", 39.7731, 98.2891, 2),
        ("敦煌", 40.1421, 94.6620, 2),
        ("张掖", 38.9259, 100.4498, 2),
        ("武威", 37.9322, 102.6379, 2),
        ("金昌", 38.5142, 102.1879, 2),
        ("克拉玛依", 45.5799, 84.8893, 2),
        ("伊宁", 43.9219, 81.3242, 2),
        ("阿克苏", 41.1687, 80.2606, 2),
        ("喀什", 39.4677, 75.9897, 2),
        ("和田", 37.1142, 79.9222, 2),

        # Famous Scenic & Geographical Landmarks (Tier 3)
        ("茶卡盐湖", 36.7000, 99.0800, 3),
        ("青海湖", 36.6000, 100.4500, 3),
        ("翡翠湖", 38.3000, 90.3500, 3),
        ("水上雅丹", 37.6000, 93.2000, 3),
        ("达坂城", 43.3550, 88.3150, 3),
        ("火焰山", 42.9800, 89.5500, 3),
        ("官厅水库", 40.3500, 115.7500, 3),
        ("八达岭", 40.3600, 116.0100, 3),
        ("日月山", 36.5600, 101.0300, 3),
        ("沙坡头", 37.4500, 105.0200, 3),
        ("赛里木湖", 44.6000, 81.1800, 3),
        ("那拉提", 43.3400, 84.0500, 3),
        ("巴音布鲁克", 42.9500, 84.1500, 3),
        ("莫高窟", 40.0400, 94.8100, 3),
    ]

    # Try loading trip_data.js for custom route stops
    for look_dir in [os.getcwd(), os.path.dirname(out_dir), os.path.dirname(os.path.dirname(out_dir))]:
        tj = os.path.join(look_dir, "trip_data.js")
        if os.path.exists(tj):
            try:
                with open(tj, 'r', encoding='utf-8') as f:
                    c = f.read().strip()
                    if c.startswith("window.TRIP_DATA = "):
                        c = c[len("window.TRIP_DATA = "):]
                    elif c.startswith("window.tripData = "):
                        c = c[len("window.tripData = "):]
                    if c.endswith(";"):
                        c = c[:-1]
                    td_raw = json.loads(c)
                    for leg in td_raw.get('legs', []):
                        sc = leg.get('start_coord')
                        ec = leg.get('end_coord')
                        rt = leg.get('route', '')
                        parts = [p.strip() for p in rt.split('→') if p.strip()]
                        if sc and len(parts) >= 1:
                            s_name = parts[0].split('/')[0].strip()
                            if s_name and not any(g[0] == s_name for g in gazetteer):
                                gazetteer.append((s_name, sc[1], sc[0], 2))
                        if ec and len(parts) >= 2:
                            e_name = parts[-1].split('/')[0].strip()
                            if e_name and not any(g[0] == e_name for g in gazetteer):
                                gazetteer.append((e_name, ec[1], ec[0], 2))
            except Exception:
                pass
            break

    # Sample track points every 6th point for fast distance check
    sub_pts = pts[::6] if len(pts) > 6 else pts
    selected = []
    seen_names = set()
    for name, clat, clon, tier in gazetteer:
        if name in seen_names:
            continue
        min_d = min(haversine_km(clat, clon, p['lat'], p['lon']) for p in sub_pts)
        if min_d <= 65.0:
            seen_names.add(name)
            selected.append({'name': name, 'lat': clat, 'lon': clon, 'tier': tier, 'dist': min_d})

    # Greedily mark overview labels so they do not collide during overview shot (min ~150km apart for enlarged 2x badges)
    selected.sort(key=lambda x: (x['tier'], x['dist']))
    overview_labels = []
    for item in selected:
        collides = False
        for ov in overview_labels:
            if haversine_km(item['lat'], item['lon'], ov['lat'], ov['lon']) < 150.0:
                collides = True
                break
        if not collides:
            item['overview'] = True
            overview_labels.append(item)
        else:
            item['overview'] = False

    if not selected:
        return

    # Render billboard badges with 2x enlarged font (size 24) for prominent readability
    font = find_cjk_font(24)
    badges = []
    total_w = 0
    max_h = 0

    for item in selected:
        name = item['name']
        tier = item['tier']
        dummy = Image.new('RGBA', (10, 10))
        d_dummy = ImageDraw.Draw(dummy)
        bbox = d_dummy.textbbox((0, 0), name, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_h = 12
        pad_v = 7
        pin_h = 6
        dot_r = 4.5
        dot_space = int(dot_r * 2 + 10)
        bw = tw + pad_h * 2 + dot_space
        bh = th + pad_v * 2

        bim = Image.new('RGBA', (bw, bh + pin_h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bim)

        # Refined translucent slate pill badge
        bd.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 2,
                             fill=(15, 23, 42, 220), outline=(255, 255, 255, 90), width=2)

        # Dot indicator: cyan for tier 1/provincial, gold for tier 3/scenic, slate for tier 2
        dot_color = (56, 189, 248, 255) if tier == 1 else ((251, 191, 36, 255) if tier == 3 else (148, 163, 184, 255))
        dot_cx = pad_h + dot_r + 2
        dot_cy = bh // 2
        bd.ellipse([dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r], fill=dot_color)

        # Drop shadow + crisp white text
        tx = dot_cx + dot_r + 6
        ty = pad_v - 1
        bd.text((tx + 1, ty + 1), name, font=font, fill=(0, 0, 0, 180))
        bd.text((tx, ty), name, font=font, fill=(255, 255, 255, 255))

        # Triangle pin pointer touching the ground anchor at bottom center
        mx = bw // 2
        bd.polygon([(mx - 5, bh - 1), (mx + 5, bh - 1), (mx, bh + pin_h - 1)], fill=(15, 23, 42, 220))

        item['w'] = bw
        item['h'] = bh + pin_h
        item['anchor_x'] = mx
        item['anchor_y'] = bh + pin_h
        badges.append((item, bim))
        total_w += bw + 4
        max_h = max(max_h, bh + pin_h)

    # Pack into atlas
    atlas = Image.new('RGBA', (total_w, max_h), (0, 0, 0, 0))
    cur_x = 0
    labels_meta = []
    for item, bim in badges:
        item['atlas_x'] = cur_x
        item['atlas_y'] = 0
        atlas.paste(bim, (cur_x, 0))
        labels_meta.append({
            'name': item['name'],
            'lat': item['lat'],
            'lon': item['lon'],
            'tier': item['tier'],
            'overview': item['overview'],
            'atlas_x': item['atlas_x'],
            'atlas_y': item['atlas_y'],
            'w': item['w'],
            'h': item['h'],
            'anchor_x': item['anchor_x'],
            'anchor_y': item['anchor_y'],
        })
        cur_x += item['w'] + 2

    write_rgba_file(os.path.join(out_dir, "labels_atlas.rgba"), atlas.width, atlas.height, atlas.tobytes())
    with open(os.path.join(out_dir, "labels.json"), 'w', encoding='utf-8') as f:
        json.dump(labels_meta, f, ensure_ascii=False, indent=2)

    # Dynamic flight timing: Ensure adequate viewing window (4~7s) for each city along the route
    dist_km = float(td.get('total_dist', 0.0)) / 1000.0
    t_dist = 26.0 + 8.5 * math.log(1.0 + max(0.0, dist_km) / 10.0)
    t_cities = max(25.0, len(labels_meta) * 1.5 + len(overview_labels) * 2.0)
    cruise_sec = min(105.0, max(28.0, max(t_dist, t_cities)))
    total_sec = cruise_sec + 14.5
    print(f"Generated {len(labels_meta)} screen-aligned billboard labels ({len(overview_labels)} overview) in atlas ({atlas.width}x{atlas.height}).")
    print(f"Dynamic Flight Timing : Dist={dist_km:.1f}km, Cities={len(labels_meta)} ({len(overview_labels)} ov) -> Cruise={cruise_sec:.1f}s, Total={total_sec:.1f}s")


def decode_image_with_ffmpeg(path, target_w=0, target_h=0):
    vf = [f"scale={target_w}:{target_h}"] if (target_w > 0 and target_h > 0) else []
    if not vf:
        # Query dimensions via ffprobe
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", path],
            capture_output=True, text=True
        )
        if pr.returncode != 0 or 'x' not in pr.stdout:
            return 0, 0, b''
        parts = pr.stdout.strip().split('x')
        target_w, target_h = int(parts[0]), int(parts[1])
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode == 0 and len(res.stdout) == target_w * target_h * 4:
        return target_w, target_h, res.stdout
    return 0, 0, b''


def prepare_with_ffmpeg_fallback(td, res_dir, out_dir):
    z = int(td['z'])
    x_min, x_max = int(td['x_min']), int(td['x_max'])
    y_min, y_max = int(td['y_min']), int(td['y_max'])
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1
    mw, mh = cols * 256, rows * 256

    sat_dir = td['sat_tiles_dir']
    road_dir = td.get('road_tiles_dir', '')
    use_road = bool(td.get('use_road_overlay', False))

    mosaic = bytearray(mw * mh * 4)
    # Initialize dark slate background
    mosaic[0::4] = bytes([20]) * (mw * mh)
    mosaic[1::4] = bytes([26]) * (mw * mh)
    mosaic[2::4] = bytes([33]) * (mw * mh)
    mosaic[3::4] = bytes([255]) * (mw * mh)

    for ty in range(y_min, y_max + 1):
        for tx in range(x_min, x_max + 1):
            p = os.path.join(sat_dir, f"{z}_{tx}_{ty}.jpg")
            if os.path.exists(p):
                _, _, buf = decode_image_with_ffmpeg(p, 256, 256)
                if buf:
                    ox = (tx - x_min) * 256
                    oy = (ty - y_min) * 256
                    for r in range(256):
                        dst_off = ((oy + r) * mw + ox) * 4
                        src_off = r * 256 * 4
                        mosaic[dst_off:dst_off + 1024] = buf[src_off:src_off + 1024]

    # Build grayscale mosaic
    gray = bytearray(mw * mh * 4)
    for i in range(0, mw * mh * 4, 4):
        lum = (mosaic[i] * 77 + mosaic[i + 1] * 150 + mosaic[i + 2] * 29) >> 8
        gray[i] = int(lum * 0.62)
        gray[i + 1] = int(lum * 0.64)
        gray[i + 2] = int(lum * 0.66)
        gray[i + 3] = 255
    write_rgba_file(os.path.join(out_dir, "mosaic_gray.rgba"), mw, mh, gray)

    # Composite road overlay in fallback mode
    if use_road and road_dir and os.path.exists(road_dir):
        for ty in range(y_min, y_max + 1):
            for tx in range(x_min, x_max + 1):
                rp = os.path.join(road_dir, f"{z}_{tx}_{ty}.png")
                if os.path.exists(rp):
                    _, _, rbuf = decode_image_with_ffmpeg(rp, 256, 256)
                    if rbuf:
                        ox = (tx - x_min) * 256
                        oy = (ty - y_min) * 256
                        for r in range(256):
                            for c in range(256):
                                s_idx = (r * 256 + c) * 4
                                sa = rbuf[s_idx + 3]
                                if sa > 0:
                                    d_idx = ((oy + r) * mw + (ox + c)) * 4
                                    da = 255 - sa
                                    mosaic[d_idx]   = (rbuf[s_idx] * sa + mosaic[d_idx] * da) >> 8
                                    mosaic[d_idx+1] = (rbuf[s_idx+1] * sa + mosaic[d_idx+1] * da) >> 8
                                    mosaic[d_idx+2] = (rbuf[s_idx+2] * sa + mosaic[d_idx+2] * da) >> 8
    write_rgba_file(os.path.join(out_dir, "mosaic_color.rgba"), mw, mh, mosaic)

    icon_mode = int(td.get('icon_mode', 0))
    icon_name = "car_icon.png" if icon_mode == 2 else ("bike_icon.png" if icon_mode == 1 else "person_icon.png")
    icon_path = os.path.join(res_dir, icon_name)
    if os.path.exists(icon_path):
        iw, ih, ibuf = decode_image_with_ffmpeg(icon_path)
        if ibuf:
            write_rgba_file(os.path.join(out_dir, "icon.rgba"), iw, ih, ibuf)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    parser.add_argument("--res-dir", required=True)
    parser.add_argument("--out-dir", "--work-dir", dest="out_dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    with open(args.json, 'r', encoding='utf-8') as f:
        td = json.load(f)

    try:
        import PIL  # noqa: F401
        has_pil = True
    except ImportError:
        has_pil = False

    if has_pil:
        prepare_with_pil(td, args.res_dir, args.out_dir)
    else:
        prepare_with_ffmpeg_fallback(td, args.res_dir, args.out_dir)
    print(f"Prepared Linux RGBA assets in {args.out_dir}")


if __name__ == "__main__":
    main()
