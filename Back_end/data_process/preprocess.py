"""
公交可达性评价系统 - 数据预处理主脚本
功能：
  1. 合并多类型POI CSV文件，分配权重，生成需求密度网格
  2. 处理公交线网Shapefile，提取站点GeoJSON        ← 已从JSON改为SHP
  3. 处理人口栅格TIF，重采样至POI网格分辨率
  4. 输出所有结果为GeoJSON，供前端直接加载

依赖安装（Mac终端运行）：
  pip install transbigdata geopandas rasterio shapely scipy pandas numpy

运行方式：
  python preprocess.py
  
  或指定数据目录：
  python preprocess.py --poi_csv ./data/Beijing_fixed.csv
                       --bus_dir ./data/Beijing
                       --tif ./data/beijing_landscan.tif
"""

import os
import glob
import json
import argparse
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, box as shapely_box
from scipy.stats import gaussian_kde
import transbigdata as tbd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────
#  POI 大类权重表（对应 Beijing_fixed.csv 的"大类"列）
# ─────────────────────────────────────────
POI_WEIGHTS = {
    "医疗保健": 3.0,
    "科教文化": 2.5,
    "商务住宅": 2.0,
    "公司企业": 2.0,
    "休闲娱乐": 1.5,
    "运动健身": 1.5,
    "购物消费": 1.5,
    "金融机构": 1.5,
    "旅游景点": 1.5,
    "生活服务": 1.2,
    "餐饮美食": 1.0,
    "酒店住宿": 1.0,
    "交通设施": 0.5,
    "汽车相关": 0.3,
}
DEFAULT_WEIGHT = 1.0

# 研究范围：东城、西城、海淀、朝阳、丰台、石景山 六区
BBOX = {
    "lon_min": 116.0,
    "lon_max": 116.8,
    "lat_min": 39.7,
    "lat_max": 40.15,
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--poi_csv",
                   default=r"/Users/aaa/Desktop/Beijing_fixed.csv",
                   help="整合后的POI CSV文件路径")
    p.add_argument("--bus_dir",
                   default=r"/Users/aaa/Desktop/CPTOND-2025/dataset/bus/shapefiles/Beijing",
                   help="公交Shapefile所在目录（含beijing_bus_routes.shp等）")
    p.add_argument("--tif",
                   default=r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/landscan-global-2022-assets/beijing_landscan.tif",
                   help="人口栅格TIF文件路径")
    p.add_argument("--out_dir",
                   default=r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output",
                   help="输出目录")
    return p.parse_args()


# ══════════════════════════════════════════
#  STEP 1: POI 数据加载 & 权重分配
#  ← 改为读取单个整合CSV，列名为中文
# ══════════════════════════════════════════

def load_poi_files(poi_csv: str) -> pd.DataFrame:
    """
    读取整合后的 Beijing_fixed.csv。
    列名：名称, 大类, 中类, 经度, 纬度, 省份, 地级市
    根据"大类"列分配权重。
    """
    print(f"→ 读取POI文件: {poi_csv}")
    try:
        df = pd.read_csv(poi_csv, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(poi_csv, encoding="gbk")

    print(f"  原始POI总数: {len(df):,}")

    # 根据大类分配权重
    df["_weight"] = df["大类"].map(POI_WEIGHTS).fillna(DEFAULT_WEIGHT)
    df["_file_type"] = df["大类"]  # 保持与原代码字段名兼容

    # 打印大类分布
    print("  大类分布:")
    for cat, cnt in df["大类"].value_counts().items():
        w = POI_WEIGHTS.get(cat, DEFAULT_WEIGHT)
        print(f"    {cat}: {cnt:,} 条  权重={w}")

    print(f"\n✓ POI 合计: {len(df):,} 条\n")
    return df


def clean_poi(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    字段标准化：
    - 坐标列：经度/纬度（WGS-84）
    - 过滤研究范围外的点
    """
    df = df.copy()

    # 统一列名（兼容中英文）
    if "经度" in df.columns and "纬度" in df.columns:
        df = df.rename(columns={"经度": "lon", "纬度": "lat"})
    elif "lng_wgs84" in df.columns and "lat_wgs84" in df.columns:
        rename_map = {}
        if "wlon" in df.columns:
            rename_map["wlon"] = "lon_gcj"
        if "lat" in df.columns:
            rename_map["lat"] = "lat_gcj"
        df = df.rename(columns=rename_map)
        df = df.rename(columns={"lng_wgs84": "lon", "lat_wgs84": "lat"})
    elif "wlon" in df.columns and "lat" in df.columns:
        df = df.rename(columns={"wlon": "lon"})
    elif "lng" in df.columns and "lat" in df.columns:
        df = df.rename(columns={"lng": "lon"})
    else:
        raise ValueError("找不到坐标列，请检查CSV字段名")

    # 防御性去重列名
    df = df.loc[:, ~df.columns.duplicated()]

    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")

    # 过滤到研究范围（六区bbox）
    mask = (
        df["lon"].between(BBOX["lon_min"], BBOX["lon_max"]) &
        df["lat"].between(BBOX["lat_min"], BBOX["lat_max"])
    )
    dropped = (~mask).sum()
    if dropped > 0:
        print(f"  ⚠ 过滤研究范围外 POI: {dropped:,} 条")
    df = df[mask].dropna(subset=["lon", "lat"])
    print(f"  六区范围内POI: {len(df):,} 条")

    geometry = [Point(xy) for xy in zip(df["lon"], df["lat"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    # 保留核心字段
    keep = ["名称", "大类", "中类", "lon", "lat",
            "_file_type", "_weight", "geometry"]
    keep = [c for c in keep if c in gdf.columns]
    return gdf[keep]


# ══════════════════════════════════════════
#  STEP 2: 六边形网格化 + 需求密度计算
#  ← 与原代码完全一致
# ══════════════════════════════════════════

def build_hex_grid(poi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    用 TransBigData 生成六边形网格，
    统计每格加权POI数量，进行高斯平滑，输出需求密度。
    """
    print("→ 生成六边形网格...")

    lon_min, lat_min, lon_max, lat_max = poi_gdf.total_bounds
    bounds = (lon_min - 0.01, lat_min - 0.01,
              lon_max + 0.01, lat_max + 0.01)

    # 生成六边形网格
    grid, params = tbd.area_to_grid(
        bounds,
        accuracy=200,
        method="hexa"
    )

    # 为每个POI匹配网格ID
    poi_df = poi_gdf.copy()
    c1, c2, c3 = tbd.GPS_to_grid(poi_df["lon"], poi_df["lat"], params)
    poi_df["loncol_1"] = c1
    poi_df["loncol_2"] = c2
    poi_df["loncol_3"] = c3

    # 加权统计
    agg = poi_df.groupby(["loncol_1", "loncol_2", "loncol_3"]).agg(
        poi_count=("_weight", "count"),
        demand_raw=("_weight", "sum")
    ).reset_index()

    # 合并到网格
    grid = grid.merge(agg, on=["loncol_1", "loncol_2", "loncol_3"], how="left")
    grid["poi_count"]  = grid["poi_count"].fillna(0)
    grid["demand_raw"] = grid["demand_raw"].fillna(0)

    # ── 空间平滑（高斯邻域加权均值）────────────────
    print("→ 空间平滑（邻域加权均值）...")

    grid["cx"] = grid.geometry.centroid.x
    grid["cy"] = grid.geometry.centroid.y

    R = 0.008  # 约800m

    raw_vals = grid["demand_raw"].values
    cx_vals  = grid["cx"].values
    cy_vals  = grid["cy"].values
    n = len(grid)

    smoothed = np.zeros(n)
    for i in range(n):
        dx = cx_vals - cx_vals[i]
        dy = cy_vals - cy_vals[i]
        dist = np.sqrt(dx**2 + dy**2)
        w = np.exp(-0.5 * (dist / (R * 0.5))**2)
        w[dist > R] = 0
        total_w = w.sum()
        if total_w > 0:
            smoothed[i] = (raw_vals * w).sum() / total_w
        else:
            smoothed[i] = raw_vals[i]

    grid["demand_kde"] = smoothed

    # ── 百分位截断归一化 ────────────────────────────
    nonzero = smoothed[smoothed > 0]
    if len(nonzero) > 0:
        p_low  = np.percentile(nonzero, 2)
        p_high = np.percentile(nonzero, 98)
    else:
        p_low, p_high = 0, 1

    def percentile_norm(arr):
        normed = np.clip((arr - p_low) / (p_high - p_low + 1e-9), 0, 1) * 100
        return np.round(normed, 2)

    grid["demand_raw_norm"] = percentile_norm(raw_vals)
    grid["demand_kde_norm"] = percentile_norm(smoothed)
    grid["demand_score"]    = grid["demand_kde_norm"]

    print(f"  平滑后非零网格: {(smoothed > 0).sum()} / {n}")
    print(f"  归一化区间: [{p_low:.4f}, {p_high:.4f}]")
    print(f"✓ 网格生成完毕: {len(grid)} 个六边形\n")
    return grid


# ══════════════════════════════════════════
#  STEP 3: 公交线网处理（Shapefile版）
#  ← 此函数为本次核心改动，原JSON解析逻辑已替换
# ══════════════════════════════════════════

def process_bus_shp(bus_dir: str) -> tuple:
    """
    读取公交Shapefile数据，输出与原系统兼容的GeoJSON字典。

    输入文件（均在 bus_dir 目录下）：
      - beijing_bus_routes.shp       线路（LineString，含route_cn等字段）
      - beijing_bus_stops_unique.shp 去重站点（Point，含stop_cn/stop_id/num等字段）

    输出：
      - lines_geojson: dict  与原 process_bus_json() 输出格式相同
      - stops_geojson: dict  与原 process_bus_json() 输出格式相同
    """
    routes_path = os.path.join(bus_dir, "beijing_bus_routes.shp")
    stops_path  = os.path.join(bus_dir, "beijing_bus_stops_unique.shp")

    if not os.path.exists(routes_path):
        raise FileNotFoundError(f"未找到线路文件: {routes_path}")
    if not os.path.exists(stops_path):
        raise FileNotFoundError(f"未找到站点文件: {stops_path}")

    # ── 读取线路 ────────────────────────────────────
    print(f"→ 读取公交线路: {routes_path}")
    routes = gpd.read_file(routes_path)
    print(f"  原始线路总数: {len(routes):,}")

    # 裁剪到研究范围（保留与bbox有交集的线路，含跨区线路）
    study_box = shapely_box(
        BBOX["lon_min"], BBOX["lat_min"],
        BBOX["lon_max"], BBOX["lat_max"]
    )
    routes = routes[routes.geometry.intersects(study_box)].copy()
    print(f"  六区范围线路数: {len(routes):,}")

    # 构造与原代码输出兼容的 GeoJSON features
    line_features = []
    for _, row in routes.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        # 支持 LineString 和 MultiLineString
        if geom.geom_type == "LineString":
            coords = list(geom.coords)
        elif geom.geom_type == "MultiLineString":
            coords = [pt for line in geom.geoms for pt in line.coords]
        else:
            continue

        line_features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[c[0], c[1]] for c in coords]
            },
            "properties": {
                "line_name":   str(row.get("route_cn", "")),
                "route_type":  str(row.get("route_type", "")),
                "city":        str(row.get("city_cn", "北京")),
                "stop_count":  int(row.get("total_stop", 0)) if pd.notna(row.get("total_stop")) else 0,
                "distance":    float(row.get("distance", 0)) if pd.notna(row.get("distance")) else 0.0,
                "start_time":  str(row.get("start_time", "")),
                "end_time":    str(row.get("end_time", "")),
            }
        })

    # ── 读取站点 ────────────────────────────────────
    print(f"→ 读取公交站点: {stops_path}")
    stops = gpd.read_file(stops_path)
    print(f"  原始去重站点总数: {len(stops):,}")

    # 过滤到研究范围
    stops = stops[
        stops.geometry.x.between(BBOX["lon_min"], BBOX["lon_max"]) &
        stops.geometry.y.between(BBOX["lat_min"], BBOX["lat_max"])
    ].copy()
    print(f"  六区范围站点数: {len(stops):,}")

    stop_features = []
    for _, row in stops.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        lon = float(geom.x)
        lat = float(geom.y)
        stop_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "name":       str(row.get("stop_cn", "")),
                "stop_id":    str(row.get("stop_id", "")),
                "lon":        lon,
                "lat":        lat,
                # num字段含义：经过该站的线路数（来自原始数据）
                "line_count": int(row.get("num", 0)) if pd.notna(row.get("num")) else 0,
            }
        })

    lines_geojson = {"type": "FeatureCollection", "features": line_features}
    stops_geojson = {"type": "FeatureCollection", "features": stop_features}

    print(f"✓ 线路: {len(line_features)} 条")
    print(f"✓ 站点: {len(stop_features)} 个（已去重）\n")
    return lines_geojson, stops_geojson


# ══════════════════════════════════════════
#  STEP 4: 人口栅格 TIF 处理
#  ← 与原代码完全一致
# ══════════════════════════════════════════

def process_population_tif(tif_path: str, grid_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    读取人口TIF，将每个网格的人口值叠加到网格属性中，
    用于后续校准需求分数。
    """
    print(f"→ 读取人口栅格: {tif_path}")

    with rasterio.open(tif_path) as src:
        print(f"  TIF CRS: {src.crs}  分辨率: {src.res}  大小: {src.width}x{src.height}")
        print(f"  TIF bounds: {src.bounds}")
        pop_array = src.read(1).astype(float)
        nodata = src.nodata
        if nodata is not None:
            pop_array[pop_array == nodata] = 0
        pop_array[pop_array < 0] = 0
        transform = src.transform
        crs = src.crs

    grid_proj = grid_gdf.copy()
    centroids = grid_proj.geometry.centroid

    if str(crs) != "EPSG:4326":
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        cx = [transformer.transform(pt.x, pt.y)[0] for pt in centroids]
        cy = [transformer.transform(pt.x, pt.y)[1] for pt in centroids]
    else:
        cx = [pt.x for pt in centroids]
        cy = [pt.y for pt in centroids]

    pop_values = []
    rows, cols = rasterio.transform.rowcol(transform, cx, cy)
    h, w = pop_array.shape
    for r, c in zip(rows, cols):
        if 0 <= r < h and 0 <= c < w:
            pop_values.append(float(pop_array[r, c]))
        else:
            pop_values.append(0.0)

    grid_proj["population"] = pop_values

    nonzero_pop = sum(1 for v in pop_values if v > 0)
    print(f"  人口采样：{nonzero_pop} / {len(pop_values)} 个网格有人口值")
    if nonzero_pop == 0:
        print("  ⚠ 警告：人口数据全为0，可能是坐标系不匹配或TIF范围不覆盖研究区域")
        print(f"  网格centroid范围: lon [{min(cx):.3f}, {max(cx):.3f}] lat [{min(cy):.3f}, {max(cy):.3f}]")

    p_min, p_max = min(pop_values), max(pop_values)
    if p_max > p_min:
        grid_proj["pop_norm"] = (
            (grid_proj["population"] - p_min) / (p_max - p_min) * 100
        ).round(2)
    else:
        grid_proj["pop_norm"] = 0.0

    # 需求校准：0.7×kde + 0.3×pop
    grid_proj["demand_calibrated"] = (
        0.7 * grid_proj["demand_kde_norm"] +
        0.3 * grid_proj["pop_norm"]
    ).round(2)

    dmin = grid_proj["demand_calibrated"].min()
    dmax = grid_proj["demand_calibrated"].max()
    if dmax > dmin:
        grid_proj["demand_final"] = (
            (grid_proj["demand_calibrated"] - dmin) / (dmax - dmin) * 100
        ).round(2)
    else:
        grid_proj["demand_final"] = grid_proj["demand_calibrated"]

    print(f"✓ 人口数据叠加完成，最大人口值: {p_max:.1f}\n")
    return grid_proj


# ══════════════════════════════════════════
#  STEP 5: 输出 GeoJSON
#  ← 与原代码完全一致
# ══════════════════════════════════════════

def save_outputs(grid: gpd.GeoDataFrame,
                 lines_geojson: dict,
                 stops_geojson: dict,
                 out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    keep_cols = [c for c in [
        "loncol_1", "loncol_2", "loncol_3",
        "poi_count", "demand_raw",
        "demand_kde_norm", "population", "pop_norm",
        "demand_calibrated", "demand_final", "demand_score",
        "geometry"
    ] if c in grid.columns]
    grid_out = grid[keep_cols].copy()

    grid_path  = os.path.join(out_dir, "demand_grid.geojson")
    lines_path = os.path.join(out_dir, "bus_lines.geojson")
    stops_path = os.path.join(out_dir, "bus_stops.geojson")

    grid_out.to_file(grid_path, driver="GeoJSON")
    print(f"✓ 需求网格 → {grid_path}")

    with open(lines_path, "w", encoding="utf-8") as f:
        json.dump(lines_geojson, f, ensure_ascii=False, indent=2)
    print(f"✓ 公交线路 → {lines_path}")

    with open(stops_path, "w", encoding="utf-8") as f:
        json.dump(stops_geojson, f, ensure_ascii=False, indent=2)
    print(f"✓ 公交站点 → {stops_path}")

    summary = {
        "grid_count":  len(grid_out),
        "poi_total":   int(grid_out["poi_count"].sum()) if "poi_count" in grid_out else 0,
        "demand_max":  float(grid_out["demand_final"].max()) if "demand_final" in grid_out else 0,
        "bus_lines":   len(lines_geojson["features"]),
        "bus_stops":   len(stops_geojson["features"]),
    }
    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"✓ 处理摘要 → {summary_path}")
    print(f"\n{'─'*40}")
    print(f"  网格总数:    {summary['grid_count']:,}")
    print(f"  POI总量:     {summary['poi_total']:,}")
    print(f"  公交线路:    {summary['bus_lines']:,} 条")
    print(f"  公交站点:    {summary['bus_stops']:,} 个")
    print(f"{'─'*40}\n")


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════

def main():
    args = parse_args()
    print("\n" + "═"*45)
    print("  公交可达性系统 - 数据预处理（全北京六区）")
    print("═"*45 + "\n")

    # Step 1: 加载POI
    print("【STEP 1】加载 & 合并 POI 数据")
    poi_raw = load_poi_files(args.poi_csv)
    poi_gdf = clean_poi(poi_raw)
    print(f"  清洗后 POI: {len(poi_gdf):,} 条\n")

    # Step 2: 六边形网格 + 需求密度
    print("【STEP 2】六边形网格化 + 需求密度计算")
    grid = build_hex_grid(poi_gdf)

    # Step 3: 公交数据（Shapefile）
    print("【STEP 3】处理公交线网数据（Shapefile）")
    lines_geojson, stops_geojson = process_bus_shp(args.bus_dir)

    # Step 4: 人口栅格（可选）
    if os.path.exists(args.tif):
        print("【STEP 4】叠加人口栅格数据")
        grid = process_population_tif(args.tif, grid)
    else:
        print(f"【STEP 4】跳过人口栅格（未找到: {args.tif}）")
        grid["demand_final"] = grid["demand_kde_norm"]

    # Step 5: 输出
    print("【STEP 5】写出 GeoJSON 结果")
    save_outputs(grid, lines_geojson, stops_geojson, args.out_dir)

    print("全部完成！\n")


if __name__ == "__main__":
    main()