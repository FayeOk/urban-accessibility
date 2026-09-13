"""
convert_isochrone_for_frontend.py
把等时圈bounds从GCJ-02转为WGS-84，生成前端可直接用的GeoJSON
"""
import json, math
import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

BASE = '/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild'
IN_FILE  = f'{BASE}/Back_end/data_process/output/isochrone_45min_6districts.geojson'
OUT_FILE = f'{BASE}/public/data/output/isochrone_polys.geojson'

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

print('读取等时圈数据...')
with open(IN_FILE, encoding='utf-8') as f:
    raw = json.load(f)

features = []
ok = 0
for feat in raw['features']:
    p = feat['properties']
    if p.get('status') != 'ok':
        continue
    bounds = p.get('bounds', [])
    if not bounds:
        continue

    # 转换所有环的坐标
    polys = []
    for ring in bounds:
        if len(ring) < 3:
            continue
        try:
            coords = []
            for pt in ring:
                wlon, wlat = gcj2wgs(float(pt[0]), float(pt[1]))
                coords.append([wlon, wlat])
            # 闭合环
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            poly = Polygon(coords)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_valid and not poly.is_empty:
                polys.append(poly)
        except:
            continue

    if not polys:
        continue

    merged = unary_union(polys) if len(polys) > 1 else polys[0]
    if merged.is_empty:
        continue

    # 转为GeoJSON geometry
    if merged.geom_type == 'Polygon':
        geom = {
            'type': 'Polygon',
            'coordinates': [list(merged.exterior.coords)]
        }
    else:  # MultiPolygon
        geom = {
            'type': 'MultiPolygon',
            'coordinates': [
                [list(g.exterior.coords)]
                for g in merged.geoms
            ]
        }

    features.append({
        'type': 'Feature',
        'properties': {
            'grid_idx': p.get('grid_idx'),
            'wgsLon':   p.get('wgsLon'),
            'wgsLat':   p.get('wgsLat'),
        },
        'geometry': geom,
    })
    ok += 1

print(f'转换成功: {ok} 个等时圈')

out_gj = {'type': 'FeatureCollection', 'features': features}
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(out_gj, f, ensure_ascii=False)

import os
size = os.path.getsize(OUT_FILE)/1024/1024
print(f'✓ 保存: {OUT_FILE} ({size:.1f} MB)')
print('前端加载路径: /data/output/isochrone_polys.geojson')