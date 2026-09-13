"""
add_poi_stats.py
================
给 demand_grid_beijing.geojson 追加各大类POI数量字段
不需要重跑完整preprocess，约3-5分钟完成

新增字段：
  poi_医疗保健, poi_科教文化, poi_购物消费,
  poi_商务住宅, poi_公司企业, poi_生活服务,
  poi_休闲娱乐, poi_运动健身, poi_其他

运行：
  python add_poi_stats.py
"""

import os, json
import numpy as np
import pandas as pd
import geopandas as gpd
import transbigdata as tbd

BASE    = "/Users/aaa/Desktop/MajorThesis/System_build"
POI_FILE  = os.path.join(BASE, "urban-accessibility-rebuild/data/Beijing_fixed.csv")
GRID_FILE = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/data_process/output/demand_grid_beijing.geojson")
PARAMS_FILE = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/data_process/output/grid_params_beijing.json")

# 统计的主要类别（权重≥1.5）
KEY_CATS = ["医疗保健","科教文化","购物消费","商务住宅","公司企业","生活服务","休闲娱乐","运动健身"]

def main():
    print("→ 读取网格和参数...")
    grid_gdf = gpd.read_file(GRID_FILE)
    with open(PARAMS_FILE) as f:
        params = json.load(f)
    print(f"  网格数: {len(grid_gdf)}")

    print("→ 读取POI...")
    poi_df = pd.read_csv(POI_FILE, encoding="utf-8", low_memory=False)
    poi_df["lon"] = pd.to_numeric(poi_df["经度"], errors="coerce")
    poi_df["lat"] = pd.to_numeric(poi_df["纬度"],  errors="coerce")
    poi_df = poi_df.dropna(subset=["lon","lat"])
    print(f"  POI总数: {len(poi_df)}")

    print("→ POI匹配网格...")
    c1, c2, c3 = tbd.GPS_to_grid(poi_df["lon"].values, poi_df["lat"].values, params)
    poi_df["loncol_1"] = c1
    poi_df["loncol_2"] = c2
    poi_df["loncol_3"] = c3

    # 分类统计
    print("→ 分类统计...")
    poi_df["cat"] = poi_df["大类"].apply(lambda x: x if x in KEY_CATS else "其他")

    agg = poi_df.groupby(["loncol_1","loncol_2","loncol_3","cat"]).size().reset_index(name="cnt")
    pivot = agg.pivot_table(
        index=["loncol_1","loncol_2","loncol_3"],
        columns="cat", values="cnt", fill_value=0
    ).reset_index()

    # 合并到网格
    grid_gdf = grid_gdf.merge(pivot, on=["loncol_1","loncol_2","loncol_3"], how="left")

    # 填充空值，重命名列
    all_cats = KEY_CATS + ["其他"]
    for cat in all_cats:
        col = f"poi_{cat}"
        if cat in grid_gdf.columns:
            grid_gdf[col] = grid_gdf[cat].fillna(0).astype(int)
            grid_gdf = grid_gdf.drop(columns=[cat])
        else:
            grid_gdf[col] = 0

    print("→ 保存...")
    grid_gdf.to_file(GRID_FILE, driver="GeoJSON")
    print(f"  ✓ 已更新 {GRID_FILE}")

    # 验证
    sample = grid_gdf[grid_gdf["poi_医疗保健"]>0].iloc[0]
    print(f"\n  样本网格POI分布:")
    for cat in all_cats:
        v = sample.get(f"poi_{cat}", 0)
        if v > 0:
            print(f"    {cat}: {v}")
    print("\n✓ 完成！")

if __name__ == "__main__":
    main()