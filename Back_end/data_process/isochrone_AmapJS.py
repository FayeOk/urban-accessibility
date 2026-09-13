import json
grid = json.load(open('/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process/output/demand_grid.geojson'))

script = '''
(async function() {
var GRID_JSON = ''' + json.dumps(grid) + ''';

function wgs84ToGcj02(lon, lat) {
    var a=6378245.0,ee=0.00669342162296594323,pi=Math.PI;
    function tLat(x,y){var r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*Math.sqrt(Math.abs(x));r+=(20*Math.sin(6*x*pi)+20*Math.sin(2*x*pi))*2/3;r+=(20*Math.sin(y*pi)+40*Math.sin(y/3*pi))*2/3;r+=(160*Math.sin(y/12*pi)+320*Math.sin(y*pi/30))*2/3;return r;}
    function tLon(x,y){var r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*Math.sqrt(Math.abs(x));r+=(20*Math.sin(6*x*pi)+20*Math.sin(2*x*pi))*2/3;r+=(20*Math.sin(x*pi)+40*Math.sin(x/3*pi))*2/3;r+=(150*Math.sin(x/12*pi)+300*Math.sin(x/30*pi))*2/3;return r;}
    var dLat=tLat(lon-105,lat-35),dLon=tLon(lon-105,lat-35);
    var radLat=lat/180*pi,magic=Math.sin(radLat);
    magic=1-ee*magic*magic;var sq=Math.sqrt(magic);
    return [lon+(dLon*180)/(a/sq*Math.cos(radLat)*pi),lat+(dLat*180)/((a*(1-ee))/(magic*sq)*pi)];
}

var grids = GRID_JSON.features.map(function(f,i){
    var g=f.geometry,cx,cy;
    if(g.type===\'Polygon\'){var r=g.coordinates[0];cx=r.reduce(function(s,p){return s+p[0];},0)/r.length;cy=r.reduce(function(s,p){return s+p[1];},0)/r.length;}
    else{cx=g.coordinates[0];cy=g.coordinates[1];}
    var gcj=wgs84ToGcj02(cx,cy);
    return{idx:i,wgsLon:cx,wgsLat:cy,gcjLon:gcj[0],gcjLat:gcj[1]};
});

function download(features,filename){
    var blob=new Blob([JSON.stringify({type:\'FeatureCollection\',features:features})],{type:\'application/json\'});
    var a=document.createElement(\'a\');a.href=URL.createObjectURL(blob);a.download=filename;a.click();
    console.log(\'downloaded:\',filename,features.length+\'features\');
}

var ar=new AMap.ArrivalRange();
var MINUTES=[30,45];
var results30=[],results45=[];
var done=0,ok=0,fail=0;
var total=grids.length*MINUTES.length;
var t0=Date.now();
console.log(\'start\',grids.length,\'grids\',total,\'requests\');

for(var i=0;i<grids.length;i++){
    var g=grids[i];
    for(var j=0;j<MINUTES.length;j++){
        var min=MINUTES[j];
        var res=await new Promise(function(resolve){
            var _g=g,_m=min;
            ar.search(new AMap.LngLat(_g.gcjLon,_g.gcjLat),_m,function(status,result){
                if(result&&result.bounds&&result.bounds.length>0){
                    var polys=result.bounds.map(function(poly){
                        var ring=Array.isArray(poly[0])?poly:[poly];
                        return ring[0].map(function(pt){return[pt[0],pt[1]];});
                    });
                    resolve({ok:true,polys:polys});
                }else{resolve({ok:false,error:status});}
            },{policy:\'BUS\'});
        });
        var feat={type:\'Feature\',geometry:{type:\'Point\',coordinates:[g.wgsLon,g.wgsLat]},properties:{grid_idx:g.idx,wgsLon:g.wgsLon,wgsLat:g.wgsLat,gcjLon:g.gcjLon,gcjLat:g.gcjLat,minute:min,status:res.ok?\'ok\':\'fail\',bounds:res.ok?res.polys:[]}};
        if(min===30)results30.push(feat);else results45.push(feat);
        if(res.ok)ok++;else fail++;
        done++;
        if(done%100===0||done===total){var e=((Date.now()-t0)/1000).toFixed(0);var eta=Math.round((total-done)*((Date.now()-t0)/1000)/done);console.log(\'progress:\'+done+\'/\'+total+\' ok:\'+ok+\' fail:\'+fail+\' elapsed:\'+e+\'s eta:\'+eta+\'s\');}
        await new Promise(function(r){setTimeout(r,700);});
    }
    if(i>0&&i%300===0){
        download(results30.slice(),\'iso30_partial_\'+i+\'.geojson\');
        await new Promise(function(r){setTimeout(r,1000);});
        download(results45.slice(),\'iso45_partial_\'+i+\'.geojson\');
    }
}
console.log(\'DONE ok:\'+ok+\' fail:\'+fail);
download(results30,\'isochrone_30min.geojson\');
await new Promise(function(r){setTimeout(r,1500);});
download(results45,\'isochrone_45min.geojson\');
})();
'''

import subprocess
subprocess.run(['pbcopy'], input=script.encode())
print('已复制到剪贴板！大小:', len(script)//1024, 'KB')
print('直接在高德demo控制台粘贴运行即可')