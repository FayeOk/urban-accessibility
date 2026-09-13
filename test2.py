
import geopandas as gpd, math
from shapely.ops import transform

def wgs2gcj(lon, lat):
    a=6378245.0; ee=0.00669342162296594323; pi=math.pi
    def tL(x,y):
        r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(y*pi)+40*math.sin(y/3*pi))*2/3
        r+=(160*math.sin(y/12*pi)+320*math.sin(y*pi/30))*2/3; return r
    def tO(x,y):
        r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
        r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
        r+=(20*math.sin(x*pi)+40*math.sin(x/3*pi))*2/3
        r+=(150*math.sin(x/12*pi)+300*math.sin(x/30*pi))*2/3; return r
    dLat=tL(lon-105,lat-35); dLon=tO(lon-105,lat-35)
    radlat=lat/180*pi; mg=math.sin(radlat); mg=1-ee*mg*mg; sq=math.sqrt(mg)
    return lon+(dLon*180)/(a/sq*math.cos(radlat)*pi), lat+(dLat*180)/((a*(1-ee))/(mg*sq)*pi)

def convert_geom(geom):
    def conv(x, y, z=None):
        lons, lats = [], []
        for lo, la in zip(x, y):
            glo, gla = wgs2gcj(lo, la)
            lons.append(glo)
            lats.append(gla)
        return tuple(lons), tuple(lats)
    return transform(conv, geom)

zones = gpd.read_file('/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild/Back_end/data_process/北京区块数据.shp')
zones = zones.to_crs('EPSG:4326')
zones_proj = zones.to_crs('EPSG:32650')
zones['cx'] = zones_proj.geometry.centroid.to_crs('EPSG:4326').x
zones['cy'] = zones_proj.geometry.centroid.to_crs('EPSG:4326').y
core = zones[zones['cx'].between(116.08,116.67) & zones['cy'].between(39.74,40.06)].copy()
core['geometry'] = core['geometry'].apply(convert_geom)
core[['id','geometry']].to_file('/Users/aaa/Desktop/MajorThesis/System_build/urban-accessibility-rebuild/public/data/output/zones_beijing.geojson', driver='GeoJSON')
print('done', len(core), '个交通小区')
