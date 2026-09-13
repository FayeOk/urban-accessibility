"""
collect_zone_rays_both.py
=========================
对3个交通小区同时采集小汽车和公交射线采样数据
8方向 × 25距离(1-25km) × 1时段 = 200次/小区/方式
3小区 × 200 × 2方式 = 1200次，约15分钟

用法：
  早高峰时段运行：SESSION = 'morning'
  平峰时段运行：  SESSION = 'midday'
  晚高峰时段运行：SESSION = 'evening'
"""

import math, time, json, requests

API_KEY  = 'fed24f8ba01f3a3561e828031553b68b'
BASE     = '/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild'
CENTROID_FILE = f'{BASE}/Back_end/data_process/output/zone_centroids.json'
OUT_FILE = f'{BASE}/Back_end/data_process/output/zone_rays_both.json'

# ── 修改这里选择当前时段 ──────────────────────
SESSION = 'morning'  # 早高峰跑时改'morning'，平峰改'midday'，晚高峰改'evening'

SESSIONS = {
    'morning': {'label': '早高峰08:00', 'ts': 1747612800},
    'midday':  {'label': '平峰15:00',   'ts': 1747638000},
    'evening': {'label': '晚高峰18:00', 'ts': 1747648800},
}

DIRECTIONS = [0, 45, 90, 135, 180, 225, 270, 315]
DISTANCES = [i * 500 for i in range(1, 41)]

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

def ray_point(center_lon, center_lat, direction_deg, distance_m):
    R = 6371000.0
    lat1 = math.radians(center_lat)
    lon1 = math.radians(center_lon)
    bearing = math.radians(direction_deg)
    d = distance_m / R
    lat2 = math.asin(math.sin(lat1)*math.cos(d) +
                     math.cos(lat1)*math.sin(d)*math.cos(bearing))
    lon2 = lon1 + math.atan2(math.sin(bearing)*math.sin(d)*math.cos(lat1),
                              math.cos(d)-math.sin(lat1)*math.sin(lat2))
    return math.degrees(lon2), math.degrees(lat2)

def get_driving_time(o_lon, o_lat, d_lon, d_lat, ts):
    try:
        r = requests.get('https://restapi.amap.com/v3/direction/driving', params={
            'key': API_KEY,
            'origin': f'{o_lon:.6f},{o_lat:.6f}',
            'destination': f'{d_lon:.6f},{d_lat:.6f}',
            'strategy': '0',
            'departure_time': str(ts),
        }, timeout=10)
        d = r.json()
        if d.get('status') != '1': return None
        paths = d['route'].get('paths', [])
        if not paths: return None
        return round(float(paths[0]['duration']) / 60.0, 2)
    except:
        return None

def get_transit_time(o_lon, o_lat, d_lon, d_lat, ts):
    try:
        r = requests.get('https://restapi.amap.com/v3/direction/transit/integrated', params={
            'key': API_KEY,
            'origin': f'{o_lon:.6f},{o_lat:.6f}',
            'destination': f'{d_lon:.6f},{d_lat:.6f}',
            'city': '010',
            'strategy': '0',
            'departure_time': str(ts),
            'nightflag': '0',
        }, timeout=10)
        d = r.json()
        if d.get('status') != '1': return None
        transits = d['route'].get('transits', [])
        if not transits: return None
        return round(float(transits[0]['duration']) / 60.0, 2)
    except:
        return None

def main():
    sess = SESSIONS[SESSION]
    print(f'采集时段: {sess["label"]}')

    with open(CENTROID_FILE, encoding='utf-8') as f:
        centroids = json.load(f)

    try:
        with open(OUT_FILE, encoding='utf-8') as f:
            results = json.load(f)
        print('已有缓存，继续...')
    except:
        results = {}

    for zid, zinfo in centroids.items():
        wgs_lon = zinfo['wgsLon']
        wgs_lat = zinfo['wgsLat']
        zname   = zinfo['name']
        gcj_lon, gcj_lat = wgs2gcj(wgs_lon, wgs_lat)

        print(f"\n{'='*50}")
        print(f"  {zname} ({zid})")

        if zid not in results:
            results[zid] = {'id': zid, 'name': zname,
                           'wgsLon': wgs_lon, 'wgsLat': wgs_lat,
                           'car': {}, 'bus': {}}

        # 生成200个采样点
        sample_points = []
        for deg in DIRECTIONS:
            for dist in DISTANCES:
                ep_lon, ep_lat = ray_point(wgs_lon, wgs_lat, deg, dist)
                gcj_ep_lon, gcj_ep_lat = wgs2gcj(ep_lon, ep_lat)
                sample_points.append({
                    'direction': deg, 'distance_m': dist,
                    'wgsLon': ep_lon, 'wgsLat': ep_lat,
                    'gcjLon': gcj_ep_lon, 'gcjLat': gcj_ep_lat,
                })

        # 小汽车采集
        if SESSION not in results[zid]['car']:
            print(f"  采集小汽车...")
            car_results = []
            errors = 0
            for i, pt in enumerate(sample_points):
                t = get_driving_time(pt['gcjLon'], pt['gcjLat'], gcj_lon, gcj_lat, sess['ts'])
                car_results.append({
                    'direction': pt['direction'],
                    'distance_m': pt['distance_m'],
                    'wgsLon': round(pt['wgsLon'], 6),
                    'wgsLat': round(pt['wgsLat'], 6),
                    'time_min': t,
                })
                if t is None: errors += 1
                time.sleep(0.15)
                if (i+1) % 50 == 0:
                    valid = [r['time_min'] for r in car_results if r['time_min']]
                    print(f"    {i+1}/200  错误:{errors}  均值:{sum(valid)/len(valid):.1f}min")
            results[zid]['car'][SESSION] = car_results
            valid = [r['time_min'] for r in car_results if r['time_min']]
            within_30 = sum(1 for v in valid if v <= 30)
            print(f"  小汽车完成: 有效={len(valid)}/200  均值={sum(valid)/len(valid):.1f}min  ≤30min={within_30}个")
        else:
            print(f"  小汽车{sess['label']}已有缓存，跳过")

        # 公交采集
        if SESSION not in results[zid]['bus']:
            print(f"  采集公交...")
            bus_results = []
            errors = 0
            for i, pt in enumerate(sample_points):
                t = get_transit_time(pt['gcjLon'], pt['gcjLat'], gcj_lon, gcj_lat, sess['ts'])
                bus_results.append({
                    'direction': pt['direction'],
                    'distance_m': pt['distance_m'],
                    'wgsLon': round(pt['wgsLon'], 6),
                    'wgsLat': round(pt['wgsLat'], 6),
                    'time_min': t,
                })
                if t is None: errors += 1
                time.sleep(0.15)
                if (i+1) % 50 == 0:
                    valid = [r['time_min'] for r in bus_results if r['time_min']]
                    avg = sum(valid)/len(valid) if valid else 0
                    print(f"    {i+1}/200  错误:{errors}  均值:{avg:.1f}min")
            results[zid]['bus'][SESSION] = bus_results
            valid = [r['time_min'] for r in bus_results if r['time_min']]
            within_45 = sum(1 for v in valid if v <= 45)
            print(f"  公交完成: 有效={len(valid)}/200  均值={sum(valid)/len(valid) if valid else 0:.1f}min  ≤45min={within_45}个")
        else:
            print(f"  公交{sess['label']}已有缓存，跳过")

        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f'✓ {sess["label"]}采集完成！输出: {OUT_FILE}')

if __name__ == '__main__':
    main()