"""
gen_zone_bus_isochrone.py
=========================
生成三个交通小区公交等时圈采集脚本，复制到剪贴板
运行：python gen_zone_bus_isochrone.py
"""

import json, subprocess

ZONES = [
    {'id':'bj_1622','name':'中心区（天安门附近）','wgsLon':116.395005,'wgsLat':39.915987},
    {'id':'bj_689', 'name':'西城次中心',          'wgsLon':116.305361,'wgsLat':39.951523},
    {'id':'bj_1610','name':'东南边缘区',           'wgsLon':116.430922,'wgsLat':39.852824},
]

import math
def wgs2gcj(lon, lat):
    a=6378245.0; ee=0.00669342162296594323; pi=math.pi
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

# 加入GCJ坐标
for z in ZONES:
    gcj_lon, gcj_lat = wgs2gcj(z['wgsLon'], z['wgsLat'])
    z['gcjLon'] = round(gcj_lon, 6)
    z['gcjLat'] = round(gcj_lat, 6)

zones_json = json.dumps(ZONES, ensure_ascii=False)

script = r"""
(async function() {

var ZONES = """ + zones_json + r""";
var results = {};

function download(obj, filename) {
    var blob = new Blob([JSON.stringify(obj)], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename; a.click();
    console.log('已下载:', filename);
}

var ar = new AMap.ArrivalRange();
console.log('开始采集3个交通小区的公交45min等时圈...');

for (var i = 0; i < ZONES.length; i++) {
    var zone = ZONES[i];
    console.log('采集中:', zone.name);

    var res = await new Promise(function(resolve) {
        var _zone = zone;
        ar.search(
            new AMap.LngLat(_zone.gcjLon, _zone.gcjLat),
            45,
            function(status, result) {
                if (result && result.bounds && result.bounds.length > 0) {
                    var bounds = result.bounds.map(function(poly) {
                        var ring = Array.isArray(poly[0]) ? poly : [poly];
                        return ring[0].map(function(pt) { return [pt[0], pt[1]]; });
                    });
                    console.log('✓', _zone.name, result.bounds.length + '环');
                    resolve({ status: 'ok', bounds: bounds });
                } else {
                    console.log('✗', _zone.name, status);
                    resolve({ status: 'failed', bounds: [] });
                }
            },
            { policy: 'BUS' }
        );
    });

    results[zone.id] = {
        id: zone.id,
        name: zone.name,
        wgsLon: zone.wgsLon,
        wgsLat: zone.wgsLat,
        gcjLon: zone.gcjLon,
        gcjLat: zone.gcjLat,
        status: res.status,
        bounds: res.bounds
    };

    await new Promise(function(r){ setTimeout(r, 2000); });
}

console.log('全部完成！');
download(results, 'zone_bus_isochrones.json');

})();
"""

try:
    subprocess.run(['pbcopy'], input=script.encode(), check=True)
    print('✓ 已复制到剪贴板！')
    print()
    print('操作步骤：')
    print('  1. 打开 https://lbs.amap.com/demo/javascript-api-v2/example/bus-info/arrival-range')
    print('  2. F12 打开控制台 → Console标签')
    print('  3. Command+V 粘贴，回车运行')
    print('  4. 约10秒后自动下载 zone_bus_isochrones.json')
except Exception as e:
    print(f'pbcopy失败: {e}')
    with open('zone_bus_isochrone_console.js', 'w') as f:
        f.write(script)
    print('已保存到 zone_bus_isochrone_console.js，手动复制粘贴')