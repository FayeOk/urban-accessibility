"""
公交可达性评价系统 - 覆盖度指标计算脚本
============================================
计算两个静态覆盖度指标（无需API，全部本地计算）：

指标1 — 步行便捷度得分 walk_score [0, 100]
  网格中心点到最近公交站的直线距离，按衰减函数转换为得分：
  - ≤300m：满分 100
  - 300~800m：线性衰减
  - >800m：0 分（超出可接受步行圈）

指标2 — 供给多样性得分 diversity_score [0, 100]
  500m 半径内不重复线路总数，归一化到 [0,100]

综合覆盖度得分 coverage_score = 0.6×walk_score + 0.4×diversity_score

输出：coverage_grid.geojson（六边形网格 + 上述三个得分字段）

运行：
  python coverage.py
"""

import os
import json
import argparse
import numpy as np
from math import radians, sin, cos, sqrt, atan2

# ── 路径配置（与 preprocess.py 保持一致）──────────────────
DEFAULT_GRID   = r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output/demand_grid.geojson"
DEFAULT_STOPS  = r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output/bus_stops.geojson"
DEFAULT_LINES  = r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output/bus_lines.geojson"
DEFAULT_OUT    = r"/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output/coverage_grid.geojson"

# ── 参数 ─────────────────────────────────────────────────
WALK_FULL   = 300   # 米：满分步行距离
WALK_MAX    = 800   # 米：0分步行距离（超出即不可达）
DIVERSITY_R = 500   # 米：统计线路多样性的半径


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--grid",  default=DEFAULT_GRID)
    p.add_argument("--stops", default=DEFAULT_STOPS)
    p.add_argument("--lines", default=DEFAULT_LINES)
    p.add_argument("--out",   default=DEFAULT_OUT)
    return p.parse_args()


# ══════════════════════════════════════════
#  地理工具函数
# ══════════════════════════════════════════

def haversine(lon1, lat1, lon2, lat2) -> float:
    """返回两点间距离（米），Haversine公式"""
    R = 6371000
    φ1, φ2 = radians(lat1), radians(lat2)
    dφ = radians(lat2 - lat1)
    dλ = radians(lon2 - lon1)
    a = sin(dφ/2)**2 + cos(φ1)*cos(φ2)*sin(dλ/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def centroid(geometry: dict):
    """从 GeoJSON geometry 取中心点 (lon, lat)"""
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Point":
        return coords[0], coords[1]
    elif gtype == "Polygon":
        ring = coords[0]
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
        return lon, lat
    elif gtype == "MultiPolygon":
        # 取第一个多边形
        ring = coords[0][0]
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
        return lon, lat
    else:
        raise ValueError(f"不支持的几何类型: {gtype}")


# ══════════════════════════════════════════
#  得分函数
# ══════════════════════════════════════════

def walk_score(dist_m: float) -> float:
    """步行距离 → [0,100] 得分，线性衰减"""
    if dist_m <= WALK_FULL:
        return 100.0
    elif dist_m >= WALK_MAX:
        return 0.0
    else:
        return round(100 * (WALK_MAX - dist_m) / (WALK_MAX - WALK_FULL), 2)


# ══════════════════════════════════════════
#  主计算流程
# ══════════════════════════════════════════

def main():
    args = parse_args()

    # ── 读取数据 ──────────────────────────
    print("→ 读取网格数据...")
    with open(args.grid, encoding="utf-8") as f:
        grid_gj = json.load(f)
    grid_features = grid_gj["features"]
    print(f"  网格数量: {len(grid_features)}")

    print("→ 读取公交站点数据...")
    with open(args.stops, encoding="utf-8") as f:
        stops_gj = json.load(f)
    stops = stops_gj["features"]
    print(f"  站点数量: {len(stops)}")

    # 预处理站点：提取坐标 + 线路列表
    stop_coords = []   # [(lon, lat), ...]
    stop_lines  = []   # [set(line_names), ...]
    for s in stops:
        p = s["properties"]
        lon = p.get("lon") or s["geometry"]["coordinates"][0]
        lat = p.get("lat") or s["geometry"]["coordinates"][1]
        lines_str = p.get("lines", "")
        lines_set = set(x.strip() for x in lines_str.split(",") if x.strip())
        stop_coords.append((float(lon), float(lat)))
        stop_lines.append(lines_set)

    stop_lons = np.array([c[0] for c in stop_coords])
    stop_lats = np.array([c[1] for c in stop_coords])

    # ── 计算每个网格的覆盖度指标 ──────────
    print("→ 计算覆盖度指标（步行距离 + 线路多样性）...")

    walk_scores      = []
    diversity_scores = []
    nearest_dists    = []
    line_counts      = []

    total = len(grid_features)
    for i, feat in enumerate(grid_features):
        if i % 200 == 0:
            print(f"  进度: {i}/{total}")

        lon, lat = centroid(feat["geometry"])

        # ── 指标1：到最近站点的步行距离 ──
        # 用经纬度差作快速粗筛（省去对所有站点做haversine）
        # 0.008度≈800m，超出这个范围直接排除
        dlat = np.abs(stop_lats - lat)
        dlon = np.abs(stop_lons - lon)
        candidates = np.where((dlat < 0.012) & (dlon < 0.012))[0]

        if len(candidates) == 0:
            # 没有附近站点，回退到全量搜索
            candidates = np.arange(len(stop_coords))

        min_dist = float("inf")
        nearest_idx = -1
        for idx in candidates:
            d = haversine(lon, lat, stop_lons[idx], stop_lats[idx])
            if d < min_dist:
                min_dist = d
                nearest_idx = idx

        ws = walk_score(min_dist)
        walk_scores.append(ws)
        nearest_dists.append(round(min_dist, 1))

        # ── 指标2：500m内不重复线路数 ──
        # 同样先粗筛
        r_deg = DIVERSITY_R / 111000  # 度，粗估
        candidates2 = np.where(
            (dlat < r_deg * 1.5) & (dlon < r_deg * 1.5)
        )[0]

        all_lines = set()
        for idx in candidates2:
            d = haversine(lon, lat, stop_lons[idx], stop_lats[idx])
            if d <= DIVERSITY_R:
                all_lines |= stop_lines[idx]

        line_counts.append(len(all_lines))
        diversity_scores.append(len(all_lines))

    # ── 多样性得分归一化 ──────────────────
    # 取 95 分位数作为满分基准（避免极值拉崩）
    lc_arr = np.array(diversity_scores)
    p95 = np.percentile(lc_arr[lc_arr > 0], 95) if (lc_arr > 0).any() else 1
    div_norm = np.clip(lc_arr / p95, 0, 1) * 100
    div_norm = np.round(div_norm, 2)

    # ── 综合覆盖度得分 ────────────────────
    ws_arr = np.array(walk_scores)
    coverage = np.round(0.6 * ws_arr + 0.4 * div_norm, 2)

    # ── 写入 GeoJSON ──────────────────────
    print("→ 写出 coverage_grid.geojson...")
    out_features = []
    for i, feat in enumerate(grid_features):
        new_feat = {
            "type": "Feature",
            "geometry": feat["geometry"],
            "properties": {
                # 保留原有属性
                **feat["properties"],
                # 新增覆盖度字段
                "nearest_stop_m":  nearest_dists[i],
                "walk_score":      walk_scores[i],
                "line_count_500m": line_counts[i],
                "diversity_score": float(div_norm[i]),
                "coverage_score":  float(coverage[i]),
            }
        }
        out_features.append(new_feat)

    out_gj = {"type": "FeatureCollection", "features": out_features}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_gj, f, ensure_ascii=False)

    # ── 统计摘要 ──────────────────────────
    print(f"\n{'─'*45}")
    print(f"  输出文件:          {args.out}")
    print(f"  网格总数:          {total}")
    print(f"\n  步行便捷度（walk_score）:")
    print(f"    满分(=100)网格:  {(ws_arr == 100).sum()} ({(ws_arr==100).mean()*100:.1f}%)")
    print(f"    0分网格:         {(ws_arr == 0).sum()} ({(ws_arr==0).mean()*100:.1f}%)")
    print(f"    均值:            {ws_arr.mean():.1f}")
    print(f"\n  最近站点距离（米）:")
    nd = np.array(nearest_dists)
    print(f"    ≤300m 网格:      {(nd<=300).sum()} ({(nd<=300).mean()*100:.1f}%)")
    print(f"    300~800m 网格:   {((nd>300)&(nd<=800)).sum()}")
    print(f"    >800m 网格:      {(nd>800).sum()}")
    print(f"    均值/最大值:     {nd.mean():.0f}m / {nd.max():.0f}m")
    print(f"\n  线路多样性（500m内线路数）:")
    print(f"    中位数:          {int(np.median(lc_arr))} 条")
    print(f"    最大值:          {int(lc_arr.max())} 条")
    print(f"    95分位基准:      {p95:.1f} 条")
    print(f"\n  综合覆盖度（coverage_score）:")
    print(f"    均值:            {coverage.mean():.1f}")
    print(f"    >80分网格:       {(coverage>80).sum()} ({(coverage>80).mean()*100:.1f}%)")
    print(f"    <40分网格:       {(coverage<40).sum()} ({(coverage<40).mean()*100:.1f}%)")
    print(f"{'─'*45}\n")
    print("✓ 覆盖度计算完成！\n")


if __name__ == "__main__":
    main()