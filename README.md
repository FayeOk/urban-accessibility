# Urban Accessibility Rebuild

城市公交可达性评估系统（Urban Accessibility Analysis System）。

本项目面向“公交服务是否匹配城市需求”的综合评估，输出三类核心空间指标：

- `Demand`：需求密度（POI + 人口校准）
- `Isochrone`：公交等时圈可达性（30/45min）
- `Coverage`：覆盖度（步行便捷度 + 线路多样性）

---

## 1. 系统定位

系统分为两个互补部分：

- `离线计算引擎（Back_end/data_process）`
- `在线可视化交互界面（React + DeckGL）`

离线引擎负责多源数据融合与指标计算；前端负责地图交互、图层控制、指标解释和结果展示。

---

## 2. 总体技术架构

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                          Data Source Layer                               │
│  POI CSV / Bus JSON / LandScan TIF / AMap Isochrone API                 │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                        Offline Processing Layer                          │
│  preprocess.py  -> demand_grid + lines + stops                           │
│  isochrone fetch -> isochrone_30/45 raw                                  │
│  isochrone_score.py -> isochrone_grid                                    │
│  Coverage.py -> coverage_grid                                             │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          Data Serving Layer                              │
│  public/data/output/*.geojson + summary.json                              │
└───────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         Frontend Application Layer                        │
│  MainPage -> SidebarPanel + MapContainer                                  │
│  DeckGL GeoJsonLayer rendering + tooltip + legend                         │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 工程架构（现状实现）

> 下面是当前仓库中已经落地的结构。

```text
urban-accessibility-rebuild/
├── Back_end/
│   ├── data_process/
│   │   ├── preprocess.py
│   │   ├── isochrone_fetch_puppeteer.js
│   │   ├── isochrone_AmapJS.py
│   │   ├── isochrone_score.py
│   │   ├── Coverage.py
│   │   ├── README.md
│   │   └── output/
│   └── landscan-global-2022-assets/
├── public/
│   ├── index.html
│   ├── favicon.ico
│   └── data/output/
├── src/
│   ├── components/
│   │   ├── Map/MapContainer.jsx
│   │   └── Sidebar/
│   │       ├── SidebarPanel.jsx
│   │       ├── DataUpload.jsx
│   │       └── AnalysisPanel.jsx
│   ├── pages/MainPage.jsx
│   ├── styles/
│   ├── App.jsx
│   └── index.jsx
├── package.json
├── config-overrides.js
└── README.md
```

---

## 4. 目标完整架构（建议形态）

> 这是你给出的更完整工程分层，我保留为“目标架构蓝图”，方便后续迭代对齐。

```text
urban-accessibility-rebuild/
├── public/
│   ├── index.html
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── Map/
│   │   │   ├── MapContainer.jsx
│   │   │   ├── HexagonLayer.jsx
│   │   │   ├── BusRouteLayer.jsx
│   │   │   └── DrawTool.jsx
│   │   ├── Sidebar/
│   │   │   ├── DataUpload.jsx
│   │   │   ├── AnalysisPanel.jsx
│   │   │   └── ResultsPanel.jsx
│   │   ├── UI/
│   │   │   ├── HexagonGridControls.jsx
│   │   │   └── BusRouteControls.jsx
│   │   └── Algorithm/
│   │       ├── AccessibilityWorker.js
│   │       └── GraphUtils.js
│   ├── pages/
│   │   └── MainPage.jsx
│   ├── utils/
│   │   ├── hexagon.js
│   │   ├── busDataParser.js
│   │   ├── accessibility.js
│   │   └── fileHandler.js
│   ├── hooks/
│   │   ├── useMapData.js
│   │   └── useAccessibility.js
│   ├── App.jsx
│   ├── index.jsx
│   └── styles/
│       ├── App.css
│       └── index.css
├── package.json
├── config-overrides.js
└── README.md
```

---

## 5. 前端架构详解

### 5.1 页面编排层

- `MainPage.jsx` 负责全局状态编排。
- 左侧 `SidebarPanel` 负责输入与控制。
- 右侧 `MapContainer` 负责可视化输出。

### 5.2 交互控制层

- `DataUpload`：导入 GeoJSON、清空视图。
- `AnalysisPanel`：图层开关（demand/isochrone/coverage/lines/stops）。
- 目标扩展可加入 `ResultsPanel` 展示统计结果与导出能力。

### 5.3 地图渲染层

- 基于 `react-map-gl + deck.gl`。
- 每个指标一个 `GeoJsonLayer`。
- tooltip 展示网格属性、站点属性。
- 图例由激活图层动态驱动。

### 5.4 目标可演进层（建议）

- 将 `MapContainer` 拆分为：
  - `HexagonLayer`
  - `BusRouteLayer`
  - `StopLayer`
  - `DrawTool`
- 将复杂计算迁移至 `WebWorker`，避免主线程卡顿。
- 通过 `hooks` 管理数据与分析状态，减少页面耦合。

---

## 6. 后端数据处理架构详解

### 6.1 preprocess.py（基础网格构建）

输入：

- POI CSV（多分类）
- 公交线网 JSON
- 人口栅格 TIF

处理：

- POI 合并与权重映射
- 200m 六边形网格化
- 空间平滑与归一化
- 人口采样校准（形成 `demand_final`）
- 公交线路与站点结构化

输出：

- `demand_grid.geojson`
- `bus_lines.geojson`
- `bus_stops.geojson`
- `summary.json`

### 6.2 isochrone 处理链

采集层：

- `isochrone_fetch_puppeteer.js`（自动化采集）
- 或 `isochrone_AmapJS.py`（生成浏览器控制台脚本）

评分层：

- `isochrone_score.py`
- 计算 `iso_score_30m_norm`
- 计算 `iso_score_45m_norm`
- 融合 `iso_score_combined`

输出：

- `isochrone_grid.geojson`

### 6.3 Coverage.py（覆盖度）

计算维度：

- 最近站点距离 `nearest_stop_m`
- 步行便捷度 `walk_score`
- 500m 线路多样性 `diversity_score`
- 综合覆盖度 `coverage_score`

输出：

- `coverage_grid.geojson`

---

## 7. 关键数据契约（Data Contract）

### 7.1 demand_grid.geojson

核心字段：

- `poi_count`
- `demand_raw`
- `demand_kde_norm`
- `population`
- `pop_norm`
- `demand_final`

### 7.2 isochrone_grid.geojson

在 demand 字段基础上增加：

- `iso_score_30m`
- `iso_score_30m_norm`
- `iso_score_45m`
- `iso_score_45m_norm`
- `iso_score_combined`

### 7.3 coverage_grid.geojson

在 demand 字段基础上增加：

- `nearest_stop_m`
- `walk_score`
- `line_count_500m`
- `diversity_score`
- `coverage_score`

---

## 8. 指标计算流程（端到端）

```text
POI/公交/人口数据
  -> preprocess.py
  -> demand_grid + lines + stops
  -> isochrone fetch (30/45min)
  -> isochrone_score.py
  -> isochrone_grid
  -> Coverage.py
  -> coverage_grid
  -> public/data/output
  -> 前端多图层可视化
```

---

## 9. 本地运行

### 9.1 前端

```bash
npm install
npm start
```

### 9.2 Python 处理依赖

```bash
pip install transbigdata geopandas rasterio shapely scipy pandas numpy pyproj
```

### 9.3 等时圈采集依赖

```bash
npm install puppeteer
```

### 9.4 推荐执行顺序

```bash
python Back_end/data_process/preprocess.py
node Back_end/data_process/isochrone_fetch_puppeteer.js
python Back_end/data_process/isochrone_score.py
python Back_end/data_process/Coverage.py
```

---

## 10. 当前数据规模（依据现有 summary.json）

- `grid_count`: 1462
- `poi_total`: 75323
- `bus_lines`: 3967
- `bus_stops`: 17383

---

## 11. 架构演进建议

- 从“单组件集中渲染”演进到“图层组件化渲染”。
- 从“页面本地状态”演进到“hooks + worker 分层状态”。
- 从“脚本手动串行执行”演进到“一键 pipeline（Makefile/npm scripts）”。
- 从“本地文件发布”演进到“API/对象存储版本化数据发布”。

