"""
gen_isochrone_script.py
=======================
生成6核心区45min等时圈采集脚本，复制到高德Demo页面控制台运行

运行：
  python gen_isochrone_script.py
  → 自动复制到剪贴板，去浏览器粘贴即可
"""

import json, subprocess, math
import transbigdata as tbd

# ── 6核心区边界框 ──────────────────────────────────
BOUNDS   = (116.1, 39.75, 116.65, 40.05)
ACCURACY = 500
MINUTE   = 45   # 只采集45min

# ── 生成网格 ───────────────────────────────────────
print("生成网格...")
grid, params = tbd.area_to_grid(BOUNDS, accuracy=ACCURACY, method="hexa")
print(f"网格数: {len(grid)}")

# ── 提取中心点并转GCJ-02 ──────────────────────────
def wgs84_to_gcj02(lon, lat):
    import math
    a = 6378245.0; ee = 0.00669342162296594323; pi = math.pi
    def tLat(x,y):
        r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(y*pi)+40*math.sin(y/3*pi))*2/3
        r+=(160*math.sin(y/12*pi)+320*math.sin(y*pi/30))*2/3; return r
    def tLon(x,y):
        r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(x*pi)+40*math.sin(x/3*pi))*2/3
        r+=(150*math.sin(x/12*pi)+300*math.sin(x/30*pi))*2/3; return r
    dLat=tLat(lon-105,lat-35); dLon=tLon(lon-105,lat-35)
    radlat=lat/180*pi; mg=math.sin(radlat); mg=1-ee*mg*mg; sq=math.sqrt(mg)
    return lon+(dLon*180)/(a/sq*math.cos(radlat)*pi), lat+(dLat*180)/((a*(1-ee))/(mg*sq)*pi)

points = []
for i, row in grid.iterrows():
    cx = row.geometry.centroid.x
    cy = row.geometry.centroid.y
    gcj_lon, gcj_lat = wgs84_to_gcj02(cx, cy)
    points.append({
        "idx": i,
        "wgsLon": round(cx, 6),
        "wgsLat": round(cy, 6),
        "gcjLon": round(gcj_lon, 6),
        "gcjLat": round(gcj_lat, 6),
    })

print(f"提取中心点: {len(points)} 个")

# ── 生成JS脚本 ────────────────────────────────────
points_json = json.dumps(points)

script = r"""
(async function() {

var POINTS = """ + points_json + r""";
var MINUTE = 45;

// 下载函数
function download(features, filename) {
    var blob = new Blob([JSON.stringify({type:'FeatureCollection',features:features})],
        {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click();
    console.log('downloaded:', filename, features.length + ' features');
}

// 初始化
var ar = new AMap.ArrivalRange();
var results = [];
var done = 0, ok = 0, fail = 0;
var total = POINTS.length;
var t0 = Date.now();

console.log('开始采集 ' + total + ' 个网格，45min等时圈...');

for (var i = 0; i < POINTS.length; i++) {
    var pt = POINTS[i];

    var res = await new Promise(function(resolve) {
        var _pt = pt;
        ar.search(
            new AMap.LngLat(_pt.gcjLon, _pt.gcjLat),
            MINUTE,
            function(status, result) {
                if (result && result.bounds && result.bounds.length > 0) {
                    var polys = result.bounds.map(function(poly) {
                        var ring = Array.isArray(poly[0]) ? poly : [poly];
                        return ring[0].map(function(pt) { return [pt[0], pt[1]]; });
                    });
                    resolve({ ok: true, polys: polys });
                } else {
                    resolve({ ok: false, error: status });
                }
            },
            { policy: 'BUS' }
        );
    });

    var feat = {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [pt.wgsLon, pt.wgsLat] },
        properties: {
            grid_idx: pt.idx,
            wgsLon: pt.wgsLon, wgsLat: pt.wgsLat,
            gcjLon: pt.gcjLon, gcjLat: pt.gcjLat,
            minute: MINUTE,
            status: res.ok ? 'ok' : 'fail',
            bounds: res.ok ? res.polys : []
        }
    };
    results.push(feat);

    if (res.ok) ok++; else fail++;
    done++;

    // 进度
    if (done % 100 === 0 || done === total) {
        var elap = ((Date.now()-t0)/1000).toFixed(0);
        var eta = Math.round((total-done)*((Date.now()-t0)/1000)/done);
        console.log('进度:'+done+'/'+total+' ✓'+ok+' ✗'+fail+' 耗时:'+elap+'s 剩余≈'+eta+'s');
    }

    // 每400个保存一次
    if (done > 0 && done % 400 === 0) {
        download(results.slice(), 'isochrone_45min_partial_' + done + '.geojson');
        await new Promise(function(r){setTimeout(r,1000);});
    }

    await new Promise(function(r){setTimeout(r,700);});
}

console.log('完成！✓'+ok+' ✗'+fail);
download(results, 'isochrone_45min_6districts.geojson');

})();
"""

# 复制到剪贴板
try:
    subprocess.run(['pbcopy'], input=script.encode(), check=True)
    print(f"\n✓ 已复制到剪贴板！")
    print(f"  请求次数: {len(points)}")
    print(f"  预计耗时: {round(len(points)*0.8/60, 1)} 分钟")
    print(f"\n操作步骤:")
    print(f"  1. 打开 https://lbs.amap.com/demo/javascript-api-v2/example/bus-info/arrival-range")
    print(f"  2. Command+Option+J 打开控制台")
    print(f"  3. Command+V 粘贴，回车运行")
    print(f"  4. 等待约 {round(len(points)*0.8/60, 1)} 分钟")
    print(f"  5. 下载文件: isochrone_45min_6districts.geojson")
except:
    # 如果pbcopy不可用，保存到文件
    with open('console_isochrone_45min.js', 'w', encoding='utf-8') as f:
        f.write(script)
    print("✓ 已保存到 console_isochrone_45min.js")
    print("  打开该文件，全选复制，粘贴到高德Demo控制台运行")