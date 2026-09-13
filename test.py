import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.font_manager as fm
from matplotlib.colorbar import ColorbarBase # 用于添加需求密度色带
import warnings
warnings.filterwarnings("ignore")

# --- 1. 路径与字体配置 (完全保留你的原始设置) ---
FONT_PATHS = ["/System/Library/Fonts/PingFang.ttc","/System/Library/Fonts/STHeiti Light.ttc"]
cn_font = None
for fp in FONT_PATHS:
    try:
        cn_font = fm.FontProperties(fname=fp); cn_font.get_name(); break
    except: continue
if cn_font is None: cn_font = fm.FontProperties()
matplotlib.rcParams['axes.unicode_minus'] = False

BASE      = "/Users/aaa/Desktop/MajorThesis/System_build"
GRID_FILE = BASE + "/urban-accessibility-rebuild/Back_end/data_process/output/demand_grid_beijing.geojson"

EW_LON_MIN, EW_LON_MAX = 116.30, 116.47
EW_LAT_MIN, EW_LAT_MAX = 39.84,  39.98

DESTINATIONS = [
    ("D01", 116.22, 39.98), ("D02", 116.28, 40.02), ("D03", 116.42, 40.02),
    ("D04", 116.52, 40.00), ("D05", 116.56, 39.93), ("D06", 116.52, 39.86),
    ("D07", 116.42, 39.80), ("D08", 116.32, 39.80), ("D09", 116.22, 39.86),
    ("D10", 116.20, 39.93), ("D11", 116.26, 39.94), ("D12", 116.38, 39.99),
    ("D13", 116.48, 39.97), ("D14", 116.48, 39.88), ("D15", 116.38, 39.85),
    ("D16", 116.30, 39.88), ("D17", 116.36, 39.92),
]

# --- 2. 数据读取 (严格使用你的原始路径) ---
grid = gpd.read_file(GRID_FILE)
cx = grid.geometry.centroid.x; cy = grid.geometry.centroid.y
grid_vis = grid[cx.between(116.14,116.64)&cy.between(39.73,40.10)].copy()

# --- 3. 绘图与美化 ---
fig, ax = plt.subplots(figsize=(10, 8), dpi=150) # 稍微加宽给右侧色带留空间
fig.patch.set_facecolor('white')
ax.set_facecolor('white') # 干净的白色背景

# 颜色映射：使用更具现代感的渐变
colors = ["#e0f3f8", "#fee090", "#f46d43", "#a50026"] 
cmap_d = LinearSegmentedColormap.from_list('d_modern', colors, N=256)

# 绘制需求密度底图
vmin, vmax = 0, 100
if 'demand_final' in grid_vis.columns:
    grid_vis.plot(ax=ax, column='demand_final', cmap=cmap_d, alpha=0.7, 
                  edgecolor='none', vmin=vmin, vmax=vmax, zorder=1)

# --- 4. 核心新增：需求密度色带 (Colorbar) ---
cax = fig.add_axes([0.91, 0.25, 0.02, 0.50]) # 设置色带位置 [左, 下, 宽, 高]
cb = ColorbarBase(cax, cmap=cmap_d, norm=matplotlib.colors.Normalize(vmin=vmin, vmax=vmax))
cb.set_label('潜在出行需求密度', fontproperties=cn_font, fontsize=10, labelpad=10)
cb.set_ticks([vmin + 5, vmax - 5])
cb.set_ticklabels(['低', '高'], fontproperties=cn_font, fontsize=9)

# --- 5. 核心新增：现代感指北针 ---
ax.annotate('', xy=(116.61, 40.08), xytext=(116.61, 40.04),
            arrowprops=dict(arrowstyle='-|>', color='#333', lw=1.5, mutation_scale=15), zorder=10)
ax.text(116.61, 40.085, 'N', ha='center', va='bottom', fontsize=11, fontweight='bold')

# --- 6. 核心优化：研究区域边框与目的地散点 ---
# 研究区域边框
rect = Rectangle((EW_LON_MIN,EW_LAT_MIN),EW_LON_MAX-EW_LON_MIN,EW_LAT_MAX-EW_LAT_MIN,
                 linewidth=1.2, edgecolor='#1a5fa8', facecolor='none', linestyle='-', alpha=0.7, zorder=6)
ax.add_patch(rect)

# 目的地散点：加大并改用深蓝+白字对比，更清晰
for did,lon,lat in DESTINATIONS:
    num = int(did[1:])
    ax.scatter(lon, lat, s=160, c='#104E8B', zorder=12, edgecolors='white', linewidths=1.2)
    ax.text(lon, lat, str(num), fontsize=8, ha='center', va='center',
            color='white', fontweight='bold', zorder=13)

# --- 7. 比例尺、图例与坐标轴 (保留原始参数并优化) ---
# 比例尺设计
sl, sb, slen = 116.165, 39.75, 0.045
ax.plot([sl, sl+slen], [sb, sb], '-', color='#333', lw=2.0, zorder=10)
ax.plot([sl, sl], [sb, sb+0.003], '-', color='#333', lw=2.0)
ax.plot([sl+slen, sl+slen], [sb, sb+0.003], '-', color='#333', lw=2.0)
ax.text(sl+slen/2, sb+0.008, '5 km', ha='center', va='bottom', fontsize=9, fontweight='bold')

# 图例
legend_elements = [
    mpatches.Patch(facecolor='none', edgecolor='#1a5fa8', linestyle='-', linewidth=1.5, label='研究区域'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#104E8B', markersize=10, 
               markeredgecolor='white', label='服务中心目的地'),
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=9, framealpha=0.9, prop=cn_font)

# 坐标轴格式
ax.set_xlim(116.14, 116.64); ax.set_ylim(39.73, 40.10)
ax.set_xlabel('经度 (°E)', fontproperties=cn_font, fontsize=10)
ax.set_ylabel('纬度 (°N)', fontproperties=cn_font, fontsize=10)
xt = np.arange(116.2, 116.64, 0.1); yt = np.arange(39.75, 40.10, 0.05)
ax.set_xticks(xt); ax.set_yticks(yt)
ax.set_xticklabels([f'{x:.1f}°' for x in xt], fontsize=8.5)
ax.set_yticklabels([f'{y:.2f}°' for y in yt], fontsize=8.5)
ax.grid(True, linestyle=':', linewidth=0.4, color='#ccc', alpha=0.6, zorder=0)

ax.set_title('图3-X  公共交通竞争力评价服务中心目的地分布',
             fontproperties=cn_font, fontsize=12, pad=15, fontweight='bold')

plt.tight_layout(rect=[0, 0, 0.90, 1]) # 留出空间给右侧色带
plt.savefig('/Users/aaa/Downloads/fig_dest_check_v2.png', dpi=250, bbox_inches='tight')
print("✓ 优化后的图表已保存至 /Users/aaa/Downloads/fig_dest_check_v2.png")