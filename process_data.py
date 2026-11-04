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

# Itinerary metadata for each leg
LEG_INFOS = {
    "activity_23898219350": {
        "day": 1,
        "title": "出京西征 · 塞外风光",
        "route": "北京朝阳区 → 张家口 → 呼和浩特 → 包头 → 巴彦淖尔",
        "highway": "G7京新高速 / G6京藏高速",
        "highlights": "出居庸关、八达岭长城、塞外草原、阴山南麓",
        "desc": "西北自驾大环线第一天，清晨由北京出发，穿越八达岭与官厅水库，驶上G7京新高速，经张家口、集宁、呼和浩特与包头，傍晚抵达黄河几字弯顶端的巴彦淖尔市。"
    },
    "activity_23907014337": {
        "day": 2,
        "title": "深入大漠 · 额济纳之约",
        "route": "巴彦淖尔 → 乌拉特后旗 → 巴丹吉林北缘 → 额济纳旗",
        "highway": "G7京新高速（最长沙漠高速）",
        "highlights": "临河绿洲、乌力吉戈壁、巴丹吉林沙漠北缘、黑河绿洲",
        "desc": "驶入G7京新高速最壮丽的沙漠公路路段，一路穿行在茫茫戈壁与大漠之间，体验极致辽阔与荒凉，傍晚抵达弱水河畔的胡杨之乡额济纳旗。"
    },
    "activity_23923610022": {
        "day": 3,
        "title": "穿越无人区 · 西出长驱入疆",
        "route": "额济纳旗 → 策克口岸连线 → 白泉/梧桐大泉 → 新疆哈密",
        "highway": "G7京新高速",
        "highlights": "黑鹰山戈壁无人区、内蒙与新疆省界、入疆第一哨、哈密绿洲",
        "desc": "自驾全程最壮烈的一天，穿越长达数百公里的内蒙-新疆交界戈壁无人区，白泉与梧桐大泉服务区，黄沙百战穿金甲，夜幕降临时顺利抵达新疆门户哈密市。"
    },
    "activity_23936684698": {
        "day": 4,
        "title": "火洲穿越 · 负海拔盆地",
        "route": "哈密 → 鄯善库木塔格沙漠 → 火焰山 → 吐鲁番",
        "highway": "G30连霍高速",
        "highlights": "百里风区、火焰山赤壁、吐峪沟麻扎村、艾丁湖盆地（负海拔-42m）",
        "desc": "沿天山南麓西进，穿过百里风区，右侧是天山雪峰，左侧是苍茫戈壁，经过库木塔格沙漠与吐峪沟大峡谷，抵达中国最热也最深的地表盆地——吐鲁番。"
    },
    "activity_23961574018": {
        "day": 5,
        "title": "风车天路 · 翻越天山白水涧",
        "route": "吐鲁番 → 达坂城风车阵 → 乌鲁木齐",
        "highway": "G30连霍高速",
        "highlights": "达坂城风力发电站、天山白水涧峡谷、博格达峰眺望、乌鲁木齐都市",
        "desc": "从火洲吐鲁番向首府乌鲁木齐挺进，穿越著名的达坂城风电走廊，成千上万座银色风车在雪山下旋转，随后穿过峡谷盘山天路，抵达新疆首府乌鲁木齐。"
    },
    "activity_23959184099": {
        "day": 6,
        "title": "天山探秘 · 极目雪峰牧野",
        "route": "乌鲁木齐 → 天山南山/天山大峡谷环线",
        "highway": "省道 / 盘山旅游公路",
        "highlights": "南山高山草甸、天山雪岭云杉、海拔3071米高山垭口、哈萨克毡房",
        "desc": "乌鲁木齐休整与周边探索，驱车深入天山南麓高山秘境，海拔从市区的900米一路盘旋爬升至3071米高山雪原草甸，雪山与云杉如诗如画。"
    },
    "activity_24033224537": {
        "day": 6,
        "title": "乌鲁木齐短驳停留",
        "route": "乌鲁木齐市区短程",
        "highway": "市区联络线",
        "highlights": "市区整备加油",
        "desc": "市区短距离位移与补给休整。"
    },
    "activity_23974751072": {
        "day": 7,
        "title": "南疆天路 · 穿干沟过塔里木",
        "route": "乌鲁木齐 → 托克逊干沟 → 和硕/博斯腾湖 → 库尔勒/尉犁 → 若羌",
        "highway": "G3012吐和高速 / G0711乌尉高速 / G218国道",
        "highlights": "险峻干沟公路、塔里木盆地东缘、博斯腾湖湿地、罗布泊门户若羌",
        "desc": "今日由北疆跨入南疆，翻越干沟绝壁险隘，经中国最大内陆淡水湖博斯腾湖西侧，沿塔里木盆地东缘向南纵贯数百公里，夜宿古丝绸之路重镇若羌。"
    },
    "activity_23986090655": {
        "day": 8,
        "title": "阿尔金天险 · 入青海柴达木",
        "route": "新疆若羌 → 依吞布拉克 → 阿尔金山无人区 → 青海茫崖",
        "highway": "G315国道 / 依若高速",
        "highlights": "阿尔金山口(3534m)、红柳沟峡谷、疆青省界、中国最孤独城市茫崖",
        "desc": "从塔里木盆地骤然拔升进入青藏高原边缘，穿越雄奇险峻的阿尔金山红柳沟，翻越海拔3534米的阿尔金山口，告别新疆进入青海省柴达木盆地西端茫崖。"
    },
    "activity_23998654828": {
        "day": 9,
        "title": "柴达木秘境 · 雅丹与双色湖",
        "route": "茫崖 → 翡翠湖/艾肯泉 → 水上雅丹 → 黄花南 → 大柴旦",
        "highway": "G315国道（火星公路）",
        "highlights": "茫崖翡翠湖碧玉水、波浪公路U型天路、水上雅丹奇观、大柴旦翡翠湖",
        "desc": "行驶在神奇的G315国道“火星公路”上，两旁尽是亿万年风蚀形成的雅丹地貌与盐沼，经过翡翠湖与世界唯一水上雅丹地貌，抵达大柴旦。"
    },
    "activity_24020014182": {
        "day": 10,
        "title": "柴达木走廊 · 奔赴天空之镜",
        "route": "大柴旦 → 德令哈（海子诗城） → 乌兰县 → 茶卡盐湖",
        "highway": "G3011柳格高速 / G109京拉国道",
        "highlights": "德令哈外星人遗址区域、柯鲁柯绿洲、茶卡盐湖天空之镜",
        "desc": "穿行在柴达木盆地腹地，途经诗人海子笔下的戈壁绿洲德令哈，穿越广袤的荒漠草原，傍晚抵达闻名遐迩的天空之镜——茶卡盐湖。"
    },
    "activity_24020034376": {
        "day": 11,
        "title": "翻越橡皮山 · 圣湖青海环游",
        "route": "茶卡 → 橡皮山口(3779m) → 青海湖二郎剑 → 日月山(3520m) → 湟源 → 西宁",
        "highway": "G109国道 / 京拉线",
        "highlights": "全线最高海拔橡皮山(3779m)、中国最大内陆湖青海湖、文成公主日月山、西宁",
        "desc": "迎着高原朝阳翻越全程最高海拔点——3779米的橡皮山垭口，随后碧蓝如海的青海湖在眼前豁然展开，沿湖滨公路驰骋，翻过日月山抵达青海省会西宁。"
    },
    "activity_24033118960": {
        "day": 12,
        "title": "高原古城 · 塔尔古刹巡礼",
        "route": "西宁市区 → 塔尔寺 / 湟中 / 拉脊山盘山天路",
        "highway": "西和高速 / 扎马线",
        "highlights": "藏传佛教圣地塔尔寺、拉脊山高山垭口(3462m)、宗喀巴大师诞生地",
        "desc": "西宁文化探索之旅，朝觐藏传佛教格鲁派六大寺院之一的塔尔寺，欣赏酥油花、壁画和堆绣艺术瑰宝，并驾车翻越西宁南侧的拉脊山风光带。"
    },
    "activity_24045303108": {
        "day": 13,
        "title": "黄河奔流 · 塞上江南行",
        "route": "西宁 → 兰州 → 白银 → 中卫沙坡头外围 → 吴忠 → 银川",
        "highway": "G6京藏高速 / G1816乌玛高速",
        "highlights": "黄河大峡谷、腾格里沙漠南缘、中卫沙坡头黄河转弯、贺兰山下塞上江南",
        "desc": "由青海高原顺黄河峡谷东下甘肃兰州，随后折向东北驶入宁夏平原，沿黄河水脉一路奔向贺兰山麓的塞上明珠银川市。"
    },
    "activity_24058769247": {
        "day": 14,
        "title": "长河落日 · 穿越鄂尔多斯高原",
        "route": "银川 → 贺兰山口 → 乌海（黄河明珠） → 鄂尔多斯市 → 准格尔 → 呼和浩特",
        "highway": "G6京藏高速 / G18荣乌高速",
        "highlights": "乌海甘德尔山黄河水库、库布齐沙漠边缘、毛乌素沙地、准格尔黄土台塬",
        "desc": "告别银川，在乌海与黄河相伴而行，随后登上鄂尔多斯高原，横跨内蒙古准格尔煤海台塬，傍晚抵达内蒙古自治区首府呼和浩特市。"
    },
    "activity_24070972632": {
        "day": 15,
        "title": "敕勒川下 · 八千公里凯旋归京",
        "route": "呼和浩特 → 乌兰察布草原 → 张家口 → 官厅水库 → 八达岭 → 北京朝阳",
        "highway": "G6京藏高速 / G7京新高速",
        "highlights": "大青山阴山山脉、乌兰察布察哈尔火山地貌带、塞外古长城、凯旋北京大闭环",
        "desc": "自驾大环线收官冲刺！从呼和浩特出发，穿越乌兰察布草原与张家口峡谷，经八达岭长城重回北京平原，顺利回到朝阳区出发地，8015公里西北大环线圆满凯旋！"
    }
}

POIS = [
    {"name": "北京 (朝阳区出发地)", "lat": 40.0375, "lon": 116.4223, "ele": 44, "day": 1, "desc": "西北8000公里自驾大征程起点"},
    {"name": "八达岭长城", "lat": 40.3590, "lon": 116.0022, "ele": 605, "day": 1, "desc": "出居庸关穿八达岭，告别华北平原"},
    {"name": "乌兰察布草原", "lat": 41.0180, "lon": 113.1120, "ele": 1412, "day": 1, "desc": "察哈尔高原草原门户"},
    {"name": "巴彦淖尔 (河套平原)", "lat": 40.7295, "lon": 107.3787, "ele": 1032, "day": 1, "desc": "黄河百害唯富一套，首日休整地"},
    {"name": "乌力吉戈壁服务区", "lat": 41.5780, "lon": 104.3820, "ele": 1180, "day": 2, "desc": "G7京新高速荒漠大服务区"},
    {"name": "额济纳旗 (胡杨林故乡)", "lat": 41.9607, "lon": 101.0680, "ele": 940, "day": 2, "desc": "弱水流沙，金秋胡杨仙境"},
    {"name": "黑鹰山戈壁无人区", "lat": 42.1800, "lon": 97.4500, "ele": 1420, "day": 3, "desc": "内蒙西端壮阔无人戈壁"},
    {"name": "新疆哈密 (甜蜜之城)", "lat": 42.7626, "lon": 92.0566, "ele": 780, "day": 3, "desc": "西出阳关长驱入疆第一门户"},
    {"name": "百里风区", "lat": 42.8500, "lon": 90.5200, "ele": 450, "day": 4, "desc": "天山山谷峡管狂风走廊"},
    {"name": "吐鲁番 (-42m艾丁湖盆地)", "lat": 42.9555, "lon": 89.1755, "ele": -42, "day": 4, "desc": "全线最低海拔点，世界第二低陆地"},
    {"name": "达坂城风力发电站", "lat": 43.3500, "lon": 88.3100, "ele": 1100, "day": 5, "desc": "天山隘口壮观万千风车银阵"},
    {"name": "乌鲁木齐 (亚欧大陆中心)", "lat": 43.7796, "lon": 87.5961, "ele": 890, "day": 5, "desc": "新疆首府，博格达雪峰眺望"},
    {"name": "天山南山垭口 (3071m)", "lat": 43.4350, "lon": 87.2150, "ele": 3071, "day": 6, "desc": "天山雪岭云杉高山牧场"},
    {"name": "干沟天险", "lat": 42.2500, "lon": 88.5200, "ele": 1250, "day": 7, "desc": "翻越天山南支干沟绝壁隘道"},
    {"name": "若羌 (罗布泊门户)", "lat": 39.0202, "lon": 88.1656, "ele": 885, "day": 7, "desc": "古丝绸之路重镇，红枣之乡"},
    {"name": "阿尔金山口 (3534m)", "lat": 38.6500, "lon": 89.9200, "ele": 3534, "day": 8, "desc": "跨越阿尔金山国家级自然保护区天险"},
    {"name": "茫崖市 (中国最孤独城市)", "lat": 38.2576, "lon": 90.8534, "ele": 2980, "day": 8, "desc": "昆仑山下石油翡翠盐沼城"},
    {"name": "水上雅丹奇观", "lat": 37.8900, "lon": 93.6800, "ele": 2720, "day": 9, "desc": "鸭湖水上垄岗状雅丹世界奇观"},
    {"name": "大柴旦 (翡翠明珠)", "lat": 37.8514, "lon": 95.3548, "ele": 3150, "day": 9, "desc": "柴达木重镇，七彩翡翠盐湖"},
    {"name": "德令哈 (海子之城)", "lat": 37.3700, "lon": 97.3700, "ele": 2980, "day": 10, "desc": "姐姐，今夜我在德令哈"},
    {"name": "茶卡盐湖 (天空之镜)", "lat": 36.7800, "lon": 99.0800, "ele": 3060, "day": 10, "desc": "柴达木东门，纯净如镜倒映云天"},
    {"name": "橡皮山口 (3779m)", "lat": 36.7580, "lon": 99.6200, "ele": 3779, "day": 11, "desc": "全线最高海拔垭口！青海风光分界线"},
    {"name": "青海湖 (高原圣湖)", "lat": 36.5700, "lon": 100.4800, "ele": 3200, "day": 11, "desc": "碧蓝无垠中国最大内陆咸水湖"},
    {"name": "日月山 (3520m)", "lat": 36.5600, "lon": 101.0500, "ele": 3520, "day": 11, "desc": "唐蕃古道文成公主西行留泪处"},
    {"name": "西宁 (青藏咽喉)", "lat": 36.6405, "lon": 101.7170, "ele": 2260, "day": 11, "desc": "青海省会，三江之源古城"},
    {"name": "塔尔寺 (藏传圣地)", "lat": 36.4800, "lon": 101.5700, "ele": 2680, "day": 12, "desc": "宗喀巴大师诞生地，艺术三绝"},
    {"name": "中卫黄河 / 沙坡头", "lat": 37.5100, "lon": 105.1800, "ele": 1240, "day": 13, "desc": "大漠孤烟直，长河落日圆"},
    {"name": "银川 (塞上江南)", "lat": 38.4915, "lon": 106.2827, "ele": 1110, "day": 13, "desc": "贺兰山下果园成，塞北江南旧有名"},
    {"name": "乌海 (黄河明珠)", "lat": 39.6600, "lon": 106.8200, "ele": 1150, "day": 14, "desc": "沙漠与黄河交相辉映之城"},
    {"name": "呼和浩特 (青城)", "lat": 40.8200, "lon": 111.6900, "ele": 1050, "day": 14, "desc": "大青山南麓塞外名城敕勒川"},
    {"name": "北京朝阳区 (终点圆满闭环)", "lat": 40.0375, "lon": 116.4223, "ele": 44, "day": 15, "desc": "8015公里壮丽巡礼圆满归来！"}
]

files = sorted(glob.glob('/home/gcpvm/3DTracker/gpx/*.gpx'))
raw_tracks = []

for filepath in files:
    tree = ET.parse(filepath)
    root = tree.getroot()
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
    trkpts = root.findall('.//gpx:trkpt', ns)
    if not trkpts:
        continue
    
    file_id = os.path.splitext(os.path.basename(filepath))[0]
    meta = LEG_INFOS.get(file_id, {})
    
    pts = []
    for pt in trkpts:
        lat = float(pt.attrib['lat'])
        lon = float(pt.attrib['lon'])
        ele_el = pt.find('gpx:ele', ns)
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else 0.0
        time_el = pt.find('gpx:time', ns)
        t_str = time_el.text if time_el is not None else ''
        dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
        epoch = int(dt.timestamp())
        pts.append((lat, lon, ele, epoch))
        
    raw_tracks.append({
        "id": file_id,
        "meta": meta,
        "pts": pts
    })

raw_tracks.sort(key=lambda t: t['pts'][0][3])

print(f"Total raw tracks sorted: {len(raw_tracks)}")

# Downsampling function preserving bends & elevation extrema
def downsample_track(pts, sample_interval_sec=5, max_dist_m=800, max_angle_deg=4.0):
    if len(pts) <= 2:
        return pts
    
    result = [pts[0]]
    prev_heading = None
    
    for i in range(1, len(pts)-1):
        prev = result[-1]
        curr = pts[i]
        
        dt = curr[3] - prev[3]
        d_meters = haversine(prev[0], prev[1], curr[0], curr[1])
        
        # Calculate heading
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
        
        # Keep point if significant time passed, significant distance moved, or noticeable turn
        if dt >= sample_interval_sec or d_meters >= max_dist_m or angle_diff >= max_angle_deg:
            result.append(curr)
            prev_heading = heading
            
    result.append(pts[-1])
    return result

# Process and assemble full trip
full_points = []
legs_list = []
total_cum_dist_m = 0.0
master_pt_index = 0

for leg_idx, trk in enumerate(raw_tracks):
    meta = trk['meta']
    pts_raw = trk['pts']
    
    # downsample
    pts_ds = downsample_track(pts_raw, sample_interval_sec=4, max_dist_m=400, max_angle_deg=3.5)
    
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
                if speed > 160: # filter GPS anomalies
                    speed = 120.0
                leg_speeds.append(speed)
        
        full_points.append({
            "idx": master_pt_index,
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "ele": round(ele, 1),
            "time": epoch,
            "dist": round(total_cum_dist_m / 1000.0, 2), # km
            "spd": round(speed, 1),
            "leg": leg_idx
        })
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
        "start_coord": [round(pts_ds[0][1], 6), round(pts_ds[0][0], 6)],
        "end_coord": [round(pts_ds[-1][1], 6), round(pts_ds[-1][0], 6)],
        "bounds": [round(min_lon, 5), round(min_lat, 5), round(max_lon, 5), round(max_lat, 5)]
    })

print(f"Total downsampled master points: {len(full_points)}")
print(f"Total distance computed: {total_cum_dist_m / 1000.0:.2f} km")

os.makedirs('/home/gcpvm/3DTracker/data', exist_ok=True)

with open('/home/gcpvm/3DTracker/data/trip_data.json', 'w', encoding='utf-8') as f:
    json.dump({
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
    }, f, ensure_ascii=False)

print("Saved /home/gcpvm/3DTracker/data/trip_data.json successfully!")
