"""
fix_population_calibration.py
==============================
只重算 pop_norm 和 demand_final，不重跑完整 preprocess
约2-3分钟完成

运行：
  python fix_population_calibration.py
"""

import os
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import rowcol

BASE      = "/Users/aaa/Desktop/MajorThesis/System_build"
GRID_FILE = BASE + "/urban-accessibility-rebuild/Back_end/data_process/output/demand_grid_beijing.geojson"
TIF_PATH  = BASE + "/urban-accessibility-rebuild/Back_end/landscan-global-2022-assets/beijing_landscan.tif"
OUT_FILE  = GRID_FILE  # 原地覆盖

print("→ 检查文件...")
assert os.path.exists(GRID_FILE), f"网格文件不存在: {GRID_FILE}"
assert os.path.exists(TIF_PATH),  f"TIF文件不存在: {TIF_PATH}"
print(f"  网格: {GRID_FILE}")
print(f"  TIF:  {TIF_PATH}")

print("\n→ 读取网格...")
grid = gpd.read_file(GRID_FILE)
print(f"  网格数: {len(grid)}")

cx = grid["cx"].values
cy = grid["cy"].values

print("\n→ 读取人口栅格...")
with rasterio.open(TIF_PATH) as src:
    tf = src.transform
    data = src.read(1).astype(float)
    nodata = src.nodata
    print(f"  栅格尺寸: {data.shape}")
    print(f"  NoData值: {nodata}")

    rows, cols = rowcol(tf, cx, cy)
    rows = np.clip(rows, 0, data.shape[0] - 1)
    cols = np.clip(cols, 0, data.shape[1] - 1)
    pv = data[rows, cols]

    if nodata is not None:
        pv[pv == nodata] = 0.0
    pv = np.maximum(pv, 0.0)

grid["population"] = np.round(pv, 2)
print(f"  人口非零网格: {(pv > 0).sum()} 个")
print(f"  人口均值（非零）: {pv[pv > 0].mean():.1f}")

print("\n→ 计算 pop_norm...")
pa = pv.copy()
nz = pa[pa > 0]
if len(nz) > 0:
    p2  = np.percentile(nz, 2)
    p98 = np.percentile(nz, 98)
    grid["pop_norm"] = np.round(
        np.clip((pa - p2) / (p98 - p2 + 1e-9), 0, 1) * 100, 2)
    print(f"  P2={p2:.1f}  P98={p98:.1f}")
else:
    grid["pop_norm"] = 0.0
    print("  ⚠ 人口数据全为零，pop_norm 设为 0")

print("\n→ 重算 demand_calibrated 和 demand_final...")
alpha = 0.7
grid["demand_calibrated"] = (
    alpha * grid["demand_kde_norm"] +
    (1 - alpha) * grid["pop_norm"]
).round(2)

dm = grid["demand_calibrated"].min()
dx = grid["demand_calibrated"].max()
grid["demand_final"] = (
    (grid["demand_calibrated"] - dm) / (dx - dm + 1e-9) * 100
).round(2)

print(f"  demand_final 均值: {grid['demand_final'].mean():.2f}")
print(f"  demand_final 非零: {(grid['demand_final'] > 0).sum()} 个")

# 验证差异
diff = grid["demand_final"] - grid["demand_kde_norm"]
print(f"\n  与校准前的差异:")
print(f"    差值均值:      {diff.mean():.4f}")
print(f"    差值标准差:    {diff.std():.4f}")
print(f"    |差值|>0.5:   {(diff.abs() > 0.5).sum()} 个网格")
print(f"    校准后增加:    {(diff > 0.5).sum()} 个")
print(f"    校准后减少:    {(diff < -0.5).sum()} 个")

print(f"\n→ 保存...")
grid.to_file(OUT_FILE, driver="GeoJSON")
print(f"  ✓ 已保存: {OUT_FILE}")
print("\n✓ 完成！建议重新复制到 public/data/output/ 并刷新前端。")