"""
compute_zone_centroids.py
=========================
计算交通小区的POI+人口加权质心
权重方案：demand_final = 0.7×POI密度 + 0.3×人口密度（与需求密度模型一致）

输入：
  北京区块数据.shp  （交通小区边界）
  demand_grid_beijing.geojson  （含demand_final字段的格网数据）

输出：
  zone_centroids.json  （各交通小区的加权质心坐标）

运行：python compute_zone_centroids.py
"""

import json, math
import numpy as np
import geopandas as gpd
from shapely.geometry import Point

BASE   = '/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild'
SHP    = '/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild/Back_end/data_process/北京区块数据.shp'
GRID   = f'{BASE}/Back_end/data_process/output/demand_grid_beijing.geojson'
OUT    = f'{BASE}/Back_end/data_process/output/zone_centroids.json'

# 选取的三个交通小区ID

TARGET_IDS = ['bj_895', 'bj_1059', 'bj_1610']
ZONE_NAMES = {
    'bj_895':  '西城北部',
    'bj_1059': '朝阳西部',
    'bj_1610': '东南边缘区',
}

def main():
    print('→ 读取交通小区边界...')
    zones = gpd.read_file(SHP)
    zones = zones[zones['id'].isin(TARGET_IDS)].copy()
    zones = zones.to_crs('EPSG:4326')
    print(f'  目标交通小区: {len(zones)} 个')

    print('\n→ 读取格网需求密度数据...')
    grid = gpd.read_file(GRID)
    grid = grid.to_crs('EPSG:4326')

    # 格网质心
    grid_proj = grid.to_crs('EPSG:32650')
    grid['cx'] = grid_proj.geometry.centroid.to_crs('EPSG:4326').x
    grid['cy'] = grid_proj.geometry.centroid.to_crs('EPSG:4326').y
    print(f'  格网总数: {len(grid)}')

    results = {}

    for _, zone in zones.iterrows():
        zid = zone['id']
        zname = ZONE_NAMES.get(zid, zid)
        poly = zone.geometry

        print(f'\n→ 处理交通小区: {zname} ({zid})')

        # 几何质心（对比用）
        zone_proj = gpd.GeoSeries([poly], crs='EPSG:4326').to_crs('EPSG:32650')
        geom_centroid = zone_proj.centroid.to_crs('EPSG:4326').iloc[0]
        print(f'  几何质心: ({geom_centroid.x:.6f}, {geom_centroid.y:.6f})')

        # 找落入该交通小区的格网
        grid_pts = gpd.GeoDataFrame(
            grid[['cx','cy','demand_final']].copy(),
            geometry=gpd.points_from_xy(grid['cx'], grid['cy']),
            crs='EPSG:4326'
        )
        within = grid_pts[grid_pts.geometry.within(poly)].copy()
        print(f'  落入格网数: {len(within)}')

        if len(within) == 0:
            # 无格网落入时用几何质心
            print(f'  ⚠ 无格网落入，使用几何质心')
            results[zid] = {
                'id': zid,
                'name': zname,
                'method': 'geometric_centroid',
                'wgsLon': round(geom_centroid.x, 6),
                'wgsLat': round(geom_centroid.y, 6),
                'grid_count': 0,
                'geom_centroid': {
                    'lon': round(geom_centroid.x, 6),
                    'lat': round(geom_centroid.y, 6),
                }
            }
            continue

        # demand_final作为权重（含0值的格网也参与，但权重为0时相当于不参与）
        weights = within['demand_final'].values.astype(float)

        # 若所有格网demand_final为0，改用等权重
        if weights.sum() == 0:
            print(f'  ⚠ 所有格网demand_final=0，改用等权重')
            weights = np.ones(len(within))

        # 加权质心
        w_sum = weights.sum()
        w_lon = (within['cx'].values * weights).sum() / w_sum
        w_lat = (within['cy'].values * weights).sum() / w_sum

        print(f'  加权质心: ({w_lon:.6f}, {w_lat:.6f})')
        print(f'  与几何质心偏差: Δlon={w_lon-geom_centroid.x:.4f}° Δlat={w_lat-geom_centroid.y:.4f}°')
        print(f'  参与加权格网: {len(within)}个  权重均值: {weights.mean():.2f}  最大: {weights.max():.2f}')

        # 验证加权质心是否落在交通小区内
        pt = Point(w_lon, w_lat)
        in_zone = poly.contains(pt)
        print(f'  加权质心在小区内: {in_zone}')
        if not in_zone:
            # snap到边界内最近点
            from shapely.ops import nearest_points
            nearest = nearest_points(poly, pt)[0]
            # 向内缩进一点
            w_lon = (w_lon + nearest.x) / 2
            w_lat = (w_lat + nearest.y) / 2
            print(f'  → 已修正至边界内: ({w_lon:.6f}, {w_lat:.6f})')

        results[zid] = {
            'id': zid,
            'name': zname,
            'method': 'demand_weighted_centroid',
            'wgsLon': round(w_lon, 6),
            'wgsLat': round(w_lat, 6),
            'grid_count': int(len(within)),
            'weight_sum': round(float(w_sum), 2),
            'geom_centroid': {
                'lon': round(geom_centroid.x, 6),
                'lat': round(geom_centroid.y, 6),
            }
        }

    # 保存结果
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*50}')
    print(f'✓ 保存: {OUT}')
    print(f'\n质心汇总：')
    for zid, r in results.items():
        print(f'  {r["name"]}')
        print(f'    加权质心: ({r["wgsLon"]}, {r["wgsLat"]})')
        print(f'    几何质心: ({r["geom_centroid"]["lon"]}, {r["geom_centroid"]["lat"]})')
        print(f'    方法: {r["method"]}  格网数: {r.get("grid_count",0)}')

if __name__ == '__main__':
    main()