"""
plot_final_destinations.py
17个目的地：框内5个（深红）+ 框外12个（深蓝）
"""
import geopandas as gpd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.font_manager as fm
import warnings
warnings.filterwarnings("ignore")

# ── 字体 ─────────────────────────────────────
FONT_PATHS = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode MS.ttf",
]
cn_font = None
for fp in FONT_PATHS:
    try:
        cn_font = fm.FontProperties(fname=fp)
        cn_font.get_name(); break
    except: continue
if cn_font is None:
    cn_font = fm.FontProperties()
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 路径 ─────────────────────────────────────
BASE      = "/Users/aaa/Desktop/MajorThesis/System_build"
GRID_FILE = BASE + "/urban-accessibility-rebuild/Back_end/data_process/output/demand_grid_beijing.geojson"
OUT_PNG   = "/Users/aaa/Downloads/fig_final_destinations.png"
OUT_PDF   = "/Users/aaa/Downloads/fig_final_destinations.pdf"

EW_LON_MIN, EW_LON_MAX = 116.30, 116.47
EW_LAT_MIN, EW_LAT_MAX = 39.84,  39.98

# ── 框内5个目的地（深红）─────────────────────
INNER = [
    ("D01", 116.3975, 39.9093, "天安门"),
    ("D02", 116.3744, 39.9136, "西单"),
    ("D03", 116.4074, 39.9145, "王府井"),
    ("D04", 116.4277, 39.9027, "北京站"),
    ("D05", 116.3951, 39.9390, "鼓楼"),
]

# ── 框外12个目的地（深蓝）────────────────────
OUTER = [
    ("D06", 116.32, 40.00),
    ("D07", 116.32, 39.98),
    ("D08", 116.28, 39.96),
    ("D09", 116.36, 39.98),
    ("D10", 116.40, 39.98),
    ("D11", 116.48, 39.98),
    ("D12", 116.46, 39.90),
    ("D13", 116.52, 39.92),
    ("D14", 116.40, 39.84),
    ("D15", 116.50, 39.86),
    ("D16", 116.28, 39.82),
    ("D17", 116.24, 39.88),
]

# ── 加载网格 ─────────────────────────────────
print("加载网格...")
grid = gpd.read_file(GRID_FILE)
cx = grid.geometry.centroid.x
cy = grid.geometry.centroid.y
XMIN, XMAX = 116.16, 116.62
YMIN, YMAX = 39.77, 40.08
grid_vis = grid[cx.between(XMIN,XMAX) & cy.between(YMIN,YMAX)].copy()

# ── 绘图 ─────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 8), dpi=150)
fig.patch.set_facecolor('white')
ax.set_facecolor('#f7f4f0')

# 1. 需求密度底图
cmap_d = LinearSegmentedColormap.from_list(
    'demand', ['#fef0e6','#fdc89a','#f4722b','#b83200'], N=256)
if 'demand_final' in grid_vis.columns:
    grid_vis.plot(ax=ax, column='demand_final', cmap=cmap_d,
                  alpha=0.55, edgecolor='none', vmin=0, vmax=100)
else:
    grid_vis.plot(ax=ax, color='#ede8e0', edgecolor='none')

# 2. 东西城边界框
rect = Rectangle((EW_LON_MIN, EW_LAT_MIN),
                  EW_LON_MAX-EW_LON_MIN, EW_LAT_MAX-EW_LAT_MIN,
                  linewidth=2.0, edgecolor='#1a5fa8',
                  facecolor='#1a5fa808', linestyle=(0,(6,3)), zorder=6)
ax.add_patch(rect)

# 3. 框内目的地（深红实心圆）
for did, lon, lat, name in INNER:
    num = int(did[1:])
    ax.scatter(lon, lat, s=105, c='#8B0000', zorder=12,
               edgecolors='white', linewidths=1.0)
    ax.text(lon, lat, str(num), fontsize=6.5, ha='center', va='center',
            color='white', fontweight='bold', zorder=13)

# 4. 框外目的地（深蓝实心圆）
for did, lon, lat in OUTER:
    num = int(did[1:])
    ax.scatter(lon, lat, s=105, c='#1a3a6b', zorder=12,
               edgecolors='white', linewidths=1.0)
    ax.text(lon, lat, str(num), fontsize=6.5, ha='center', va='center',
            color='white', fontweight='bold', zorder=13)

# 5. 指北针
ax.annotate('', xy=(116.585, 40.052), xytext=(116.585, 40.032),
            arrowprops=dict(arrowstyle='->', color='#222', lw=1.8))
ax.text(116.585, 40.055, 'N', ha='center', va='bottom',
        fontsize=10, fontweight='bold', color='#222')

# 6. 比例尺
sl, sb, slen = 116.18, 39.785, 0.045
ax.plot([sl, sl+slen], [sb, sb], '-', color='#333', lw=2.5, zorder=10)
for x in [sl, sl+slen]:
    ax.plot([x,x],[sb-0.003,sb+0.003],'-',color='#333',lw=1.5)
ax.text(sl+slen/2, sb-0.008, '≈5 km', ha='center', va='top', fontsize=8)

# 7. 颜色条
if 'demand_final' in grid_vis.columns:
    sm = plt.cm.ScalarMappable(cmap=cmap_d, norm=plt.Normalize(0,100))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.22, pad=0.015,
                        aspect=14, anchor=(1.0,0.1))
    cbar.set_label('需求密度', fontproperties=cn_font,
                   fontsize=9, labelpad=8, rotation=270, va='bottom')
    cbar.set_ticks([0,50,100])
    cbar.set_ticklabels(['低','中','高'])
    cbar.ax.tick_params(labelsize=8)
    for lb in cbar.ax.get_yticklabels():
        lb.set_fontproperties(cn_font)

# 8. 图例
legend_elements = [
    mpatches.Patch(facecolor='none', edgecolor='#1a5fa8',
                   linestyle='--', linewidth=2.0,
                   label='研究区域（东城区、西城区）'),
    plt.Line2D([0],[0], marker='o', color='w', markerfacecolor='#8B0000',
               markersize=9, markeredgecolor='white', markeredgewidth=1,
               label='区域内服务中心（5处）'),
    plt.Line2D([0],[0], marker='o', color='w', markerfacecolor='#1a3a6b',
               markersize=9, markeredgecolor='white', markeredgewidth=1,
               label='区域外服务中心（12处）'),
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=8.5,
          framealpha=0.92, edgecolor='#ccc', prop=cn_font,
          borderpad=0.8, handletextpad=0.6)

# 9. 轴
ax.set_xlim(XMIN, XMAX)
ax.set_ylim(YMIN, YMAX)
ax.set_xlabel('经度 (°E)', fontproperties=cn_font, fontsize=10)
ax.set_ylabel('纬度 (°N)', fontproperties=cn_font, fontsize=10)
xt = np.arange(116.2, 116.62, 0.1)
yt = np.arange(39.80, 40.09, 0.05)
ax.set_xticks(xt); ax.set_yticks(yt)
ax.set_xticklabels([f'{x:.1f}°' for x in xt], fontsize=8)
ax.set_yticklabels([f'{y:.2f}°' for y in yt], fontsize=8)
ax.tick_params(direction='in', length=4, width=0.8)
ax.grid(True, linestyle=':', linewidth=0.35, color='#ccc', alpha=0.6)
ax.set_axisbelow(True)
for sp in ax.spines.values():
    sp.set_linewidth(0.8); sp.set_color('#999')

ax.set_title('图3-X  公共交通竞争力评价服务中心目的地分布',
             fontproperties=cn_font, fontsize=11.5,
             pad=10, fontweight='bold', color='#1a1a1a')

plt.tight_layout(pad=0.8)
plt.savefig(OUT_PNG, dpi=300, bbox_inches='tight', facecolor='white')
plt.savefig(OUT_PDF, bbox_inches='tight', facecolor='white')
print(f"✓ {OUT_PNG}")
print(f"✓ {OUT_PDF}")

print("\n框内目的地：")
for did,lon,lat,name in INNER:
    print(f"  {did} {name:8s} ({lon},{lat})")
print("框外目的地：")
for did,lon,lat in OUTER:
    print(f"  {did} ({lon},{lat})")