"""
等时圈 POI 评分脚本 isochrone_score.py
=======================================
读取浏览器采集的等时圈数据（isochrone_30min.geojson / isochrone_45min.geojson），
计算每个网格的等时圈POI加权得分，输出 isochrone_grid.geojson。

数据格式说明（浏览器采集版）：
  - 坐标以字符串存储：["116.319519","39.84935"]，需转 float
  - bounds 结构：[多边形1的点列表, 多边形2的点列表, ...]
  - 坐标系：GCJ-02，需转 WGS-84 后做空间分析

运行：
  python isochrone_score.py

依赖：
  pip install geopandas shapely numpy pandas --break-system-packages
"""

import os
import json
import math
import argparse
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union

# ── 路径配置 ─────────────────────────────────────
BASE = "/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process"

DEFAULT_ISO30   = os.path.join(BASE, "output/isochrone_30min.geojson")
DEFAULT_ISO45   = os.path.join(BASE, "output/isochrone_45min.geojson")
DEFAULT_GRID    = os.path.join(BASE, "output/demand_grid.geojson")
DEFAULT_POI_DIR = "/Users/aaa/Desktop/Major Thesis/System_build/Data/MajorThesis/poi/poi_data"
DEFAULT_OUT     = os.path.join(BASE, "output/isochrone_grid.geojson")

# ── POI 权重 ──────────────────────────────────────
POI_WEIGHTS = {
    "医疗保健服务": 3.0, "科教文化服务": 2.5, "购物服务": 2.0,
    "住宅区": 2.0, "公司企业": 2.0, "政府机构及社会团体": 1.8,
    "商务住宅": 1.8, "餐饮服务": 1.5, "体育休闲服务": 1.5,
    "生活服务": 1.5, "金融保险服务": 1.2, "住宿服务": 1.2,
    "汽车服务": 0.8, "摩托车服务": 0.4,
}
DEFAULT_WEIGHT = 1.0

# ── 高斯衰减参数 ──────────────────────────────────
SIGMA_MIN = 15.0  # 分钟，15min时权重约0.61，30min约0.14


# ══════════════════════════════════════════════════
#  坐标转换
# ══════════════════════════════════════════════════

def gcj02_to_wgs84(lon, lat):
    """GCJ-02 → WGS-84（迭代法，精度 < 1m）"""
    a = 6378245.0
    ee = 0.00669342162296594323

    def transform_lat(x, y):
        r = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
        r += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        r += (20.0*math.sin(y*math.pi) + 40.0*math.sin(y/3.0*math.pi)) * 2.0/3.0
        r += (160.0*math.sin(y/12.0*math.pi) + 320*math.sin(y*math.pi/30.0)) * 2.0/3.0
        return r

    def transform_lon(x, y):
        r = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
        r += (20.0*math.sin(6.0*x*math.pi) + 20.0*math.sin(2.0*x*math.pi)) * 2.0/3.0
        r += (20.0*math.sin(x*math.pi) + 40.0*math.sin(x/3.0*math.pi)) * 2.0/3.0
        r += (150.0*math.sin(x/12.0*math.pi) + 300.0*math.sin(x/30.0*math.pi)) * 2.0/3.0
        return r

    wgs_lon, wgs_lat = lon, lat
    for _ in range(10):
        dlat = transform_lat(wgs_lon - 105.0, wgs_lat - 35.0)
        dlon = transform_lon(wgs_lon - 105.0, wgs_lat - 35.0)
        radlat = wgs_lat / 180.0 * math.pi
        magic = math.sin(radlat)
        magic = 1 - ee * magic * magic
        sqrtmagic = math.sqrt(magic)
        dlat2 = (dlat * 180.0) / ((a*(1-ee)) / (magic*sqrtmagic) * math.pi)
        dlon2 = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
        wgs_lon -= (wgs_lon + dlon2) - lon
        wgs_lat -= (wgs_lat + dlat2) - lat
    return wgs_lon, wgs_lat


def gaussian_decay(t_min, sigma=SIGMA_MIN):
    return math.exp(-(t_min ** 2) / (2 * sigma ** 2))


# ══════════════════════════════════════════════════
#  解析等时圈数据（浏览器采集格式）
# ══════════════════════════════════════════════════

def parse_bounds_to_polygon(bounds_raw):
    """
    解析 bounds 字段为 WGS-84 Shapely Polygon。

    浏览器采集的 bounds 结构：
      [ 多边形1_点列表, 多边形2_点列表, ... ]
      每个点是 [lng_str, lat_str]（GCJ-02，字符串）

    返回：Shapely Polygon 或 None
    """
    if not bounds_raw:
        return None

    polygons = []
    for ring in bounds_raw:
        if not ring or len(ring) < 3:
            continue
        try:
            # 坐标是字符串，转 float；同时从 GCJ-02 转 WGS-84
            coords_wgs = []
            for pt in ring:
                gcj_lon = float(pt[0])
                gcj_lat = float(pt[1])
                wgs_lon, wgs_lat = gcj02_to_wgs84(gcj_lon, gcj_lat)
                coords_wgs.append((wgs_lon, wgs_lat))

            if len(coords_wgs) < 3:
                continue
            poly = Polygon(coords_wgs)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_valid and not poly.is_empty:
                polygons.append(poly)
        except (ValueError, TypeError) as e:
            continue

    if not polygons:
        return None
    if len(polygons) == 1:
        return polygons[0]
    return unary_union(polygons)


# ══════════════════════════════════════════════════
#  读取 POI 数据
# ══════════════════════════════════════════════════

def load_poi_data(poi_dir):
    import glob
    print("→ 读取 POI 数据...")
    dfs = []
    for csv_file in glob.glob(os.path.join(poi_dir, "**/*.csv"), recursive=True):
        try:
            df = pd.read_csv(csv_file, encoding="utf-8", low_memory=False)
        except Exception:
            try:
                df = pd.read_csv(csv_file, encoding="gbk", low_memory=False)
            except Exception:
                continue
        dfs.append(df)

    if not dfs:
        raise ValueError("未找到 POI CSV 文件")

    poi_df = pd.concat(dfs, ignore_index=True)

    # 坐标列处理：优先 WGS-84，兼容各种列名
    if "lng_wgs84" in poi_df.columns and "lat_wgs84" in poi_df.columns:
        poi_df = poi_df.rename(columns={"lng_wgs84": "lon", "lat_wgs84": "lat"})
    elif "wlon" in poi_df.columns and "lat" in poi_df.columns:
        poi_df = poi_df.rename(columns={"wlon": "lon"})
    elif "lon" not in poi_df.columns:
        print(f"  ⚠ 可用列名: {list(poi_df.columns[:10])}")

    # 去重列（防止 rename 后出现重复列）
    poi_df = poi_df.loc[:, ~poi_df.columns.duplicated()]

    if "lon" not in poi_df.columns or "lat" not in poi_df.columns:
        raise ValueError(f"找不到坐标列，现有列: {list(poi_df.columns[:15])}")

    poi_df = poi_df.dropna(subset=["lon", "lat"])
    poi_df["lon"] = pd.to_numeric(poi_df["lon"], errors="coerce")
    poi_df["lat"] = pd.to_numeric(poi_df["lat"], errors="coerce")
    poi_df = poi_df.dropna(subset=["lon", "lat"])

    if "type1" in poi_df.columns:
        poi_df["_weight"] = poi_df["type1"].map(POI_WEIGHTS).fillna(DEFAULT_WEIGHT)
    else:
        poi_df["_weight"] = DEFAULT_WEIGHT

    print(f"  POI 总数: {len(poi_df)}")
    return poi_df


# ══════════════════════════════════════════════════
#  计算单个网格评分
# ══════════════════════════════════════════════════

def compute_score(poly, center_lon, center_lat, poi_df, minute):
    if poly is None or poly.is_empty:
        return 0.0

    bounds = poly.bounds  # (minx, miny, maxx, maxy)
    mask = (
        (poi_df["lon"] >= bounds[0]) & (poi_df["lon"] <= bounds[2]) &
        (poi_df["lat"] >= bounds[1]) & (poi_df["lat"] <= bounds[3])
    )
    candidates = poi_df[mask]
    if len(candidates) == 0:
        return 0.0

    # 等时圈大致半径（用于距离衰减估算）
    iso_radius = max(bounds[2]-bounds[0], bounds[3]-bounds[1]) / 2.0

    score = 0.0
    center = Point(center_lon, center_lat)
    for _, row in candidates.iterrows():
        pt = Point(row["lon"], row["lat"])
        if not poly.contains(pt):
            continue
        weight = row["_weight"]
        if iso_radius > 0:
            ratio = min(center.distance(pt) / iso_radius, 1.0)
            t_approx = ratio * minute
        else:
            t_approx = minute * 0.5
        score += weight * gaussian_decay(t_approx)

    return round(score, 4)


# ══════════════════════════════════════════════════
#  归一化
# ══════════════════════════════════════════════════

def percentile_norm(arr, p_low=2, p_high=98):
    arr = arr.astype(float)
    nonzero = arr[arr > 0]
    if len(nonzero) == 0:
        return np.zeros_like(arr)
    vmin = np.percentile(nonzero, p_low)
    vmax = np.percentile(nonzero, p_high)
    if vmax <= vmin:
        return np.zeros_like(arr)
    return np.round(np.clip((arr - vmin) / (vmax - vmin), 0, 1) * 100, 2)


# ══════════════════════════════════════════════════
#  主流程
# ══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso30",   default=DEFAULT_ISO30)
    parser.add_argument("--iso45",   default=DEFAULT_ISO45)
    parser.add_argument("--grid",    default=DEFAULT_GRID)
    parser.add_argument("--poi_dir", default=DEFAULT_POI_DIR)
    parser.add_argument("--out",     default=DEFAULT_OUT)
    args = parser.parse_args()

    # ── 读取等时圈数据 ────────────────────────────
    print("→ 读取等时圈数据...")
    iso_map = {}  # {grid_idx: {30: polygon, 45: polygon}}

    for minute, fpath in [(30, args.iso30), (45, args.iso45)]:
        print(f"  {minute}min: {fpath}")
        with open(fpath, encoding="utf-8") as f:
            gj = json.load(f)

        ok = 0
        for feat in gj["features"]:
            p = feat["properties"]
            idx = int(p["grid_idx"])
            status = p.get("status", "ok")
            bounds_raw = p.get("bounds", [])

            if idx not in iso_map:
                iso_map[idx] = {}

            if status == "ok" and bounds_raw:
                poly = parse_bounds_to_polygon(bounds_raw)
                iso_map[idx][minute] = poly
                if poly is not None:
                    ok += 1
            else:
                iso_map[idx][minute] = None

        print(f"    有效等时圈: {ok} / {len(gj['features'])}")

    # ── 读取网格 ──────────────────────────────────
    print(f"\n→ 读取网格: {args.grid}")
    grid_gdf = gpd.read_file(args.grid)
    print(f"  网格数: {len(grid_gdf)}")

    # ── 读取 POI ──────────────────────────────────
    poi_df = load_poi_data(args.poi_dir)

    # ── 计算评分 ──────────────────────────────────
    print("\n→ 计算等时圈 POI 评分...")
    scores = {30: [], 45: []}
    total = len(grid_gdf)

    for idx_row, row in grid_gdf.iterrows():
        i = grid_gdf.index.get_loc(idx_row)
        if i % 100 == 0:
            print(f"  进度: {i}/{total}")

        centroid = row.geometry.centroid
        cx, cy = centroid.x, centroid.y

        for minute in [30, 45]:
            poly = iso_map.get(i, {}).get(minute, None)
            s = compute_score(poly, cx, cy, poi_df, minute)
            scores[minute].append(s)

    # ── 归一化 ────────────────────────────────────
    print("\n→ 归一化...")
    for minute in [30, 45]:
        arr = np.array(scores[minute], dtype=float)
        grid_gdf[f"iso_score_{minute}m"]      = arr.round(4)
        grid_gdf[f"iso_score_{minute}m_norm"] = percentile_norm(arr)

    # 综合得分：30min 权重 0.6，45min 权重 0.4
    grid_gdf["iso_score_combined"] = (
        0.6 * grid_gdf["iso_score_30m_norm"] +
        0.4 * grid_gdf["iso_score_45m_norm"]
    ).round(2)

    # ── 输出 ─────────────────────────────────────
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    grid_gdf.to_file(args.out, driver="GeoJSON")

    # ── 统计摘要 ──────────────────────────────────
    print(f"\n{'═'*50}")
    print(f"  输出: {args.out}")
    for minute in [30, 45]:
        col = f"iso_score_{minute}m_norm"
        arr = grid_gdf[col].values
        print(f"\n  {minute}min 等时圈评分:")
        print(f"    有效网格 (>0): {(arr>0).sum()} / {total}")
        print(f"    均值: {arr.mean():.1f}  >60分: {(arr>60).sum()}")
    c = grid_gdf["iso_score_combined"].values
    print(f"\n  综合等时圈评分:")
    print(f"    均值: {c.mean():.1f}  >60分: {(c>60).sum()}")
    print(f"{'═'*50}\n")
    print("✓ 完成！下一步运行 isochrone_merge.py\n")


if __name__ == "__main__":
    main()