"""
process_bus_isochrone.py
从isochrone_45min_6districts.geojson找最近格网的等时圈
合并小汽车等时圈，输出zone_isochrones.geojson
"""
import json, math
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import unary_union

BASE = '/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild'
ISO_FILE = f'{BASE}/Back_end/data_process/output/isochrone_45min_6districts.geojson'
CAR_FILE = f'{BASE}/public/data/output/zone_isochrones.geojson'
OUT      = f'{BASE}/public/data/output/zone_isochrones.geojson'

ZONES = [
    {'id':'bj_895',  'name':'西城北部',   'cx':116.375085, 'cy':39.963068},
    {'id':'bj_1059', 'name':'朝阳西部',   'cx':116.442909, 'cy':39.928070},
    {'id':'bj_1610', 'name':'东南边缘区', 'cx':116.430922, 'cy':39.852824},
]

def gcj2wgs(lon, lat):
    a=6378245.0; ee=0.00669342162296594323; pi=math.pi
    def tL(x,y):
        r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(y*pi)+40*math.sin(y/3*pi))*2/3
        r+=(160*math.sin(y/12*pi)+320*math.sin(y*pi/30))*2/3; return r
    def tO(x,y):
        r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(x*pi)+40*math.sin(x/3*pi))*2/3
        r+=(150*math.sin(x/12*pi)+300*math.sin(x/30*pi))*2/3; return r
    wl,wt=lon,lat
    for _ in range(10):
        dl=tL(wl-105,wt-35); do=tO(wl-105,wt-35)
        rl=wt/180*pi; mg=math.sin(rl); mg=1-ee*mg*mg; sq=math.sqrt(mg)
        wl-=(wl+(do*180)/(a/sq*math.cos(rl)*pi))-lon
        wt-=(wt+(dl*180)/((a*(1-ee))/(mg*sq)*pi))-lat
    return wl, wt

def bounds_to_poly(bounds):
    """把bounds列表转成shapely多边形，GCJ02→WGS84"""
    polys = []
    for ring in bounds:
        if len(ring) < 3: continue
        try:
            coords = []
            for pt in ring:
                lon, lat = float(pt[0]), float(pt[1])
                wlon, wlat = gcj2wgs(lon, lat)
                coords.append((wlon, wlat))
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            p = Polygon(coords)
            if not p.is_valid: p = p.buffer(0)
            if p.is_valid and not p.is_empty and p.area > 1e-8:
                polys.append(p)
        except: continue
    if not polys: return None
    return unary_union(polys) if len(polys)>1 else polys[0]

# 读取等时圈数据
print('读取isochrone_45min_6districts.geojson...')
with open(ISO_FILE) as f:
    iso_data = json.load(f)
print(f'共{len(iso_data["features"])}个格网')

# 读取小汽车等时圈（只保留正确ID的）
print('读取小汽车等时圈...')
with open(CAR_FILE) as f:
    car_data = json.load(f)
car_features = [f for f in car_data['features']
                if f['properties']['mode']=='car'
                and f['properties']['zone_id'] in [z['id'] for z in ZONES]]
print(f'小汽车等时圈: {len(car_features)}个')

# 为每个交通小区找最近格网的公交等时圈
bus_features = []
for zone in ZONES:
    best = None
    best_dist = 999
    for feat in iso_data['features']:
        p = feat['properties']
        if p.get('status') != 'ok': continue
        dx = p['wgsLon'] - zone['cx']
        dy = p['wgsLat'] - zone['cy']
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < best_dist:
            best_dist = dist
            best = feat

    if not best:
        print(f'{zone["name"]}: 未找到最近格网')
        continue

    bounds = best['properties'].get('bounds', [])
    poly = bounds_to_poly(bounds)
    if not poly:
        print(f'{zone["name"]}: 等时圈多边形构建失败')
        continue

    area_km2 = poly.area*(111000**2)/1e6
    print(f'{zone["name"]}: 最近格网{best_dist*111:.2f}km  面积≈{area_km2:.1f}km²')

    for sess in ['morning', 'midday']:
        bus_features.append({
            'type': 'Feature',
            'properties': {
                'zone_id': zone['id'],
                'zone_name': zone['name'],
                'session': sess,
                'mode': 'bus',
                'threshold': 45,
                'area_km2': round(area_km2, 2),
            },
            'geometry': mapping(poly)
        })

# 合并输出
all_features = car_features + bus_features
geojson = {'type':'FeatureCollection','features':all_features}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(geojson, f, ensure_ascii=False)

print(f'\n✓ 输出: {OUT}')
print(f'  小汽车: {len(car_features)}个')
print(f'  公交:   {len(bus_features)}个')
print(f'  合计:   {len(all_features)}个')