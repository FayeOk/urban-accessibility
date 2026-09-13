# 数据预处理脚本说明

## 目录结构要求


## 安装依赖

```bash
pip install transbigdata geopandas rasterio shapely scipy pandas numpy pyproj
```

## 运行方式

```bash
# 使用默认路径（推荐，按上面目录结构放置数据）
python preprocess.py

# 或者手动指定路径
python preprocess.py \
  --poi_dir ./data/poi \
  --bus_json ./data/bus_lines.json \
  --tif ./data/beijing_landscan.tif \
  --out_dir ./data/output
```

## 输出文件说明

| 文件 | 说明 |
|------|------|
| `demand_grid.geojson` | 六边形网格，含每格需求分数（0-100），直接供前端热力图使用 |
| `bus_lines.geojson` | 公交线路（LineString），含线路名和站点数 |
| `bus_stops.geojson` | 公交站点（Point，去重），含站点名和经过线路列表 |
| `summary.json` | 处理统计摘要 |

## 网格属性字段说明

| 字段 | 说明 |
|------|------|
| `poi_count` | 网格内 POI 数量（未加权） |
| `demand_raw` | 网格内加权 POI 总分 |
| `demand_kde_norm` | KDE 平滑后归一化需求分 [0,100] |
| `population` | 人口栅格采样值 |
| `pop_norm` | 归一化人口分 [0,100] |
| `demand_final` | 最终需求分（人口校准后，0-100），用于供需比计算 |

## 后续步骤

预处理完成后，下一步是在前端 MapContainer.jsx 中加载 demand_grid.geojson 并用 Mapbox/Leaflet 渲染六边形热力图，以及计算覆盖度指标（网格中心点到最近公交站距离）。
