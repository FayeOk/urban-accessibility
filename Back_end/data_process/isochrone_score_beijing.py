"""
isochrone_score_beijing.py
==========================
6核心区等时圈POI可达性评分脚本

输入：
  isochrone_45min_6districts.geojson  浏览器采集的45min等时圈数据
  demand_grid_beijing.geojson         全北京500m需求网格
  全量北京POI文件                      Beijing_fixed.csv

输出：
  isochrone_grid_beijing.geojson      含iso_score字段的网格文件

运行：
  python isochrone_score_beijing.py
"""

import os, json, math
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union
from scipy.spatial import cKDTree

# ── 路径配置 ──────────────────────────────────────
BASE    = "/Users/aaa/Desktop/MajorThesis/System_build"
OUT_DIR = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/data_process/output")

ISO_FILE  = "/Users/aaa/Downloads/isochrone_45min_6districts.geojson"
GRID_FILE = os.path.join(OUT_DIR, "demand_grid_beijing.geojson")
POI_FILE  = os.path.join(BASE, "urban-accessibility-rebuild/data/Beijing_fixed.csv")
OUT_FILE  = os.path.join(OUT_DIR, "isochrone_grid_beijing.geojson")

# ── 评分参数 ──────────────────────────────────────
SIGMA = 15.0   # 高斯衰减带宽（分钟）
MAX_T = 45.0   # 最大时间档位

POI_WEIGHTS = {
    "医疗保健": 3.0, "科教文化": 2.5, "购物消费": 2.0,
    "商务住宅": 2.0, "公司企业": 2.0, "运动健身": 1.5,
    "休闲娱乐": 1.5, "生活服务": 1.5, "金融机构": 1.2,
    "酒店住宿": 1.2, "旅游景点": 1.0, "餐饮美食": 1.0,
    "交通设施": 0.5, "汽车相关": 0.3,
}
DEFAULT_WEIGHT = 1.0

# ══════════════════════════════════════════════════
#  GCJ-02 → WGS-84
# ══════════════════════════════════════════════════
def gcj02_to_wgs84(lon, lat):
    a = 6378245.0; ee = 0.00669342162296594323; pi = math.pi
    def tLat(x,y):
        r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(y*pi)+40*math.sin(y/3*pi))*2/3
        r+=(160*math.sin(y/12*pi)+320*math.sin(y*pi/30))*2/3; return r
    def tLon(x,y):
        r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(x*pi)+40*math.sin(x/3*pi))*2/3
        r+=(150*math.sin(x/12*pi)+300*math.sin(x/30*pi))*2/3; return r
    wl, wt = lon, lat
    for _ in range(10):
        dlat=tLat(wl-105,wt-35); dlon=tLon(wl-105,wt-35)
        rl=wt/180*pi; mg=math.sin(rl); mg=1-ee*mg*mg; sq=math.sqrt(mg)
        wl-=(wl+(dlon*180)/(a/sq*math.cos(rl)*pi))-lon
        wt-=(wt+(dlat*180)/((a*(1-ee))/(mg*sq)*pi))-lat
    return wl, wt

# ══════════════════════════════════════════════════
#  解析bounds → WGS-84 Polygon
# ══════════════════════════════════════════════════
def bounds_to_polygon(bounds_raw):
    if not bounds_raw: return None
    polygons = []
    for ring in bounds_raw:
        if not ring or len(ring) < 3: continue
        try:
            coords = []
            for pt in ring:
                gcj_lon = float(pt[0])
                gcj_lat = float(pt[1])
                wgs_lon, wgs_lat = gcj02_to_wgs84(gcj_lon, gcj_lat)
                coords.append((wgs_lon, wgs_lat))
            if len(coords) < 3: continue
            poly = Polygon(coords)
            if not poly.is_valid: poly = poly.buffer(0)
            if poly.is_valid and not poly.is_empty:
                polygons.append(poly)
        except: continue
    if not polygons: return None
    return unary_union(polygons) if len(polygons) > 1 else polygons[0]

# ══════════════════════════════════════════════════
#  高斯衰减
# ══════════════════════════════════════════════════
def gaussian_decay(t, sigma=SIGMA):
    return math.exp(-(t**2) / (2 * sigma**2))

# ══════════════════════════════════════════════════
#  计算单网格评分
# ══════════════════════════════════════════════════
def compute_score(poly, center_lon, center_lat, poi_df):
    if poly is None or poly.is_empty: return 0.0
    bounds = poly.bounds
    # 边界框粗筛
    mask = (
        (poi_df["lon"] >= bounds[0]) & (poi_df["lon"] <= bounds[2]) &
        (poi_df["lat"] >= bounds[1]) & (poi_df["lat"] <= bounds[3])
    )
    candidates = poi_df[mask]
    if len(candidates) == 0: return 0.0

    iso_radius = max(bounds[2]-bounds[0], bounds[3]-bounds[1]) / 2.0
    center = Point(center_lon, center_lat)
    score = 0.0
    for _, row in candidates.iterrows():
        pt = Point(row["lon"], row["lat"])
        if not poly.contains(pt): continue
        ratio = min(center.distance(pt) / iso_radius, 1.0) if iso_radius > 0 else 0.5
        t_approx = ratio * MAX_T
        score += row["_weight"] * gaussian_decay(t_approx)
    return round(score, 4)

# ══════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════
def main():
    print("\n" + "═"*50)
    print("  6核心区等时圈POI评分计算")
    print("═"*50 + "\n")

    # ── 读取等时圈数据 ────────────────────────────
    print(f"→ 读取等时圈数据: {ISO_FILE}")
    with open(ISO_FILE, encoding="utf-8") as f:
        iso_gj = json.load(f)

    # 构建坐标→polygon映射（用KD-Tree匹配，不依赖grid_idx）
    iso_lons, iso_lats, iso_polys = [], [], []
    ok_count = 0
    for feat in iso_gj["features"]:
        p = feat["properties"]
        bounds_raw = p.get("bounds", [])
        if p.get("status") == "ok" and bounds_raw:
            poly = bounds_to_polygon(bounds_raw)
            iso_lons.append(float(p["wgsLon"]))
            iso_lats.append(float(p["wgsLat"]))
            iso_polys.append(poly)
            if poly is not None: ok_count += 1
        else:
            iso_lons.append(float(p["wgsLon"]))
            iso_lats.append(float(p["wgsLat"]))
            iso_polys.append(None)
    print(f"  有效等时圈: {ok_count} / {len(iso_gj['features'])}")

    # 构建KD-Tree（等时圈网格中心点）
    iso_coords = np.column_stack([
        np.array(iso_lons) * np.cos(np.radians(39.9)),
        np.array(iso_lats)
    ])
    iso_tree = cKDTree(iso_coords)
    MATCH_THRESH = 800 / 111000  # 800m对应的度数

    # ── 读取需求网格 ──────────────────────────────
    print(f"\n→ 读取需求网格: {GRID_FILE}")
    grid_gdf = gpd.read_file(GRID_FILE)
    print(f"  网格总数: {len(grid_gdf)}")

    # ── 读取全量POI ───────────────────────────────
    print(f"\n→ 读取全量POI: {POI_FILE}")
    poi_df = pd.read_csv(POI_FILE, encoding="utf-8", low_memory=False)
    poi_df["lon"] = pd.to_numeric(poi_df["经度"], errors="coerce")
    poi_df["lat"] = pd.to_numeric(poi_df["纬度"],  errors="coerce")
    poi_df = poi_df.dropna(subset=["lon","lat"])

    # POI坐标从GCJ-02转WGS-84（向量化）
    print("  → 坐标转换 GCJ-02 → WGS-84...")

    def gcj02_to_wgs84_arr(lons, lats):
        a=6378245.0; ee=0.00669342162296594323; pi=math.pi
        lons=np.array(lons,dtype=float); lats=np.array(lats,dtype=float)
        def tL(x,y):
            r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*np.sqrt(np.abs(x))
            r+=(20*np.sin(6*x*pi)+20*np.sin(2*x*pi))*2/3
            r+=(20*np.sin(y*pi)+40*np.sin(y/3*pi))*2/3
            r+=(160*np.sin(y/12*pi)+320*np.sin(y*pi/30))*2/3; return r
        def tO(x,y):
            r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*np.sqrt(np.abs(x))
            r+=(20*np.sin(6*x*pi)+20*np.sin(2*x*pi))*2/3
            r+=(20*np.sin(x*pi)+40*np.sin(x/3*pi))*2/3
            r+=(150*np.sin(x/12*pi)+300*np.sin(x/30*pi))*2/3; return r
        wl,wt=lons.copy(),lats.copy()
        for _ in range(10):
            dl=tL(wl-105,wt-35); do=tO(wl-105,wt-35)
            rl=wt/180*pi; mg=np.sin(rl); mg=1-ee*mg*mg; sq=np.sqrt(mg)
            wl-=(wl+(do*180)/(a/sq*np.cos(rl)*pi))-lons
            wt-=(wt+(dl*180)/((a*(1-ee))/(mg*sq)*pi))-lats
        return wl, wt

    wl, wt = gcj02_to_wgs84_arr(poi_df["lon"].values, poi_df["lat"].values)
    poi_df["lon"] = wl
    poi_df["lat"] = wt
    poi_df["_weight"] = poi_df["大类"].map(POI_WEIGHTS).fillna(DEFAULT_WEIGHT)

    # 只保留6核心区范围内的POI（加速计算）
    poi_df = poi_df[
        poi_df["lon"].between(116.0, 116.7) &
        poi_df["lat"].between(39.7, 40.1)
    ].copy()
    print(f"  6核心区范围内POI: {len(poi_df)} 条")

    # ── 计算评分 ──────────────────────────────────
    print(f"\n→ 计算等时圈POI评分...")
    # 预先计算所有网格中心点，批量KD-Tree查询（一次性找出有等时圈的网格）
    print("  → 预筛选有等时圈覆盖的网格...")
    all_cx = np.array([grid_gdf.iloc[i].geometry.centroid.x for i in range(len(grid_gdf))])
    all_cy = np.array([grid_gdf.iloc[i].geometry.centroid.y for i in range(len(grid_gdf))])
    grid_coords_q = np.column_stack([all_cx * np.cos(np.radians(all_cy)), all_cy])
    dists, nearest_idxs = iso_tree.query(grid_coords_q, k=1)
    valid_mask = dists <= MATCH_THRESH
    valid_indices = np.where(valid_mask)[0]
    print(f"  有等时圈覆盖的网格: {len(valid_indices)} / {len(grid_gdf)}")

    scores  = np.zeros(len(grid_gdf))
    has_iso = np.zeros(len(grid_gdf), dtype=bool)
    total   = len(valid_indices)

    for count, i in enumerate(valid_indices):
        if count % 200 == 0:
            print(f"  进度: {count}/{total}")

        cx, cy = all_cx[i], all_cy[i]
        poly = iso_polys[nearest_idxs[i]]
        s    = compute_score(poly, cx, cy, poi_df)
        scores[i]  = s
        has_iso[i] = poly is not None

    # ── 归一化 ────────────────────────────────────
    print("\n→ 归一化...")
    scores_arr = np.array(scores, dtype=float)
    nonzero    = scores_arr[scores_arr > 0]

    if len(nonzero) > 0:
        p2, p98 = np.percentile(nonzero, 2), np.percentile(nonzero, 98)
        scores_norm = np.round(
            np.clip((scores_arr - p2) / (p98 - p2 + 1e-9), 0, 1) * 100, 2)
    else:
        scores_norm = np.zeros(len(scores))

    grid_gdf["iso_score_45m"]      = scores_arr
    grid_gdf["iso_score_45m_norm"] = scores_norm
    grid_gdf["iso_score_combined"] = scores_norm
    grid_gdf["has_isochrone"]      = has_iso

    # ── 输出 ─────────────────────────────────────
    print(f"\n→ 写出结果: {OUT_FILE}")
    grid_gdf.to_file(OUT_FILE, driver="GeoJSON")

    print(f"\n{'─'*45}")
    print(f"  输出文件: {OUT_FILE}")
    print(f"  有等时圈数据的网格: {has_iso.sum()} / {len(grid_gdf)}")
    print(f"  评分>0的网格: {(scores_norm>0).sum()} / {len(grid_gdf)}")
    print(f"  评分均值(有数据区域): {scores_norm[scores_norm>0].mean():.1f}")
    print(f"  归一化区间: [{p2:.4f}, {p98:.4f}]")
    print(f"{'─'*45}")
    print("\n✓ 完成！下一步运行 merge_beijing.py 计算综合可达性")

if __name__ == "__main__":
    main()