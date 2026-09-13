"""
compute_tci.py
==============
从采集的原始数据计算TCI指数
输入：tci_raw_data.json
输出：tci_grid_beijing.geojson
"""

import os, json, math
import numpy as np
import pandas as pd
import geopandas as gpd

# ── 配置 ─────────────────────────────────────
BASE     = "/Users/aaa/Desktop/MajorThesis/System_build"
OUT_DIR  = BASE + "/urban-accessibility-rebuild/Back_end/data_process/output"
GRID_FILE = OUT_DIR + "/demand_grid_beijing.geojson"
RAW_FILE  = OUT_DIR + "/tci_raw_data.json"
OUT_FILE  = OUT_DIR + "/tci_grid_beijing.geojson"

# 换乘惩罚系数（分钟/次）
ALPHA = 8.0
# 有效出行时间范围
BUS_MAX = 70.0
CAR_MAX = 30.0

# 东西城边界
EW_LON_MIN, EW_LON_MAX = 116.30, 116.47
EW_LAT_MIN, EW_LAT_MAX = 39.84,  39.98

SESSIONS = ["morning", "midday", "evening"]
SESSION_LABELS = {
    "morning": "早高峰",
    "midday":  "平峰",
    "evening": "晚高峰",
}

def main():
    print("→ 读取原始数据...")
    with open(RAW_FILE, encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    print(f"  总记录: {len(df)} 条")
    print(f"  时段分布: {df['session'].value_counts().to_dict()}")
    print(f"  公交时间有效率: {df['bus_time'].notna().mean()*100:.1f}%")
    print(f"  驾车时间有效率: {df['car_time'].notna().mean()*100:.1f}%")

    # 读取网格
    print("\n→ 读取网格...")
    grid = gpd.read_file(GRID_FILE)
    cx = grid.geometry.centroid.x.values
    cy = grid.geometry.centroid.y.values
    mask = ((cx >= EW_LON_MIN) & (cx <= EW_LON_MAX) &
            (cy >= EW_LAT_MIN) & (cy <= EW_LAT_MAX))
    ew_grid = grid[mask].copy()
    ew_grid["cx"] = cx[mask]
    ew_grid["cy"] = cy[mask]
    print(f"  东西城网格: {len(ew_grid)} 个")

    # 计算TCI
    print("\n→ 计算TCI...")
    for sess in SESSIONS:
        sess_df = df[df["session"] == sess].copy()
        if len(sess_df) == 0:
            print(f"  ⚠ {sess} 无数据，跳过")
            continue

        tci_scores = {}
        for gi, row in ew_grid.iterrows():
            g_data = sess_df[sess_df["grid_idx"] == gi]
            if len(g_data) == 0:
                tci_scores[gi] = np.nan
                continue

            tci_list = []
            for _, r in g_data.iterrows():
                bus_t  = r["bus_time"]
                car_t  = r["car_time"]
                n_trans = r["transfer"] if pd.notna(r["transfer"]) else 0

                # 过滤无效数据
                if pd.isna(bus_t) or pd.isna(car_t): continue
                if bus_t > BUS_MAX or car_t > CAR_MAX: continue
                if bus_t <= 0 or car_t <= 0: continue

                # 换乘惩罚修正
                bus_adj = bus_t + ALPHA * n_trans

                # TCI
                tci = car_t / bus_adj
                tci_list.append(tci)

            tci_scores[gi] = round(np.mean(tci_list), 4) if tci_list else np.nan

        col = f"tci_{sess}"
        ew_grid[col] = ew_grid.index.map(tci_scores)

        valid = ew_grid[col].dropna()
        print(f"  {SESSION_LABELS[sess]}: "
              f"有效网格={len(valid)}  "
              f"均值={valid.mean():.3f}  "
              f"TCI>1(公交有优势)={(valid>1).sum()}  "
              f"TCI<0.5(公交很慢)={(valid<0.5).sum()}")

    # 归一化（可选，用于前端展示）
    for sess in SESSIONS:
        col = f"tci_{sess}"
        if col not in ew_grid.columns: continue
        vals = ew_grid[col].dropna().values
        if len(vals) == 0: continue
        p2, p98 = np.percentile(vals, 2), np.percentile(vals, 98)
        ew_grid[f"tci_{sess}_norm"] = np.round(
            np.clip((ew_grid[col] - p2) / (p98 - p2 + 1e-9), 0, 1) * 100, 2)

    # 综合TCI（三时段平均）
    tci_cols = [f"tci_{s}" for s in SESSIONS if f"tci_{s}" in ew_grid.columns]
    if tci_cols:
        ew_grid["tci_mean"] = ew_grid[tci_cols].mean(axis=1).round(4)
        vals = ew_grid["tci_mean"].dropna()
        print(f"\n  综合TCI: 均值={vals.mean():.3f}  "
              f"最大={vals.max():.3f}  最小={vals.min():.3f}")

    # 保存
    ew_grid.to_file(OUT_FILE, driver="GeoJSON")
    print(f"\n✓ 保存: {OUT_FILE}")
    print(f"  字段: {[c for c in ew_grid.columns if 'tci' in c]}")

if __name__ == "__main__":
    main()