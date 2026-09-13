"""
公交可达性评价系统 - 数据预处理主脚本
功能：
  1. 合并多类型POI CSV文件，分配权重，生成需求密度网格
  2. 处理公交线网JSON，提取站点GeoJSON
  3. 处理人口栅格TIF，重采样至POI网格分辨率
  4. 输出所有结果为GeoJSON，供前端直接加载

依赖安装（Mac终端运行）：
  pip install transbigdata geopandas rasterio shapely scipy pandas numpy

运行方式：
  python preprocess.py
  
  或指定数据目录：
  python preprocess.py --poi_dir ./data/poi --bus_json ./data/bus.json --tif ./data/beijing_landscan.tif
"""

import os
import glob
import json
import argparse
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, shape
from scipy.stats import gaussian_kde
import transbigdata as tbd
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────
#  POI 类型权重表（参考功能描述文档）
#  key: 文件名中的类型关键词  value: 需求权重
# ─────────────────────────────────────────
POI_WEIGHTS = {
    "餐饮服务":       1.5,
    "购物服务":       2.0,
    "医疗保健服务":   3.0,
    "科教文化服务":   2.5,
    "住宅区":         2.0,
    "商务住宅":       1.8,
    "公司企业":       2.0,
    "交通设施服务":   1.0,
    "体育休闲服务":   1.5,
    "生活服务":       1.5,
    "金融保险服务":   1.2,
    "政府机构及社会团体": 1.8,
    "风景名胜":       1.0,
    "住宿服务":       1.2,
    "汽车服务":       0.8,
    "汽车维修":       0.6,
    "汽车销售":       0.6,
    "摩托车服务":     0.4,
}

# 六边形网格参数（单位：度，约500m）
HEX_ACCURACY = 7          # H3 分辨率等级（transbigdata用整数精度参数）
GRID_CELL_SIZE = 0.005    # 备用方形网格边长（度），约500m

# 核密度估计带宽（米转度，约600m）
KDE_BANDWIDTH = 0.003  # 约300m，匹配200m网格尺寸


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--poi_dir",  default=r"/Users/aaa/Desktop/Major Thesis/System_build/Data/MajorThesis/poi/poi_data",
                   help="POI CSV文件所在目录（含东城+西城所有分类文件）")
    p.add_argument("--bus_json", default=r"/Users/aaa/Desktop/Major Thesis/System_build/Data/MajorThesis/bus_data/json_lines",
                   help="公交线网JSON文件路径")
    p.add_argument("--tif",      default=r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/landscan-global-2022-assets/beijing_landscan.tif",
                   help="人口栅格TIF文件路径")
    p.add_argument("--out_dir",  default=r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output",
                   help="输出目录")
    return p.parse_args()


# ══════════════════════════════════════════
#  STEP 1: POI 数据合并 & 权重分配
# ══════════════════════════════════════════

def load_poi_files(poi_dir: str) -> pd.DataFrame:
    """
    读取目录下所有 poi-*.csv 文件，
    根据文件名中的类型关键词分配权重。
    """
    csv_files = glob.glob(os.path.join(poi_dir, "poi-*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"未在 {poi_dir} 找到 poi-*.csv 文件")

    dfs = []
    for fp in csv_files:
        # 从文件名提取类型，例如 poi-110101-住宅区.csv → 住宅区
        base = os.path.basename(fp)
        parts = base.replace(".csv", "").split("-")
        poi_type_label = parts[-1] if len(parts) >= 3 else "未知"

        # 匹配权重
        weight = 1.0
        for key, w in POI_WEIGHTS.items():
            if key in poi_type_label:
                weight = w
                break

        try:
            df = pd.read_csv(fp, encoding="utf-8", sep=None, engine="python")
        except Exception:
            df = pd.read_csv(fp, encoding="gbk", sep=None, engine="python")

        df["_file_type"] = poi_type_label
        df["_weight"] = weight
        dfs.append(df)
        print(f"  加载: {base}  ({len(df)} 条)  权重={weight}")

    combined = pd.concat(dfs, ignore_index=True)
    print(f"\n✓ POI 合计: {len(combined)} 条，来自 {len(csv_files)} 个文件\n")
    return combined


def clean_poi(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    字段标准化：
    - 坐标优先使用 lng_wgs84/lat_wgs84（WGS84，更精确）
    - 原始数据同时含 lat 和 lat_wgs84，需先重命名原始列再 rename wgs84列
    - 去除坐标异常行
    """
    df = df.copy()

    if "lng_wgs84" in df.columns and "lat_wgs84" in df.columns:
        # 原始数据同时有 wlon/lat（GCJ-02）和 lng_wgs84/lat_wgs84（WGS84）
        # 先把原始 GCJ-02 列改名，避免 rename 后出现重复列名导致 Series 变 DataFrame
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

    # 防御性去重（防止任何残留的重复列名）
    df = df.loc[:, ~df.columns.duplicated()]

    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")

    # 过滤北京范围外的点（粗过滤）
    mask = (df["lon"].between(115.4, 117.5)) & (df["lat"].between(39.4, 41.0))
    dropped = (~mask).sum()
    if dropped > 0:
        print(f"  ⚠ 过滤坐标异常 POI: {dropped} 条")
    df = df[mask].dropna(subset=["lon", "lat"])

    geometry = [Point(xy) for xy in zip(df["lon"], df["lat"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    # 保留核心字段
    keep = ["name", "type", "typecode", "type1", "type2", "type3",
            "address", "lon", "lat", "_file_type", "_weight", "geometry"]
    keep = [c for c in keep if c in gdf.columns]
    return gdf[keep]


# ══════════════════════════════════════════
#  STEP 2: 六边形网格化 + 需求密度计算
# ══════════════════════════════════════════

def build_hex_grid(poi_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    用 TransBigData 生成六边形网格，
    统计每格加权POI数量，进行KDE平滑，输出需求密度。
    """
    print("→ 生成六边形网格...")

    lon_min, lat_min, lon_max, lat_max = poi_gdf.total_bounds
    # 稍微扩大边界
    bounds = (lon_min - 0.01, lat_min - 0.01,
              lon_max + 0.01, lat_max + 0.01)

    # 生成六边形网格
    grid, params = tbd.area_to_grid(
        bounds,
        accuracy=200,        # 网格大小（米）—— 东西城区面积小，200m更合适
        method="hexa"        # 六边形
    )

    # 为每个POI匹配网格ID
    # 六边形网格用 loncol_1/loncol_2/loncol_3 三列作为联合ID
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

    # ── KDE 平滑 ──────────────────────────
    # 用 demand_raw（加权POI计数）直接做网格级平滑，不用点级KDE
    # 原因：点级KDE带宽难以覆盖整个区域，导致大量网格KDE=0
    print("→ 空间平滑（邻域加权均值）...")
    import warnings
    warnings.filterwarnings("ignore")

    # 计算每个网格的centroid
    grid["cx"] = grid.geometry.centroid.x
    grid["cy"] = grid.geometry.centroid.y

    # 以每个网格为中心，统计半径R内所有网格的demand_raw加权均值
    # R约为800m ≈ 0.0072度（纬度方向），用于平滑需求分布
    R = 0.008  # 度，约800m

    raw_vals = grid["demand_raw"].values
    cx_vals  = grid["cx"].values
    cy_vals  = grid["cy"].values
    n = len(grid)

    smoothed = np.zeros(n)
    for i in range(n):
        dx = cx_vals - cx_vals[i]
        dy = cy_vals - cy_vals[i]
        dist = np.sqrt(dx**2 + dy**2)
        # 高斯衰减权重
        w = np.exp(-0.5 * (dist / (R * 0.5))**2)
        w[dist > R] = 0
        total_w = w.sum()
        if total_w > 0:
            smoothed[i] = (raw_vals * w).sum() / total_w
        else:
            smoothed[i] = raw_vals[i]

    grid["demand_kde"] = smoothed

    # ── 百分位截断归一化（避免极值拉崩分布）──────────────────
    # 取非零值的 2% ~ 98% 作为归一化区间
    nonzero = smoothed[smoothed > 0]
    if len(nonzero) > 0:
        p_low  = np.percentile(nonzero, 2)
        p_high = np.percentile(nonzero, 98)
    else:
        p_low, p_high = 0, 1

    def percentile_norm(arr):
        normed = np.clip((arr - p_low) / (p_high - p_low + 1e-9), 0, 1) * 100
        return np.round(normed, 2)

    grid["demand_raw_norm"]  = percentile_norm(raw_vals)
    grid["demand_kde_norm"]  = percentile_norm(smoothed)

    # 最终需求分数
    grid["demand_score"] = grid["demand_kde_norm"]

    print(f"  平滑后非零网格: {(smoothed > 0).sum()} / {n}")
    print(f"  归一化区间: [{p_low:.4f}, {p_high:.4f}]")

    print(f"✓ 网格生成完毕: {len(grid)} 个六边形\n")
    return grid


# ══════════════════════════════════════════
#  STEP 3: 公交线网 JSON 处理
# ══════════════════════════════════════════

def process_bus_json(bus_json_path: str):
    """
    解析公交JSON，分别输出：
    - 线路 GeoJSON (LineString)
    - 站点 GeoJSON (Point，去重)
    
    兼容两种输入：
    1. 单个JSON文件（列表或单对象）
    2. 目录（遍历目录下所有 .json 文件）
    """
    # 判断是目录还是文件
    if os.path.isdir(bus_json_path):
        json_files = glob.glob(os.path.join(bus_json_path, "*.json"))
        if not json_files:
            raise FileNotFoundError(f"目录 {bus_json_path} 下没有找到 .json 文件")
        print(f"→ 读取公交JSON目录: {bus_json_path}（共 {len(json_files)} 个文件）")
        lines_data = []
        for fp in json_files:
            with open(fp, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                lines_data.extend(raw)
            else:
                lines_data.append(raw)
    else:
        print(f"→ 读取公交JSON: {bus_json_path}")
        with open(bus_json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        lines_data = raw if isinstance(raw, list) else [raw]

    line_features = []
    stop_dict = {}   # 用于站点去重，key = stationnames

    for line in lines_data:
        line_name = line.get("full_line_name") or line.get("query_keyword", "未知线路")
        city      = line.get("city", "")

        # ── 线路 ──
        path = line.get("path", [])
        if path and len(path) >= 2:
            # path 是 [[lon,lat], [lon,lat], ...]
            coords = [[p[0], p[1]] for p in path if len(p) >= 2]
            line_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {
                    "line_name": line_name,
                    "city": city,
                    "stop_count": len(line.get("stops", []))
                }
            })

        # ── 站点 ──
        for stop in line.get("stops", []):
            sname = stop.get("stationnames", "")
            lon   = stop.get("lon")
            lat   = stop.get("lat")
            if sname and lon and lat:
                if sname not in stop_dict:
                    stop_dict[sname] = {
                        "name": sname,
                        "lon": lon,
                        "lat": lat,
                        "lines": [line_name]
                    }
                else:
                    # 追加经过该站的线路名
                    if line_name not in stop_dict[sname]["lines"]:
                        stop_dict[sname]["lines"].append(line_name)

    # 站点转 GeoJSON
    stop_features = []
    for s in stop_dict.values():
        stop_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["lon"], s["lat"]]
            },
            "properties": {
                "name":       s["name"],
                "lon":        s["lon"],
                "lat":        s["lat"],
                "line_count": len(s["lines"]),
                "lines":      ", ".join(s["lines"][:10])  # 最多显示10条
            }
        })

    lines_geojson = {"type": "FeatureCollection", "features": line_features}
    stops_geojson = {"type": "FeatureCollection", "features": stop_features}

    print(f"✓ 线路: {len(line_features)} 条")
    print(f"✓ 站点: {len(stop_features)} 个（去重后）\n")
    return lines_geojson, stops_geojson


# ══════════════════════════════════════════
#  STEP 4: 人口栅格 TIF 处理
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
        # 负值也清零（LandScan有时用-9999表示无数据）
        pop_array[pop_array < 0] = 0
        transform = src.transform
        crs = src.crs

    # 为每个网格中心点采样人口值
    grid_proj = grid_gdf.copy()
    centroids = grid_proj.geometry.centroid

    # 转换网格坐标到TIF坐标系（如果不同）
    if str(crs) != "EPSG:4326":
        import pyproj
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        cx = [transformer.transform(pt.x, pt.y)[0] for pt in centroids]
        cy = [transformer.transform(pt.x, pt.y)[1] for pt in centroids]
    else:
        cx = [pt.x for pt in centroids]
        cy = [pt.y for pt in centroids]

    # 采样（行列坐标）
    pop_values = []
    rows, cols = rasterio.transform.rowcol(transform, cx, cy)
    h, w = pop_array.shape
    for r, c in zip(rows, cols):
        if 0 <= r < h and 0 <= c < w:
            pop_values.append(float(pop_array[r, c]))
        else:
            pop_values.append(0.0)

    grid_proj["population"] = pop_values

    # 调试：检查采样结果
    nonzero_pop = sum(1 for v in pop_values if v > 0)
    print(f"  人口采样：{nonzero_pop} / {len(pop_values)} 个网格有人口值")
    if nonzero_pop == 0:
        print("  ⚠ 警告：人口数据全为0，可能是坐标系不匹配或TIF范围不覆盖研究区域")
        print(f"  网格centroid范围: lon [{min(cx):.3f}, {max(cx):.3f}] lat [{min(cy):.3f}, {max(cy):.3f}]")

    # 人口归一化
    p_min, p_max = min(pop_values), max(pop_values)
    if p_max > p_min:
        grid_proj["pop_norm"] = (
            (grid_proj["population"] - p_min) / (p_max - p_min) * 100
        ).round(2)
    else:
        grid_proj["pop_norm"] = 0.0

    # ── 人口校准需求分数 ──────────────────────
    # 公式：calibrated = 0.7 * demand_kde_norm + 0.3 * pop_norm
    # 目的：抑制郊区POI多但人口少的噪声
    grid_proj["demand_calibrated"] = (
        0.7 * grid_proj["demand_kde_norm"] +
        0.3 * grid_proj["pop_norm"]
    ).round(2)

    # 重新归一化校准分数
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
# ══════════════════════════════════════════

def save_outputs(grid: gpd.GeoDataFrame,
                 lines_geojson: dict,
                 stops_geojson: dict,
                 out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    # 网格：只保留关键属性列
    keep_cols = [c for c in [
        "loncol_1", "loncol_2", "loncol_3",
        "poi_count", "demand_raw",
        "demand_kde_norm", "population", "pop_norm",
        "demand_calibrated", "demand_final", "demand_score",
        "geometry"
    ] if c in grid.columns]
    grid_out = grid[keep_cols].copy()

    # 输出 GeoJSON
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

    # 输出统计摘要
    summary = {
        "grid_count": len(grid_out),
        "poi_total": int(grid_out["poi_count"].sum()) if "poi_count" in grid_out else 0,
        "demand_max": float(grid_out["demand_final"].max()) if "demand_final" in grid_out else 0,
        "bus_lines": len(lines_geojson["features"]),
        "bus_stops": len(stops_geojson["features"]),
    }
    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"✓ 处理摘要 → {summary_path}")
    print(f"\n{'─'*40}")
    print(f"  网格总数:    {summary['grid_count']}")
    print(f"  POI总量:     {summary['poi_total']}")
    print(f"  公交线路:    {summary['bus_lines']} 条")
    print(f"  公交站点:    {summary['bus_stops']} 个")
    print(f"{'─'*40}\n")


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════

def main():
    args = parse_args()
    print("\n" + "═"*45)
    print("  公交可达性系统 - 数据预处理")
    print("═"*45 + "\n")

    # Step 1: 加载POI
    print("【STEP 1】加载 & 合并 POI 数据")
    poi_raw = load_poi_files(args.poi_dir)
    poi_gdf = clean_poi(poi_raw)
    print(f"  清洗后 POI: {len(poi_gdf)} 条\n")

    # Step 2: 六边形网格 + 需求密度
    print("【STEP 2】六边形网格化 + 需求密度计算")
    grid = build_hex_grid(poi_gdf)

    # Step 3: 公交数据
    print("【STEP 3】处理公交线网数据")
    lines_geojson, stops_geojson = process_bus_json(args.bus_json)

    # Step 4: 人口栅格（可选，文件不存在则跳过）
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