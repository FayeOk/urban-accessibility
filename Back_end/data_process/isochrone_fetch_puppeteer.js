/**
 * isochrone_fetch_puppeteer.js
 * ============================
 * 用本地 HTTP 服务 + Puppeteer 调用高德 ArrivalRange
 * 
 * 原理：
 *   1. 在本地起一个 HTTP 服务（8765端口）提供 HTML 页面
 *   2. Puppeteer 用 page.goto() 访问这个页面（真实 URL，高德 SDK 能正常加载）
 *   3. 通过 URL 参数传入坐标和时间，页面执行后把结果写到 window._result
 *   4. Puppeteer 读取结果，写入缓存
 *
 * 安装：npm install puppeteer
 * 运行：
 *   node isochrone_fetch_puppeteer.js --limit=5
 *   node isochrone_fetch_puppeteer.js
 */

const puppeteer = require('puppeteer');
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

// ── 配置 ─────────────────────────────────────────
const AMAP_KEY = import.meta.env.VITE_AMAP_KEY;
const AMAP_SEC_CODE = 'd360b45265a6b65016eca2fb8d59da48';
const MINUTES = [30, 45];
const CONCURRENCY = 2;
const TIMEOUT = 45000;
const RETRY_MAX = 3;
const SERVER_PORT = 8765;

const BASE = '/Users/aaa/Desktop/Major Thesis/System_build/urban-accessibility-rebuild/Back_end/data_process';
const GRID_PATH = path.join(BASE, 'output/demand_grid.geojson');
const CACHE_DIR = path.join(BASE, 'cache');

// ── HTML 模板（由本地服务器提供）────────────────
function makeHtml(gcjLon, gcjLat, minute) {
    return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script>
window._AMapSecurityConfig = { securityJsCode: "${AMAP_SEC_CODE}" };
</script>
<script src="https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}&plugin=AMap.ArrivalRange"></script>
</head>
<body>
<div id="container" style="width:400px;height:400px"></div>
<script>
window._done   = false;
window._result = null;
window._error  = null;

function waitAndSearch(retry) {
    if (typeof AMap === 'undefined' || !AMap.Map || !AMap.ArrivalRange) {
        if (retry > 100) { window._error = 'AMap load timeout'; window._done = true; return; }
        setTimeout(function() { waitAndSearch(retry + 1); }, 200);
        return;
    }
    try {
        var map = new AMap.Map('container', {
            center: [${gcjLon}, ${gcjLat}],
            zoom: 11
        });
        var ar = new AMap.ArrivalRange();
        ar.search(
            new AMap.LngLat(${gcjLon}, ${gcjLat}),
            ${minute},
            function(status, result) {
                if (result && result.bounds && result.bounds.length > 0) {
                    window._result = result.bounds.map(function(poly) {
                        return poly.map(function(pt) { return [pt.lng, pt.lat]; });
                    });
                } else {
                    window._error = 'status=' + status + '|' + JSON.stringify(result).slice(0, 150);
                }
                window._done = true;
            },
            { policy: 'BUS' }
        );
    } catch(e) {
        window._error = 'err:' + e.message;
        window._done = true;
    }
}
waitAndSearch(0);
</script>
</body>
</html>`;
}

// ── 本地 HTTP 服务器 ──────────────────────────────
function startServer() {
    const server = http.createServer((req, res) => {
        const parsed = url.parse(req.url, true);
        const q = parsed.query;
        if (!q.lon || !q.lat || !q.min) {
            res.writeHead(400); res.end('missing params'); return;
        }
        const html = makeHtml(
            parseFloat(q.lon),
            parseFloat(q.lat),
            parseInt(q.min)
        );
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html);
    });
    return new Promise(resolve => {
        server.listen(SERVER_PORT, '127.0.0.1', () => {
            console.log(`  本地服务器启动: http://127.0.0.1:${SERVER_PORT}`);
            resolve(server);
        });
    });
}

// ── WGS-84 → GCJ-02 ──────────────────────────────
function wgs84ToGcj02(lon, lat) {
    const a = 6378245.0, ee = 0.00669342162296594323, pi = Math.PI;
    const dLat = (function (x, y) {
        let r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
        r += (20 * Math.sin(6 * x * pi) + 20 * Math.sin(2 * x * pi)) * 2 / 3;
        r += (20 * Math.sin(y * pi) + 40 * Math.sin(y / 3 * pi)) * 2 / 3;
        r += (160 * Math.sin(y / 12 * pi) + 320 * Math.sin(y * pi / 30)) * 2 / 3;
        return r;
    })(lon - 105, lat - 35);
    const dLon = (function (x, y) {
        let r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
        r += (20 * Math.sin(6 * x * pi) + 20 * Math.sin(2 * x * pi)) * 2 / 3;
        r += (20 * Math.sin(x * pi) + 40 * Math.sin(x / 3 * pi)) * 2 / 3;
        r += (150 * Math.sin(x / 12 * pi) + 300 * Math.sin(x / 30 * pi)) * 2 / 3;
        return r;
    })(lon - 105, lat - 35);
    const radLat = lat / 180 * pi;
    let magic = Math.sin(radLat);
    magic = 1 - ee * magic * magic;
    const sq = Math.sqrt(magic);
    return [
        lon + (dLon * 180) / (a / sq * Math.cos(radLat) * pi),
        lat + (dLat * 180) / ((a * (1 - ee)) / (magic * sq) * pi),
    ];
}

// ── 读取网格 ──────────────────────────────────────
function loadGrid(p) {
    const feats = JSON.parse(fs.readFileSync(p, 'utf8')).features;
    return feats.map((f, i) => {
        const g = f.geometry;
        let cx, cy;
        if (g.type === 'Polygon') {
            const r = g.coordinates[0];
            cx = r.reduce((s, p) => s + p[0], 0) / r.length;
            cy = r.reduce((s, p) => s + p[1], 0) / r.length;
        } else { [cx, cy] = g.coordinates; }
        return { idx: i, wgsLon: cx, wgsLat: cy };
    });
}

// ── 缓存 ─────────────────────────────────────────
const cacheFile = (idx, min) => path.join(CACHE_DIR, `grid_${idx}_t${min}.json`);
const isCached = (idx, min) => fs.existsSync(cacheFile(idx, min));
const saveCache = (idx, min, data) => fs.writeFileSync(cacheFile(idx, min), JSON.stringify(data));

// ── 单次调用 ──────────────────────────────────────
async function fetchOne(page, grid, minute) {
    const [gcjLon, gcjLat] = wgs84ToGcj02(grid.wgsLon, grid.wgsLat);
    const pageUrl = `http://127.0.0.1:${SERVER_PORT}/?lon=${gcjLon}&lat=${gcjLat}&min=${minute}`;

    for (let attempt = 0; attempt < RETRY_MAX; attempt++) {
        try {
            await page.goto(pageUrl, { waitUntil: 'networkidle2', timeout: 15000 });

            const r = await page.waitForFunction(
                () => window._done === true,
                { timeout: TIMEOUT, polling: 300 }
            ).then(() => page.evaluate(() => ({
                result: window._result,
                error: window._error,
            })));

            if (r.result && r.result.length > 0) {
                return {
                    status: 'ok', gridIdx: grid.idx, minute,
                    gcjLon, gcjLat, wgsLon: grid.wgsLon, wgsLat: grid.wgsLat,
                    bounds: r.result, coords: r.result[0],
                };
            }

            const errMsg = r.error || 'empty_bounds';
            console.log(`\n    [✗ g${grid.idx} t${minute} #${attempt + 1}] ${errMsg}`);
            if (attempt < RETRY_MAX - 1) await new Promise(res => setTimeout(res, 2000));
            else return { status: 'fail', error: errMsg, coords: [], bounds: [] };

        } catch (e) {
            console.log(`\n    [err g${grid.idx} t${minute} #${attempt + 1}] ${e.message}`);
            if (attempt < RETRY_MAX - 1) await new Promise(res => setTimeout(res, 2000));
            else return { status: 'fail', error: e.message, coords: [], bounds: [] };
        }
    }
    return { status: 'fail', error: 'max_retries', coords: [], bounds: [] };
}

// ── Worker ────────────────────────────────────────
async function runWorker(queue, browser, stats) {
    const page = await browser.newPage();
    await page.setRequestInterception(true);
    page.on('request', req => {
        if (['image', 'font', 'media'].includes(req.resourceType())) req.abort();
        else req.continue();
    });
    page.on('pageerror', err => console.log(`\n  [page_err] ${err.message}`));

    while (queue.length > 0) {
        const task = queue.shift();
        if (!task) break;
        const { grid, minute, total } = task;

        if (isCached(grid.idx, minute)) {
            stats.done++; stats.skip++;
            process.stdout.write(`\r  ${stats.done}/${total} ✓:${stats.success} ✗:${stats.fail} skip:${stats.skip}   `);
            continue;
        }

        const res = await fetchOne(page, grid, minute);
        saveCache(grid.idx, minute, res);
        stats.done++;
        if (res.status === 'ok') {
            stats.success++;
            process.stdout.write(`\r  ${stats.done}/${total} ✓:${stats.success} ✗:${stats.fail} | g${grid.idx} t${minute} ${res.coords.length}pts   `);
        } else {
            stats.fail++;
            process.stdout.write(`\r  ${stats.done}/${total} ✓:${stats.success} ✗:${stats.fail} | g${grid.idx} t${minute} FAIL   `);
        }
        await new Promise(r => setTimeout(r, 500));
    }
    await page.close();
}

// ── 主流程 ────────────────────────────────────────
async function main() {
    const args = process.argv.slice(2);
    const limit = parseInt((args.find(a => a.startsWith('--limit=')) || '=0').split('=')[1]);
    const conc = parseInt((args.find(a => a.startsWith('--concurrency=')) || `=${CONCURRENCY}`).split('=')[1]);

    if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });

    console.log(`→ 读取网格: ${GRID_PATH}`);
    let grids = loadGrid(GRID_PATH);
    console.log(`  网格总数: ${grids.length}`);
    if (limit > 0) { grids = grids.slice(0, limit); console.log(`  ⚠ 调试: 前 ${limit} 个`); }

    const cached = grids.filter(g => MINUTES.every(m => isCached(g.idx, m))).length;
    console.log(`  已缓存: ${cached}/${grids.length}\n`);

    // 启动本地服务器
    const server = await startServer();

    const queue = [];
    for (const grid of grids)
        for (const minute of MINUTES)
            queue.push({ grid, minute, total: grids.length * MINUTES.length });

    console.log(`→ 启动 Puppeteer（${conc} 并发）...`);
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    });

    const stats = { done: 0, success: 0, skip: 0, fail: 0 };
    const t0 = Date.now();
    await Promise.all(Array.from({ length: conc }, () => runWorker(queue, browser, stats)));
    await browser.close();
    server.close();

    const mins = ((Date.now() - t0) / 60000).toFixed(1);
    console.log(`\n\n${'─'.repeat(50)}`);
    console.log(`  完成！耗时: ${mins} 分钟`);
    console.log(`  成功:${stats.success}  跳过:${stats.skip}  失败:${stats.fail}`);
    if (stats.success > 0) console.log(`  下一步: python isochrone_score.py`);
}

main().catch(e => { console.error(e); process.exit(1); });