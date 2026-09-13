"""
preprocess_beijing.py
=====================
全北京市公交可达性评价系统 — 数据预处理脚本
覆盖范围：北京市全部16个区

输出文件：
  demand_grid_beijing.geojson   需求密度网格
  bus_lines_beijing.geojson     公交线路
  bus_stops_beijing.geojson     公交站点（前端可视化用）
  bus_stops_beijing_gdf.geojson 公交站点（含线路信息，覆盖度计算用）
  grid_params_beijing.json      网格参数
  summary_beijing.json          统计摘要

运行：
  python preprocess_beijing.py                 # 默认500m精度
  python preprocess_beijing.py --accuracy 200  # 200m精度（较慢）
  python preprocess_beijing.py --skip_grid     # 跳过STEP1-2（断点续跑）
"""

import os, json, math, warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import transbigdata as tbd
import rasterio
from shapely.geometry import Point
from scipy.spatial import cKDTree
warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════
#  路径配置
# ══════════════════════════════════════════════════
BASE     = "/Users/aaa/Desktop/MajorThesis/System_build"
DATA_DIR = os.path.join(BASE, "urban-accessibility-rebuild/data")
OUT_DIR  = os.path.join(BASE, "urban-accessibility-rebuild/Back_end/data_process/output")

POI_FILE   = os.path.join(DATA_DIR, "Beijing_fixed.csv")
ROUTES_SHP = os.path.join(DATA_DIR, "beijing_bus_routes.shp")
STOP_DIR   = os.path.join(BASE, "Data/MajorThesis/bus_stop")
TIF_PATH   = os.path.join(DATA_DIR, "landscan-global-2022-assets/beijing_landscan.tif")

# ══════════════════════════════════════════════════
#  POI大类权重
# ══════════════════════════════════════════════════
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
def gcj02_to_wgs84_arr(lons, lats):
    a = 6378245.0; ee = 0.00669342162296594323; pi = math.pi
    lons = np.array(lons, dtype=float); lats = np.array(lats, dtype=float)
    def tLat(x,y):
        r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*np.sqrt(np.abs(x))
        r+=(20*np.sin(6*x*pi)+20*np.sin(2*x*pi))*2/3
        r+=(20*np.sin(y*pi)+40*np.sin(y/3*pi))*2/3
        r+=(160*np.sin(y/12*pi)+320*np.sin(y*pi/30))*2/3; return r
    def tLon(x,y):
        r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*np.sqrt(np.abs(x))
        r+=(20*np.sin(6*x*pi)+20*np.sin(2*x*pi))*2/3
        r+=(20*np.sin(x*pi)+40*np.sin(x/3*pi))*2/3
        r+=(150*np.sin(x/12*pi)+300*np.sin(x/30*pi))*2/3; return r
    wl, wt = lons.copy(), lats.copy()
    for _ in range(10):
        dlat=tLat(wl-105,wt-35); dlon=tLon(wl-105,wt-35)
        rl=wt/180*pi; mg=np.sin(rl); mg=1-ee*mg*mg; sq=np.sqrt(mg)
        wl-=(wl+(dlon*180)/(a/sq*np.cos(rl)*pi))-lons
        wt-=(wt+(dlat*180)/((a*(1-ee))/(mg*sq)*pi))-lats
    return wl, wt

# ══════════════════════════════════════════════════
#  STEP 1
# ══════════════════════════════════════════════════
def load_beijing_poi(poi_file):
    print(f"→ 读取全量北京POI: {poi_file}")
    df = pd.read_csv(poi_file, encoding="utf-8", low_memory=False)
    print(f"  原始行数: {len(df)}")
    df["lon"] = pd.to_numeric(df["经度"], errors="coerce")
    df["lat"] = pd.to_numeric(df["纬度"], errors="coerce")
    df = df.dropna(subset=["lon","lat"])
    df = df[df["lon"].between(115.4,117.6) & df["lat"].between(39.4,41.1)].copy()
    df["_weight"] = df["大类"].map(POI_WEIGHTS).fillna(DEFAULT_WEIGHT)
    print("  → GCJ-02 转 WGS-84...")
    wl, wt = gcj02_to_wgs84_arr(df["lon"].values, df["lat"].values)
    df["lon_wgs"] = wl; df["lat_wgs"] = wt
    geometry = [Point(x,y) for x,y in zip(df["lon_wgs"],df["lat_wgs"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    keep = ["名称","大类","中类","lon_wgs","lat_wgs","_weight","geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]
    print(f"  清洗后POI: {len(gdf)} 条")
    print(f"  大类分布:\n{gdf['大类'].value_counts().to_string()}")
    return gdf

# ══════════════════════════════════════════════════
#  STEP 2
# ══════════════════════════════════════════════════
def build_beijing_grid(poi_gdf, accuracy, out_dir):
    print(f"\n→ 生成六边形网格（accuracy={accuracy}m）...")
    bounds = (115.40, 39.44, 117.55, 41.06)
    grid, params = tbd.area_to_grid(bounds, accuracy=accuracy, method="hexa")
    print(f"  生成网格数: {len(grid)}")

    print("  → POI匹配网格...")
    poi_df = poi_gdf.copy()
    c1,c2,c3 = tbd.GPS_to_grid(poi_df["lon_wgs"].values, poi_df["lat_wgs"].values, params)
    poi_df["loncol_1"]=c1; poi_df["loncol_2"]=c2; poi_df["loncol_3"]=c3
    agg = poi_df.groupby(["loncol_1","loncol_2","loncol_3"]).agg(
        poi_count=("_weight","count"), demand_raw=("_weight","sum")).reset_index()
    grid = grid.merge(agg, on=["loncol_1","loncol_2","loncol_3"], how="left")
    grid["poi_count"]  = grid["poi_count"].fillna(0)
    grid["demand_raw"] = grid["demand_raw"].fillna(0)
    grid["cx"] = grid.geometry.centroid.x
    grid["cy"] = grid.geometry.centroid.y

    print("  → 高斯邻域平滑（KD-Tree，R=800m，σ=400m）...")
    R=0.0072; sigma=0.0036
    rv=grid["demand_raw"].values; cx=grid["cx"].values; cy=grid["cy"].values
    n=len(grid); coords=np.column_stack([cx,cy]); tree=cKDTree(coords)
    smoothed=np.zeros(n)
    for start in range(0,n,5000):
        if start%20000==0: print(f"    平滑进度: {start}/{n}")
        for j in range(start,min(start+5000,n)):
            idxs=np.array(tree.query_ball_point(coords[j],R))
            if len(idxs)==0: smoothed[j]=rv[j]; continue
            dx=cx[idxs]-cx[j]; dy=cy[idxs]-cy[j]
            w=np.exp(-0.5*((dx**2+dy**2)/sigma**2)); tw=w.sum()
            smoothed[j]=(rv[idxs]*w).sum()/tw if tw>0 else rv[j]

    grid["demand_kde"]=smoothed
    nz=smoothed[smoothed>0]
    if len(nz)>0:
        p2,p98=np.percentile(nz,2),np.percentile(nz,98)
        grid["demand_kde_norm"]=np.round(np.clip((smoothed-p2)/(p98-p2+1e-9),0,1)*100,2)
    else:
        grid["demand_kde_norm"]=0.0
    grid["demand_score"]=grid["demand_kde_norm"]
    print(f"  有POI的网格: {(smoothed>0).sum()} / {n}")

    # 立刻保存
    os.makedirs(out_dir, exist_ok=True)
    grid.to_file(os.path.join(out_dir,"demand_grid_beijing.geojson"), driver="GeoJSON")
    with open(os.path.join(out_dir,"grid_params_beijing.json"),"w") as f:
        json.dump(params, f)
    print("  ✓ 中间结果已保存")
    return grid, params

# ══════════════════════════════════════════════════
#  STEP 3
# ══════════════════════════════════════════════════
def process_bus(routes_shp, stop_dir):
    print("\n→ 读取公交数据...")
    routes_gdf = gpd.read_file(routes_shp)
    if routes_gdf.crs and routes_gdf.crs.to_epsg()!=4326:
        routes_gdf = routes_gdf.to_crs("EPSG:4326")
    print(f"  线路数量: {len(routes_gdf)} 条")

    line_features = []
    for i,row in routes_gdf.iterrows():
        geom=row.geometry
        if geom is None or geom.is_empty: continue
        if geom.geom_type=="LineString": coords=list(geom.coords)
        elif geom.geom_type=="MultiLineString": coords=list(geom.geoms[0].coords)
        else: continue
        line_features.append({"type":"Feature",
            "geometry":{"type":"LineString","coordinates":[[c[0],c[1]] for c in coords]},
            "properties":{"line_id":i}})

    csv_files = sorted([os.path.join(stop_dir,f) for f in os.listdir(stop_dir)
                        if f.startswith("poi-") and f.endswith(".csv")])
    print(f"  找到站点CSV: {len(csv_files)} 个")
    dfs = [pd.read_csv(f, encoding="utf-8") for f in csv_files]
    stops_df = pd.concat(dfs, ignore_index=True)
    stops_df = stops_df.drop_duplicates(subset=["id"]).copy()
    stops_df["lon"] = pd.to_numeric(stops_df["lng_wgs84"], errors="coerce")
    stops_df["lat"] = pd.to_numeric(stops_df["lat_wgs84"], errors="coerce")
    stops_df = stops_df.dropna(subset=["lon","lat"])
    stops_df = stops_df[stops_df["lon"].between(115.4,117.6) &
                        stops_df["lat"].between(39.4,41.1)].copy()
    stops_df["lines"] = stops_df["address"].fillna("").apply(
        lambda x: [l.strip() for l in str(x).split(";") if l.strip()])
    stops_df["line_count"] = stops_df["lines"].apply(len)
    print(f"  去重后站点: {len(stops_df)} 个")

    geometry=[Point(x,y) for x,y in zip(stops_df["lon"],stops_df["lat"])]
    stops_gdf=gpd.GeoDataFrame(stops_df, geometry=geometry, crs="EPSG:4326")
    stop_features=[{"type":"Feature",
        "geometry":{"type":"Point","coordinates":[r["lon"],r["lat"]]},
        "properties":{"name":str(r.get("name","")),"lon":r["lon"],"lat":r["lat"],
                      "line_count":int(r["line_count"]),"lines":";".join(r["lines"][:10])}}
        for _,r in stops_gdf.iterrows()]

    print(f"  ✓ 线路: {len(line_features)} 条，站点: {len(stop_features)} 个")
    return ({"type":"FeatureCollection","features":line_features},
            {"type":"FeatureCollection","features":stop_features}, stops_gdf)

# ══════════════════════════════════════════════════
#  STEP 4
# ══════════════════════════════════════════════════
def process_population(tif_path, grid_gdf):
    print("\n→ 叠加人口栅格...")
    if not os.path.exists(tif_path):
        print(f"  ⚠ 未找到TIF，跳过")
        grid_gdf["population"]=0.0; grid_gdf["pop_norm"]=0.0
        grid_gdf["demand_final"]=grid_gdf.get("demand_kde_norm",0)
        return grid_gdf

    with rasterio.open(tif_path) as src:
        pop=src.read(1).astype(float); nd=src.nodata
        if nd is not None: pop[pop==nd]=0
        pop[pop<0]=0; tf=src.transform; h,w=pop.shape
        print(f"  TIF: {h}×{w}")

    cx=[pt.x for pt in grid_gdf.geometry.centroid]
    cy=[pt.y for pt in grid_gdf.geometry.centroid]
    rows,cols=rasterio.transform.rowcol(tf,cx,cy)
    pv=[float(pop[r,c]) if 0<=r<h and 0<=c<w else 0.0 for r,c in zip(rows,cols)]
    grid_gdf["population"]=pv
    print(f"  有人口值网格: {sum(v>0 for v in pv)} / {len(pv)}")

    pa=np.array(pv); nz=pa[pa>0]
    if len(nz)>0:
        p2,p98=np.percentile(nz,2),np.percentile(nz,98)
        grid_gdf["pop_norm"]=np.round(np.clip((pa-p2)/(p98-p2+1e-9),0,1)*100,2)
    else:
        grid_gdf["pop_norm"]=0.0

    grid_gdf["demand_calibrated"]=(
        0.7*grid_gdf["demand_kde_norm"]+0.3*grid_gdf["pop_norm"]).round(2)
    dm=grid_gdf["demand_calibrated"].min(); dx=grid_gdf["demand_calibrated"].max()
    grid_gdf["demand_final"]=((grid_gdf["demand_calibrated"]-dm)/(dx-dm+1e-9)*100).round(2)
    print(f"  最大人口值: {max(pv):.0f}")
    return grid_gdf

# ══════════════════════════════════════════════════
#  STEP 5
# ══════════════════════════════════════════════════
def save_outputs(grid, lines_gj, stops_gj, stops_gdf, params, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    keep=[c for c in ["loncol_1","loncol_2","loncol_3","poi_count","demand_raw",
        "demand_kde_norm","population","pop_norm","demand_calibrated",
        "demand_final","demand_score","cx","cy","geometry"] if c in grid.columns]
    grid[keep].to_file(os.path.join(out_dir,"demand_grid_beijing.geojson"),driver="GeoJSON")
    print(f"  ✓ demand_grid_beijing.geojson ({len(grid)} 个网格)")
    with open(os.path.join(out_dir,"bus_lines_beijing.geojson"),"w",encoding="utf-8") as f:
        json.dump(lines_gj,f,ensure_ascii=False)
    with open(os.path.join(out_dir,"bus_stops_beijing.geojson"),"w",encoding="utf-8") as f:
        json.dump(stops_gj,f,ensure_ascii=False)
    stops_gdf.to_file(os.path.join(out_dir,"bus_stops_beijing_gdf.geojson"),driver="GeoJSON")
    print(f"  ✓ bus_lines_beijing / bus_stops_beijing")
    with open(os.path.join(out_dir,"grid_params_beijing.json"),"w") as f:
        json.dump(params,f)
    summary={"grid_count":len(grid),
             "poi_total":int(grid["poi_count"].sum()) if "poi_count" in grid.columns else 0,
             "bus_lines":len(lines_gj["features"]),"bus_stops":len(stops_gj["features"]),
             "grid_accuracy":params.get("gridsize",500),"coverage":"全北京16区"}
    with open(os.path.join(out_dir,"summary_beijing.json"),"w") as f:
        json.dump(summary,f,ensure_ascii=False,indent=2)
    print(f"\n{'─'*45}")
    for k,v in summary.items(): print(f"  {k}: {v}")
    print(f"{'─'*45}")

# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--poi",        default=POI_FILE)
    parser.add_argument("--routes_shp", default=ROUTES_SHP)
    parser.add_argument("--stop_dir",   default=STOP_DIR)
    parser.add_argument("--tif",        default=TIF_PATH)
    parser.add_argument("--out",        default=OUT_DIR)
    parser.add_argument("--accuracy",   default=500, type=int)
    parser.add_argument("--skip_grid",  action="store_true",
                        help="跳过STEP1-2，从已保存网格继续")
    args = parser.parse_args()

    print("\n"+"═"*50)
    print("  北京市公交可达性 - 全市数据预处理")
    print(f"  网格精度: {args.accuracy}m")
    print("═"*50+"\n")

    grid_path   = os.path.join(args.out,"demand_grid_beijing.geojson")
    params_path = os.path.join(args.out,"grid_params_beijing.json")

    if args.skip_grid or (os.path.exists(grid_path) and os.path.exists(params_path)):
        print("【STEP 1+2】加载已有需求网格（断点续跑）...")
        grid = gpd.read_file(grid_path)
        with open(params_path) as f: params = json.load(f)
        print(f"  网格数: {len(grid)}")
    else:
        print("【STEP 1】加载全量北京POI")
        poi_gdf = load_beijing_poi(args.poi)
        print("\n【STEP 2】全北京六边形网格化 + 需求密度")
        grid, params = build_beijing_grid(poi_gdf, args.accuracy, args.out)

    print("\n【STEP 3】公交线网数据")
    lines_gj, stops_gj, stops_gdf = process_bus(args.routes_shp, args.stop_dir)

    print("\n【STEP 4】人口栅格叠加")
    grid = process_population(args.tif, grid)

    print("\n【STEP 5】输出结果")
    save_outputs(grid, lines_gj, stops_gj, stops_gdf, params, args.out)

    print("\n✓ 全部完成！")
    print("下一步：运行 coverage_beijing.py 计算覆盖度指标")

if __name__ == "__main__":
    main()