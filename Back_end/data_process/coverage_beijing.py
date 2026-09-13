"""
coverage_beijing.py
===================
全北京覆盖度指标计算脚本

指标1 — 步行便捷度 walk_score [0,100]
  网格中心到最近公交站Haversine距离：
  ≤300m → 100分，300~800m → 线性衰减，>800m → 0分

指标2 — 线路多样性 diversity_score [0,100]
  500m半径内不重复线路数，95分位归一化

综合覆盖度 coverage_score = 0.6×walk_score + 0.4×diversity_score

运行：
  python coverage_beijing.py
"""

import os, json, argparse
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from scipy.spatial import cKDTree

# ── 路径配置 ──────────────────────────────────────
BASE    = "/Users/aaa/Desktop/MajorThesis/System_build"
OUT_DIR = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/data_process/output")

DEFAULT_GRID  = os.path.join(OUT_DIR, "demand_grid_beijing.geojson")
DEFAULT_STOPS = os.path.join(OUT_DIR, "bus_stops_beijing_gdf.geojson")
DEFAULT_OUT   = os.path.join(OUT_DIR, "coverage_grid_beijing.geojson")

WALK_FULL   = 300   # 米：满分
WALK_MAX    = 800   # 米：0分
DIVERSITY_R = 500   # 米：线路多样性半径

# ── 参数 ─────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--grid",  default=DEFAULT_GRID)
    p.add_argument("--stops", default=DEFAULT_STOPS)
    p.add_argument("--out",   default=DEFAULT_OUT)
    return p.parse_args()

# ── Haversine距离（米）────────────────────────────
def haversine(lon1, lat1, lon2, lat2):
    R = 6371000
    p1,p2 = radians(lat1), radians(lat2)
    dp = radians(lat2-lat1); dl = radians(lon2-lon1)
    a = sin(dp/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

# ── 经纬度距离近似转换（用于KD-Tree半径查询）────
# 1度纬度≈111000m，1度经度≈111000*cos(lat)m
# 北京纬度约40°，cos(40°)≈0.766，1度经度≈85000m
# 取保守值：500m ≈ 0.005度（纬度），0.006度（经度）
# 统一用度为单位的KD-Tree，半径用度
def meters_to_deg(meters, lat=40.0):
    lat_deg = meters / 111000
    lon_deg = meters / (111000 * cos(radians(lat)))
    return max(lat_deg, lon_deg)  # 取较大值保证覆盖

def main():
    args = parse_args()

    print("\n" + "═"*50)
    print("  全北京覆盖度指标计算")
    print("═"*50 + "\n")

    # ── 读取网格 ──────────────────────────────────
    print(f"→ 读取需求网格: {args.grid}")
    with open(args.grid, encoding="utf-8") as f:
        grid_gj = json.load(f)
    grid_features = grid_gj["features"]
    n = len(grid_features)
    print(f"  网格数: {n}")

    # 提取网格中心点
    grid_lons, grid_lats = [], []
    for feat in grid_features:
        g = feat["geometry"]
        if g["type"] == "Polygon":
            ring = g["coordinates"][0]
            grid_lons.append(sum(p[0] for p in ring)/len(ring))
            grid_lats.append(sum(p[1] for p in ring)/len(ring))
        else:
            grid_lons.append(g["coordinates"][0])
            grid_lats.append(g["coordinates"][1])
    grid_lons = np.array(grid_lons)
    grid_lats = np.array(grid_lats)

    # ── 读取站点 ──────────────────────────────────
    print(f"→ 读取公交站点: {args.stops}")
    with open(args.stops, encoding="utf-8") as f:
        stops_gj = json.load(f)
    stops_feats = stops_gj["features"]
    print(f"  站点数: {len(stops_feats)}")

    stop_lons, stop_lats, stop_lines = [], [], []
    for feat in stops_feats:
        g = feat["geometry"]
        p = feat.get("properties", {})
        stop_lons.append(g["coordinates"][0])
        stop_lats.append(g["coordinates"][1])
        # 线路信息：lines字段（分号分隔字符串）
        lines_str = p.get("lines", "") or p.get("address", "")
        lines_list = [l.strip() for l in str(lines_str).split(";") if l.strip()]
        stop_lines.append(lines_list)

    stop_lons = np.array(stop_lons)
    stop_lats = np.array(stop_lats)

    # ── 构建KD-Tree（用经纬度坐标，加cos修正）────
    print("→ 构建空间索引...")
    mean_lat = np.mean(grid_lats)
    cos_lat  = cos(radians(mean_lat))

    # 坐标缩放：经度乘以cos(lat)使经纬度单位统一
    stop_coords  = np.column_stack([stop_lons * cos_lat, stop_lats])
    grid_coords  = np.column_stack([grid_lons * cos_lat, grid_lats])
    stop_tree    = cKDTree(stop_coords)

    # 度→米的转换系数（查询半径用）
    deg_per_meter = 1.0 / 111000

    # ── 计算步行便捷度（最近站距离）──────────────
    print("→ 计算步行便捷度（walk_score）...")

    # KD-Tree查最近站（用度，查询半径=WALK_MAX）
    r_deg = WALK_MAX * deg_per_meter * 1.2  # 留20%余量
    dists_deg, idxs = stop_tree.query(grid_coords, k=1)

    walk_scores = np.zeros(n)
    for i in range(n):
        if idxs[i] >= len(stop_lons):
            walk_scores[i] = 0.0
            continue
        # 精确Haversine距离（米）
        dist_m = haversine(grid_lons[i], grid_lats[i],
                           stop_lons[idxs[i]], stop_lats[idxs[i]])
        if dist_m <= WALK_FULL:
            walk_scores[i] = 100.0
        elif dist_m <= WALK_MAX:
            walk_scores[i] = round((WALK_MAX - dist_m) / (WALK_MAX - WALK_FULL) * 100, 2)
        else:
            walk_scores[i] = 0.0

    print(f"  walk_score: 均值={walk_scores.mean():.1f}, "
          f">0的网格: {(walk_scores>0).sum()}/{n}")

    # ── 计算线路多样性（500m内不重复线路数）──────
    print("→ 计算线路多样性（diversity_score）...")
    r_div_deg = DIVERSITY_R * deg_per_meter * 1.2

    diversity_counts = np.zeros(n)
    batch = 2000
    for start in range(0, n, batch):
        if start % 10000 == 0:
            print(f"  多样性进度: {start}/{n}")
        end = min(start+batch, n)
        for i in range(start, end):
            idxs_near = stop_tree.query_ball_point(grid_coords[i], r_div_deg)
            if not idxs_near:
                diversity_counts[i] = 0
                continue
            # 精确过滤（Haversine）
            unique_lines = set()
            for si in idxs_near:
                dist_m = haversine(grid_lons[i], grid_lats[i],
                                   stop_lons[si], stop_lats[si])
                if dist_m <= DIVERSITY_R:
                    unique_lines.update(stop_lines[si])
            diversity_counts[i] = len(unique_lines)

    # 95分位归一化
    nz_div = diversity_counts[diversity_counts > 0]
    if len(nz_div) > 0:
        p95 = np.percentile(nz_div, 95)
        diversity_scores = np.round(
            np.clip(diversity_counts / p95, 0, 1) * 100, 2)
    else:
        diversity_scores = np.zeros(n)

    print(f"  diversity_score: 均值={diversity_scores.mean():.1f}, "
          f"95分位线路数={p95:.0f}")

    # ── 综合覆盖度 ────────────────────────────────
    coverage_scores = np.round(0.6*walk_scores + 0.4*diversity_scores, 2)
    print(f"  coverage_score: 均值={coverage_scores.mean():.1f}")

    # ── 写出结果 ──────────────────────────────────
    print(f"\n→ 写出结果: {args.out}")
    for i, feat in enumerate(grid_features):
        p = feat.setdefault("properties", {})
        p["walk_score"]       = float(walk_scores[i])
        p["diversity_score"]  = float(diversity_scores[i])
        p["diversity_count"]  = int(diversity_counts[i])
        p["coverage_score"]   = float(coverage_scores[i])

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(grid_gj, f, ensure_ascii=False)

    print(f"  ✓ 输出: {n} 个网格")
    print(f"\n{'─'*45}")
    print(f"  网格总数:      {n}")
    print(f"  有步行覆盖:    {(walk_scores>0).sum()} ({(walk_scores>0).sum()/n*100:.1f}%)")
    print(f"  有线路覆盖:    {(diversity_counts>0).sum()} ({(diversity_counts>0).sum()/n*100:.1f}%)")
    print(f"  平均覆盖度分:  {coverage_scores.mean():.1f}")
    print(f"{'─'*45}")
    print("\n✓ 完成！下一步运行 competition_beijing.py 计算公交竞争力指标")

if __name__ == "__main__":
    main()