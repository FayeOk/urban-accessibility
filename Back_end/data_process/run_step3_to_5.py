"""
run_step3_to_5.py
=================
只运行STEP 3-5（公交数据 + 人口叠加 + 输出）
前提：demand_grid_beijing.geojson 和 grid_params_beijing.json 已存在

如果没有这两个文件，先运行：
  python preprocess_beijing.py --accuracy 500
"""

import os, json, glob
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# ── 路径配置（根据实际情况修改）──────────────────
BASE      = "/Users/aaa/Desktop/MajorThesis/System_build"
OUT_DIR   = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/data_process/output")
ROUTES_SHP = os.path.join(BASE, "urban-accessibility-rebuild/data/beijing_bus_routes.shp")
STOP_DIR   = os.path.join(BASE, "Data/MajorThesis/bus_stop")
stop_dir = STOP_DIR  # 变量名统一
TIF_PATH   = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/landscan-global-2022-assets/beijing_landscan.tif")

GRID_PATH   = os.path.join(OUT_DIR, "demand_grid_beijing.geojson")
PARAMS_PATH = os.path.join(OUT_DIR, "grid_params_beijing.json")

# ══════════════════════════════════════════════════
print("=" * 50)
print("  STEP 3-5：公交数据 + 人口叠加 + 输出")
print("=" * 50)

# ── 加载已有网格 ──────────────────────────────────
print("\n→ 加载需求网格...")
if not os.path.exists(GRID_PATH):
    raise FileNotFoundError(f"找不到 {GRID_PATH}，请先运行 preprocess_beijing.py")

grid = gpd.read_file(GRID_PATH)
with open(PARAMS_PATH) as f:
    params = json.load(f)
print(f"  网格数: {len(grid)}")

# ══════════════════════════════════════════════════
# STEP 3: 公交数据
# ══════════════════════════════════════════════════
print("\n【STEP 3】公交线网数据")

# ── 线路（Shapefile）──────────────────────────────
print("→ 读取线路 Shapefile...")
routes_gdf = gpd.read_file(ROUTES_SHP)
if routes_gdf.crs and routes_gdf.crs.to_epsg() != 4326:
    routes_gdf = routes_gdf.to_crs("EPSG:4326")
print(f"  线路数量: {len(routes_gdf)} 条")

line_features = []
for i, row in routes_gdf.iterrows():
    geom = row.geometry
    if geom is None or geom.is_empty:
        continue
    if geom.geom_type == "LineString":
        coords = list(geom.coords)
    elif geom.geom_type == "MultiLineString":
        coords = list(geom.geoms[0].coords)
    else:
        continue
    line_features.append({
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[c[0], c[1]] for c in coords]},
        "properties": {"line_id": i}
    })
print(f"  有效线路: {len(line_features)} 条")

# ── 站点（CSV，含线路信息）────────────────────────
print("→ 读取站点 CSV...")
print("  stop_dir实际值:", stop_dir)
print("  glob pattern:", os.path.join(stop_dir, "poi-*-公交车站.csv"))
csv_files = [
    os.path.join(stop_dir, f) 
    for f in os.listdir(stop_dir) 
    if f.startswith("poi-") and f.endswith(".csv")
]
csv_files = sorted(csv_files)
print("  找到CSV:", len(csv_files))

dfs = []
for f in sorted(csv_files):
    df = pd.read_csv(f, encoding="utf-8")
    dfs.append(df)

stops_df = pd.concat(dfs, ignore_index=True)
print(f"  原始站点: {len(stops_df)}")

# 去重
stops_df = stops_df.drop_duplicates(subset=["id"]).copy()
stops_df["lon"] = pd.to_numeric(stops_df["lng_wgs84"], errors="coerce")
stops_df["lat"] = pd.to_numeric(stops_df["lat_wgs84"], errors="coerce")
stops_df = stops_df.dropna(subset=["lon", "lat"])

# 北京范围过滤
mask = (stops_df["lon"].between(115.4, 117.6)) & (stops_df["lat"].between(39.4, 41.1))
stops_df = stops_df[mask].copy()
print(f"  去重后站点: {len(stops_df)}")

# 解析线路列表
stops_df["lines"] = stops_df["address"].fillna("").apply(
    lambda x: [l.strip() for l in str(x).split(";") if l.strip()]
)
stops_df["line_count"] = stops_df["lines"].apply(len)

# 构建GeoDataFrame
geometry = [Point(x, y) for x, y in zip(stops_df["lon"], stops_df["lat"])]
stops_gdf = gpd.GeoDataFrame(stops_df, geometry=geometry, crs="EPSG:4326")

# 构建GeoJSON
stop_features = []
for _, row in stops_gdf.iterrows():
    stop_features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
        "properties": {
            "name":       str(row.get("name", "")),
            "lon":        row["lon"],
            "lat":        row["lat"],
            "line_count": int(row["line_count"]),
            "lines":      ";".join(row["lines"][:10]),
        }
    })

lines_gj = {"type": "FeatureCollection", "features": line_features}
stops_gj = {"type": "FeatureCollection", "features": stop_features}
print(f"  ✓ 线路: {len(line_features)} 条，站点: {len(stop_features)} 个")

# ══════════════════════════════════════════════════
# STEP 4: 人口栅格叠加
# ══════════════════════════════════════════════════
print("\n【STEP 4】人口栅格叠加")

if os.path.exists(TIF_PATH):
    import rasterio
    with rasterio.open(TIF_PATH) as src:
        pop_array = src.read(1).astype(float)
        nodata = src.nodata
        if nodata is not None:
            pop_array[pop_array == nodata] = 0
        pop_array[pop_array < 0] = 0
        transform = src.transform
        h, w = pop_array.shape
        print(f"  TIF大小: {h}×{w}")

    centroids = grid.geometry.centroid
    cx = [pt.x for pt in centroids]
    cy = [pt.y for pt in centroids]
    rows, cols = rasterio.transform.rowcol(transform, cx, cy)

    pop_values = []
    for r, c in zip(rows, cols):
        pop_values.append(float(pop_array[r, c]) if 0 <= r < h and 0 <= c < w else 0.0)

    grid["population"] = pop_values
    nonzero = sum(1 for v in pop_values if v > 0)
    print(f"  有人口值网格: {nonzero} / {len(pop_values)}")

    pop_arr = np.array(pop_values)
    nz = pop_arr[pop_arr > 0]
    if len(nz) > 0:
        p2, p98 = np.percentile(nz, 2), np.percentile(nz, 98)
        grid["pop_norm"] = np.round(
            np.clip((pop_arr - p2) / (p98 - p2 + 1e-9), 0, 1) * 100, 2)
    else:
        grid["pop_norm"] = 0.0

    # 需求校准
    if "demand_kde_norm" in grid.columns:
        grid["demand_calibrated"] = (
            0.7 * grid["demand_kde_norm"] + 0.3 * grid["pop_norm"]
        ).round(2)
        dmin = grid["demand_calibrated"].min()
        dmax = grid["demand_calibrated"].max()
        grid["demand_final"] = (
            (grid["demand_calibrated"] - dmin) / (dmax - dmin + 1e-9) * 100
        ).round(2)
    else:
        grid["demand_final"] = grid.get("demand_score", grid.get("demand_kde_norm", 0))

    print(f"  最大人口值: {max(pop_values):.0f}")
else:
    print(f"  ⚠ TIF不存在，跳过人口校准")
    grid["population"] = 0.0
    grid["pop_norm"]   = 0.0
    if "demand_kde_norm" in grid.columns:
        grid["demand_final"] = grid["demand_kde_norm"]

# ══════════════════════════════════════════════════
# STEP 5: 输出
# ══════════════════════════════════════════════════
print("\n【STEP 5】输出结果")
os.makedirs(OUT_DIR, exist_ok=True)

# 需求网格（更新版，含人口）
keep = [c for c in [
    "loncol_1","loncol_2","loncol_3",
    "poi_count","demand_raw","demand_kde_norm",
    "population","pop_norm","demand_calibrated",
    "demand_final","demand_score","cx","cy","geometry"
] if c in grid.columns]
grid[keep].to_file(os.path.join(OUT_DIR, "demand_grid_beijing.geojson"), driver="GeoJSON")
print(f"  ✓ demand_grid_beijing.geojson ({len(grid)} 个网格)")

# 公交线路
with open(os.path.join(OUT_DIR, "bus_lines_beijing.geojson"), "w", encoding="utf-8") as f:
    json.dump(lines_gj, f, ensure_ascii=False)
print(f"  ✓ bus_lines_beijing.geojson")

# 公交站点（GeoJSON）
with open(os.path.join(OUT_DIR, "bus_stops_beijing.geojson"), "w", encoding="utf-8") as f:
    json.dump(stops_gj, f, ensure_ascii=False)
print(f"  ✓ bus_stops_beijing.geojson")

# 站点GDF（供覆盖度计算用）
stops_gdf.to_file(os.path.join(OUT_DIR, "bus_stops_beijing_gdf.geojson"), driver="GeoJSON")
print(f"  ✓ bus_stops_beijing_gdf.geojson")

# 网格参数
with open(os.path.join(OUT_DIR, "grid_params_beijing.json"), "w") as f:
    json.dump(params, f)
print(f"  ✓ grid_params_beijing.json")

# 摘要
summary = {
    "grid_count":    len(grid),
    "poi_total":     int(grid["poi_count"].sum()) if "poi_count" in grid.columns else 0,
    "bus_lines":     len(line_features),
    "bus_stops":     len(stop_features),
    "grid_accuracy": params.get("gridsize", 500),
    "coverage":      "全北京16区",
}
with open(os.path.join(OUT_DIR, "summary_beijing.json"), "w") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n{'─'*45}")
for k, v in summary.items():
    print(f"  {k}: {v}")
print(f"{'─'*45}")
print("\n✓ 全部完成！")
print("下一步: 运行 coverage_beijing.py 计算覆盖度指标")