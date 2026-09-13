"""
quick_isochrone.py - 射线采样边界点法提取等时圈
边界点取法：对每个方向，找时间序列中最远的<=threshold的采样点
用样条曲线连成平滑多边形
"""
import json, math, warnings
import numpy as np
from shapely.geometry import Polygon, Point, mapping
from scipy.interpolate import splprep, splev
warnings.filterwarnings('ignore')

BASE = '/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild'
RAYS = f'{BASE}/Back_end/data_process/output/zone_rays_both.json'
OUT  = f'{BASE}/public/data/output/zone_isochrones.geojson'

CAR_T = 30
BUS_T = 45
DIRECTIONS = [0, 45, 90, 135, 180, 225, 270, 315]

def ray_point(cx, cy, deg, dist_m):
    R = 6371000.0
    lat1 = math.radians(cy)
    lon1 = math.radians(cx)
    bearing = math.radians(deg)
    d = dist_m / R
    lat2 = math.asin(math.sin(lat1)*math.cos(d)+math.cos(lat1)*math.sin(d)*math.cos(bearing))
    lon2 = lon1+math.atan2(math.sin(bearing)*math.sin(d)*math.cos(lat1),math.cos(d)-math.sin(lat1)*math.sin(lat2))
    return math.degrees(lon2), math.degrees(lat2)

def extract_iso(rays, threshold, cx, cy):
    # 按方向分组
    rays_by_dir = {}
    for r in rays:
        if r.get('time_min') is None: continue
        deg = r['direction']
        if deg not in rays_by_dir: rays_by_dir[deg] = []
        rays_by_dir[deg].append((r['distance_m'], r['time_min']))

    boundary_pts = []
    for deg in DIRECTIONS:
        pts = sorted(rays_by_dir.get(deg, []), key=lambda x: x[0])
        if not pts: continue

        # 找最远的<=threshold的采样点
        # 这代表在该方向上，30/45分钟内能到达的最远位置
        valid_within = [(d, t) for d, t in pts if t <= threshold]
        if not valid_within:
            # 该方向所有点都超过阈值，边界在质心附近，跳过
            continue

        # 取最远的在阈值内的点作为边界
        boundary_dist, boundary_time = valid_within[-1]

        # 如果最远点之后还有点，做一次线性插值找更精确边界
        beyond = [(d, t) for d, t in pts if d > boundary_dist and t is not None]
        if beyond:
            d2, t2 = beyond[0]
            d1, t1 = boundary_dist, boundary_time
            if t2 > threshold and abs(t2-t1) > 0.01:
                ratio = (threshold - t1) / (t2 - t1)
                boundary_dist = d1 + ratio * (d2 - d1)

        lon, lat = ray_point(cx, cy, deg, boundary_dist)
        boundary_pts.append((deg, boundary_dist, lon, lat))

    if len(boundary_pts) < 4:
        print(f'    边界点不足: {len(boundary_pts)}个')
        return None

    boundary_pts.sort(key=lambda x: x[0])
    dists = [p[1]/1000 for p in boundary_pts]
    print(f'    边界距离: {[f"{d:.1f}km" for d in dists]}')

    lons = [p[2] for p in boundary_pts]
    lats = [p[3] for p in boundary_pts]
    lons.append(lons[0])
    lats.append(lats[0])

    try:
        pts_arr = np.array([lons, lats])
        tck, u = splprep(pts_arr, s=0, per=True, k=min(3, len(boundary_pts)-1))
        u_new = np.linspace(0, 1, 300)
        smooth_lons, smooth_lats = splev(u_new, tck)
        coords = list(zip(smooth_lons, smooth_lats))
    except:
        coords = list(zip(lons, lats))

    if coords[0] != coords[-1]: coords.append(coords[0])

    try:
        poly = Polygon(coords)
        if not poly.is_valid: poly = poly.buffer(0)
        if not poly.is_valid or poly.is_empty: return None
        area_km2 = poly.area*(111000**2)/1e6
        print(f'    ✓ {len(boundary_pts)}个方向边界点→面积≈{area_km2:.1f}km²')
        return poly
    except Exception as e:
        print(f'    多边形构建失败: {e}')
        return None

with open(RAYS, encoding='utf-8') as f:
    data = json.load(f)

features = []
summary = {}

for zid, zone in data.items():
    cx, cy = zone['wgsLon'], zone['wgsLat']
    zname  = zone['name']
    print(f'\n{zname} ({zid})')
    summary[zid] = {'name': zname, 'sessions': {}}

    for sess in ['morning', 'midday']:
        label = '早高峰' if sess == 'morning' else '平峰'
        car_rays = zone.get('car', {}).get(sess, [])
        bus_rays = zone.get('bus', {}).get(sess, [])

        print(f'  [{label}] 小汽车{CAR_T}min...')
        car_poly = extract_iso(car_rays, CAR_T, cx, cy)
        if car_poly:
            a = car_poly.area*(111000**2)/1e6
            features.append({'type':'Feature','properties':{'zone_id':zid,'zone_name':zname,'session':sess,'mode':'car','threshold':CAR_T,'area_km2':round(a,2)},'geometry':mapping(car_poly)})
            summary[zid]['sessions'].setdefault(sess,{})['car_area'] = round(a,2)
        else:
            print(f'    ✗ 提取失败')

        print(f'  [{label}] 公交{BUS_T}min...')
        bus_poly = extract_iso(bus_rays, BUS_T, cx, cy)
        if bus_poly:
            a = bus_poly.area*(111000**2)/1e6
            features.append({'type':'Feature','properties':{'zone_id':zid,'zone_name':zname,'session':sess,'mode':'bus','threshold':BUS_T,'area_km2':round(a,2)},'geometry':mapping(bus_poly)})
            summary[zid]['sessions'].setdefault(sess,{})['bus_area'] = round(a,2)
        else:
            print(f'    ✗ 提取失败')

geojson = {'type':'FeatureCollection','features':features}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(geojson, f, ensure_ascii=False)

print(f'\n✓ 输出: {OUT}  ({len(features)}个多边形)')
for zid, r in summary.items():
    print(f'  {r["name"]}:')
    for sess, v in r['sessions'].items():
        label = '早高峰' if sess=='morning' else '平峰'
        print(f'    {label}: 小汽车={v.get("car_area","—")}km²  公交={v.get("bus_area","—")}km²')