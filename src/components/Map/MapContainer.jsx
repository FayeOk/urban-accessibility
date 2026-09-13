import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import Map from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, PolygonLayer } from '@deck.gl/layers';
import 'mapbox-gl/dist/mapbox-gl.css';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
const AMAP_KEY = import.meta.env.VITE_AMAP_KEY;

const DEMAND_STOPS = [
    [0, 0, 0, 0], [0, 200, 210, 140], [80, 210, 120, 150],
    [255, 220, 0, 158], [255, 110, 0, 165], [220, 30, 30, 172],
];
const ISO_STOPS = [
    [0, 0, 0, 0], [255, 240, 150, 130], [255, 200, 50, 150],
    [255, 140, 0, 165], [220, 60, 0, 175], [160, 0, 50, 185],
];
const COV_STOPS = [
    [0, 0, 0, 0], [200, 0, 80, 135], [240, 80, 0, 148],
    [255, 190, 0, 158], [160, 240, 80, 168],
];
const TCI_STOPS = [
    [0, 0, 0, 0], [210, 40, 40, 155], [240, 120, 30, 160],
    [245, 210, 30, 158], [130, 210, 60, 155], [30, 180, 80, 150],
];
// FIX 3: Composite alpha values brought in line with other layers (~140-170 range)
const COMPOSITE_STOPS = [
    [0, 0, 0, 0], [30, 58, 95, 140], [37, 99, 235, 150],
    [34, 197, 94, 158], [251, 191, 36, 158], [239, 68, 68, 165],
];

function interpolate(stops, score) {
    if (!score || score <= 0) return [0, 0, 0, 0];
    const t = Math.min(score / 100, 1);
    const raw = t * (stops.length - 1);
    const idx = Math.min(Math.floor(raw), stops.length - 2);
    const frac = raw - idx;
    const a = stops[idx], b = stops[idx + 1];
    return [
        Math.round(a[0] + (b[0] - a[0]) * frac),
        Math.round(a[1] + (b[1] - a[1]) * frac),
        Math.round(a[2] + (b[2] - a[2]) * frac),
        Math.round(a[3] + (b[3] - a[3]) * frac),
    ];
}

function fmt(v, d = 1) { return v == null ? '—' : Number(v).toFixed(d); }

const TCI_SESSIONS = [
    { key: 'morning', label: '早高峰', field: 'tci_morning_norm', raw: 'tci_morning', color: '#f87171' },
    { key: 'midday', label: '平峰', field: 'tci_midday_norm', raw: 'tci_midday', color: '#fbbf24' },
    { key: 'evening', label: '晚高峰', field: 'tci_evening_norm', raw: 'tci_evening', color: '#818cf8' },
];

// 三个交通小区
const ZONES = [
    { id: 'bj_895', name: '西城北部', cx: 116.375085, cy: 39.963068 },
    { id: 'bj_1059', name: '朝阳西部', cx: 116.442909, cy: 39.928070 },
    { id: 'bj_1610', name: '东南边缘区', cx: 116.430922, cy: 39.852824 },
];

// ── Tooltip ───────────────────────────────────
function Tooltip({ info, tciSession }) {
    if (!info?.object) return null;
    const p = info.object.properties || {};
    const isGrid = p.demand_final != null || p.coverage_score != null || p.tci_mean != null || p.iso_score_combined != null || p.composite != null;
    const sess = TCI_SESSIONS.find(s => s.key === tciSession);
    return (
        <div style={{
            position: 'absolute', left: info.x + 14, top: info.y + 14,
            background: 'rgba(8,12,24,0.94)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 9, boxShadow: '0 4px 20px rgba(0,0,0,0.55)',
            padding: '9px 13px', fontSize: 12,
            fontFamily: 'system-ui,-apple-system,sans-serif',
            pointerEvents: 'none', zIndex: 100, minWidth: 170,
            color: 'rgba(220,232,248,0.88)', backdropFilter: 'blur(12px)',
        }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(96,196,255,0.8)', marginBottom: 7, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                {isGrid ? '网格详情' : '公交站点'}
            </div>
            {isGrid ? (<>
                {p.demand_final != null && <TR label="需求密度" val={fmt(p.demand_final ?? p.demand_kde_norm)} c="#fbbf24" />}
                {p.iso_score_combined > 0 && <TR label="等时圈评分" val={fmt(p.iso_score_combined)} c="#818cf8" />}
                {p.coverage_score != null && <TR label="覆盖度" val={fmt(p.coverage_score)} c="#34d399" />}
                {p.tci_mean != null && <TR label="综合TCI" val={fmt(p.tci_mean, 3)} c="#fb923c" />}
                {sess && p[sess.raw] != null && <TR label={`TCI(${sess.label})`} val={fmt(p[sess.raw], 3)} c={sess.color} />}
                {p.walk_score != null && <TR label="步行便捷度" val={fmt(p.walk_score)} c="#67e8f9" />}
                {/* FIX 3: Show composite score in tooltip */}
                {p.composite != null && <TR label="综合可达性" val={fmt(p.composite)} c="#22c55e" />}
                {p.d_norm != null && <TR label="需求密度" val={fmt(p.d_norm)} c="#fbbf24" />}
                {p.status != null && <TR label="供需状态" val={p.status} c="#f87171" />}
            </>) : (<>
                {p.name && <TR label="站点" val={p.name} c="#67e8f9" />}
                {p.line_count != null && <TR label="线路数" val={`${p.line_count}条`} c="#fbbf24" />}
            </>)}
        </div>
    );
}
function TR({ label, val, c }) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, gap: 14 }}>
            <span style={{ color: 'rgba(148,163,184,0.65)', fontSize: 11 }}>{label}</span>
            <span style={{ color: c, fontWeight: 600 }}>{val}</span>
        </div>
    );
}

// ── 图例 ──────────────────────────────────────
function MapLegend({ vis, tciSession }) {
    const sess = TCI_SESSIONS.find(s => s.key === tciSession);
    const LEGENDS = {
        // FIX 1: demand legend — label stripped, only 高/低 markers remain (handled in render)
        demand: { stops: ['rgba(0,200,210,0.85)', 'rgba(80,210,120,0.85)', 'rgba(255,220,0,0.85)', 'rgba(255,110,0,0.85)', 'rgba(220,30,30,0.85)'], label: '需求密度' },
        isochrone: { stops: ['rgba(255,220,100,0.85)', 'rgba(255,160,30,0.85)', 'rgba(240,80,0,0.85)', 'rgba(180,0,0,0.85)'], label: '等时圈POI' },
        coverage: { stops: ['rgba(200,0,80,0.85)', 'rgba(240,80,0,0.85)', 'rgba(255,190,0,0.85)', 'rgba(160,240,80,0.85)'], label: '覆盖度' },
        tci: { stops: ['rgba(210,40,40,0.85)', 'rgba(240,120,30,0.85)', 'rgba(245,210,30,0.85)', 'rgba(130,210,60,0.85)', 'rgba(30,180,80,0.85)'], label: `竞争力${sess ? `(${sess.label})` : ''}` },
        composite: { stops: ['rgba(30,58,95,0.85)', 'rgba(37,99,235,0.85)', 'rgba(34,197,94,0.85)', 'rgba(251,191,36,0.85)', 'rgba(239,68,68,0.85)'], label: '综合可达性' },
    };
    const active = Object.entries(LEGENDS).filter(([k]) => vis?.[k]);
    if (!active.length) return null;
    return (
        <div style={{ position: 'absolute', bottom: 28, right: 16, display: 'flex', flexDirection: 'column', gap: 7, zIndex: 50, pointerEvents: 'none' }}>
            {active.map(([key, cfg]) => (
                <div key={key} style={{
                    background: 'rgba(8,12,24,0.88)', border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 9, padding: '8px 10px', backdropFilter: 'blur(14px)',
                    display: 'flex', alignItems: 'stretch', gap: 8,
                }}>
                    <div style={{ width: 10, borderRadius: 4, flexShrink: 0, minHeight: 70, background: `linear-gradient(to top, ${cfg.stops.join(', ')})` }} />
                    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 70 }}>
                        <span style={{ fontSize: 10, color: 'rgba(200,220,245,0.6)' }}>{key === 'tci' ? '强' : '高'}</span>
                        {/* FIX 1: For demand layer, only show 高/低, no label text in the middle */}
                        {key !== 'demand' && (
                            <span style={{ fontSize: 10, color: 'rgba(200,220,245,0.5)', writingMode: 'vertical-lr', letterSpacing: '0.08em', textOrientation: 'mixed', fontWeight: 500 }}>{cfg.label}</span>
                        )}
                        <span style={{ fontSize: 10, color: 'rgba(200,220,245,0.6)' }}>{key === 'tci' ? '弱' : '低'}</span>
                    </div>
                </div>
            ))}
            {/* FIX 1: Isochrone travel-time legend only shown when isochrone layer is active */}
            {vis?.isochrone && (
                <div style={{ background: 'rgba(8,12,24,0.88)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 9, padding: '7px 10px', backdropFilter: 'blur(14px)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <div style={{ width: 24, height: 3, background: 'rgba(50,255,180,0.9)', borderRadius: 2 }} />
                        <span style={{ fontSize: 10, color: 'rgba(200,220,245,0.6)' }}>公交45min</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: 24, height: 3, background: 'rgba(255,140,0,0.9)', borderRadius: 2 }} />
                        <span style={{ fontSize: 10, color: 'rgba(200,220,245,0.6)' }}>小汽车30min</span>
                    </div>
                </div>
            )}
        </div>
    );
}

// ── 数据下载面板 ──────────────────────────────
const DOWNLOAD_REGIONS = [
    { key: 'xicheng', label: '西城区' },
    { key: 'chaoyang', label: '朝阳区', disabled: true },
    { key: 'haidian', label: '海淀区', disabled: true },
    { key: 'dongcheng', label: '东城区', disabled: true },
];

// 每个指标组：label=组名，color=颜色，file=数据来源，fields=详细字段列表
const DOWNLOAD_GROUPS = [
    {
        key: 'demand', label: '需求密度', color: '#fbbf24',
        file: '/data/output/demand_grid_beijing.geojson',
        fields: [
            { key: 'demand_final', label: '综合需求密度（校准后）' },
            { key: 'demand_kde_norm', label: '需求密度KDE（归一化）' },
            { key: 'demand_raw', label: '原始需求密度' },
            { key: 'population', label: '人口数量' },
            { key: 'pop_norm', label: '人口密度（归一化）' },
            { key: 'poi_count', label: 'POI总数' },
            { key: 'poi_医疗保健', label: 'POI_医疗保健' },
            { key: 'poi_科教文化', label: 'POI_科教文化' },
            { key: 'poi_购物消费', label: 'POI_购物消费' },
            { key: 'poi_公司企业', label: 'POI_公司企业' },
            { key: 'poi_生活服务', label: 'POI_生活服务' },
            { key: 'poi_休闲娱乐', label: 'POI_休闲娱乐' },
            { key: 'poi_运动健身', label: 'POI_运动健身' },
            { key: 'poi_商务住宅', label: 'POI_商务住宅' },
        ],
    },
    {
        key: 'isochrone', label: '机会可达性（等时圈）', color: '#818cf8',
        file: '/data/output/isochrone_grid_beijing.geojson',
        fields: [
            { key: 'iso_score_combined', label: '等时圈综合得分' },
            { key: 'iso_score_45m', label: '45min等时圈POI总量' },
            { key: 'iso_score_45m_norm', label: '45min等时圈得分（归一化）' },
            { key: 'poi_医疗保健', label: '等时圈内_医疗保健POI' },
            { key: 'poi_科教文化', label: '等时圈内_科教文化POI' },
            { key: 'poi_购物消费', label: '等时圈内_购物消费POI' },
            { key: 'poi_公司企业', label: '等时圈内_公司企业POI' },
            { key: 'poi_生活服务', label: '等时圈内_生活服务POI' },
            { key: 'poi_休闲娱乐', label: '等时圈内_休闲娱乐POI' },
            { key: 'poi_运动健身', label: '等时圈内_运动健身POI' },
            { key: 'has_isochrone', label: '是否有等时圈数据' },
        ],
    },
    {
        key: 'coverage', label: '网络覆盖度', color: '#34d399',
        file: '/data/output/coverage_grid_beijing.geojson',
        fields: [
            { key: 'coverage_score', label: '综合覆盖度得分' },
            { key: 'walk_score', label: '步行便捷度' },
            { key: 'diversity_score', label: '线路多样性得分' },
            { key: 'diversity_count', label: '500m内线路数' },
        ],
    },
    {
        key: 'tci', label: '公交竞争力（TCI）', color: '#fb923c',
        file: '/data/output/tci_grid_beijing.geojson',
        fields: [
            { key: 'tci_mean', label: 'TCI均值' },
            { key: 'tci_morning', label: 'TCI_早高峰（原始）' },
            { key: 'tci_morning_norm', label: 'TCI_早高峰（归一化）' },
            { key: 'tci_midday', label: 'TCI_平峰（原始）' },
            { key: 'tci_midday_norm', label: 'TCI_平峰（归一化）' },
            { key: 'tci_evening', label: 'TCI_晚高峰（原始）' },
            { key: 'tci_evening_norm', label: 'TCI_晚高峰（归一化）' },
        ],
    },
    {
        key: 'composite', label: '综合评价', color: '#22c55e',
        file: '/data/output/composite_xicheng.geojson',
        note: '仅西城区',
        fields: [
            { key: 'composite', label: '综合可达性得分' },
            { key: 'd_norm', label: '需求密度分项得分' },
            { key: 'i_norm', label: '机会可达性分项得分' },
            { key: 'c_norm', label: '网络覆盖度分项得分' },
            { key: 'supply', label: '综合供给得分' },
            { key: 'status', label: '供需状态分类' },
        ],
    },
];

function DownloadPanel() {
    const [open, setOpen] = useState(false);
    const [region, setRegion] = useState('xicheng');
    const [selectedGroups, setSelectedGroups] = useState({ composite: true });
    const [expandedGroup, setExpandedGroup] = useState(null);
    const [selectedFields, setSelectedFields] = useState({});
    const [loading, setLoading] = useState(false);

    // 初始化每组的字段选择（默认全选）
    const getGroupFields = (groupKey) => {
        if (selectedFields[groupKey] !== undefined) return selectedFields[groupKey];
        const grp = DOWNLOAD_GROUPS.find(g => g.key === groupKey);
        return grp ? grp.fields.map(f => f.key) : [];
    };

    const toggleGroup = (key) => {
        setSelectedGroups(prev => ({ ...prev, [key]: !prev[key] }));
        if (!selectedGroups[key] && !selectedFields[key]) {
            const grp = DOWNLOAD_GROUPS.find(g => g.key === key);
            setSelectedFields(prev => ({ ...prev, [key]: grp.fields.map(f => f.key) }));
        }
    };

    const toggleFieldInGroup = (groupKey, fieldKey) => {
        const cur = getGroupFields(groupKey);
        const next = cur.includes(fieldKey) ? cur.filter(k => k !== fieldKey) : [...cur, fieldKey];
        setSelectedFields(prev => ({ ...prev, [groupKey]: next }));
    };

    const activeGroups = DOWNLOAD_GROUPS.filter(g => selectedGroups[g.key]);
    const totalFields = activeGroups.reduce((s, g) => s + getGroupFields(g.key).length, 0);

    const handleDownload = async () => {
        if (activeGroups.length === 0 || totalFields === 0) return;
        setLoading(true);
        try {
            // 按组分别加载，以cx/cy为key合并所有字段
            const mergedMap = {};
            for (const grp of activeGroups) {
                const gFields = getGroupFields(grp.key);
                if (gFields.length === 0) continue;
                const res = await fetch(grp.file);
                const geojson = await res.json();
                for (const feat of geojson.features) {
                    const p = feat.properties;
                    const coords = feat.geometry?.coordinates?.[0];
                    const cx = p.cx != null ? Number(p.cx).toFixed(6)
                        : coords ? (coords.reduce((s, c) => s + c[0], 0) / coords.length).toFixed(6) : '';
                    const cy = p.cy != null ? Number(p.cy).toFixed(6)
                        : coords ? (coords.reduce((s, c) => s + c[1], 0) / coords.length).toFixed(6) : '';
                    const cellKey = cx + '_' + cy;
                    if (!mergedMap[cellKey]) mergedMap[cellKey] = { cx, cy };
                    for (const fk of gFields) {
                        const v = p[fk];
                        mergedMap[cellKey][`${grp.key}__${fk}`] = v == null ? '' : typeof v === 'number' ? Number(v).toFixed(4) : v;
                    }
                }
            }

            // 构建表头
            const colDefs = [];
            for (const grp of activeGroups) {
                const gFields = getGroupFields(grp.key);
                for (const fk of gFields) {
                    const fDef = grp.fields.find(f => f.key === fk);
                    colDefs.push({ colKey: `${grp.key}__${fk}`, label: `[${grp.label}] ${fDef?.label ?? fk}` });
                }
            }

            const headers = ['格网经度', '格网纬度', ...colDefs.map(c => c.label)];
            const rows = Object.values(mergedMap).map(row =>
                [row.cx, row.cy, ...colDefs.map(c => row[c.colKey] ?? '')]
            );

            const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
            const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const regionLabel = DOWNLOAD_REGIONS.find(r => r.key === region)?.label ?? region;
            a.download = `accessibility_${regionLabel}_${new Date().toISOString().slice(0, 10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('下载失败', e);
        } finally {
            setLoading(false);
            setOpen(false);
        }
    };

    const btnBase = { width: 34, height: 34, borderRadius: '50%', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(12px)', boxShadow: '0 2px 10px rgba(0,0,0,0.4)', transition: 'all 0.18s', fontSize: 15, border: 'none', fontFamily: 'system-ui,-apple-system,sans-serif' };

    return (
        <div style={{ position: 'relative' }}>
            <button onClick={() => setOpen(v => !v)} title="下载分析数据" style={{ ...btnBase, background: open ? 'rgba(34,197,94,0.22)' : 'rgba(8,12,24,0.82)', border: open ? '1.5px solid rgba(34,197,94,0.55)' : '1px solid rgba(255,255,255,0.1)', color: open ? 'rgba(34,210,100,0.95)' : 'rgba(255,255,255,0.4)' }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
            </button>
            {open && (
                <div style={{ position: 'absolute', top: 42, right: 0, width: 270, maxHeight: '80vh', overflowY: 'auto', background: 'rgba(8,12,24,0.97)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 11, boxShadow: '0 8px 28px rgba(0,0,0,0.65)', backdropFilter: 'blur(18px)', zIndex: 300, fontFamily: 'system-ui,-apple-system,sans-serif' }}>

                    {/* 标题 */}
                    <div style={{ padding: '10px 13px 8px', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, background: 'rgba(8,12,24,0.97)', zIndex: 1 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'rgba(34,210,100,0.85)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>导出分析数据</span>
                        <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.25)', fontSize: 16, lineHeight: 1, padding: 0 }}>×</button>
                    </div>

                    {/* 地区选择 */}
                    <div style={{ padding: '9px 13px 8px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 6 }}>选择地区</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                            {DOWNLOAD_REGIONS.map(r => (
                                <button key={r.key} onClick={() => !r.disabled && setRegion(r.key)}
                                    style={{ padding: '4px 9px', borderRadius: 5, cursor: r.disabled ? 'not-allowed' : 'pointer', fontSize: 11, fontWeight: region === r.key ? 700 : 400, fontFamily: 'system-ui,-apple-system,sans-serif', background: region === r.key ? 'rgba(34,197,94,0.18)' : 'rgba(255,255,255,0.05)', color: region === r.key ? 'rgba(34,210,100,0.9)' : r.disabled ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.45)', border: region === r.key ? '1px solid rgba(34,197,94,0.4)' : '1px solid rgba(255,255,255,0.08)', transition: 'all 0.15s' }}>
                                    {r.label}{r.disabled && <span style={{ fontSize: 9, marginLeft: 3, opacity: 0.5 }}>暂无</span>}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 指标分组多选 */}
                    <div style={{ padding: '6px 0 4px' }}>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.07em', textTransform: 'uppercase', padding: '0 13px', marginBottom: 4 }}>选择指标（可展开查看详细字段）</div>
                        {DOWNLOAD_GROUPS.map(grp => {
                            const isActive = !!selectedGroups[grp.key];
                            const isExpanded = expandedGroup === grp.key;
                            const grpFields = getGroupFields(grp.key);
                            return (
                                <div key={grp.key} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                    {/* 组标题行 */}
                                    <div style={{ display: 'flex', alignItems: 'center', padding: '6px 13px', gap: 8 }}>
                                        {/* 勾选框 */}
                                        <div onClick={() => toggleGroup(grp.key)} style={{ width: 15, height: 15, borderRadius: 3, border: isActive ? `1.5px solid ${grp.color}` : '1.5px solid rgba(255,255,255,0.15)', background: isActive ? `${grp.color}28` : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, cursor: 'pointer', transition: 'all 0.15s' }}>
                                            {isActive && <svg width="9" height="9" viewBox="0 0 12 12" fill="none"><polyline points="2,6 5,9 10,3" stroke={grp.color} strokeWidth="2.2" strokeLinecap="round" /></svg>}
                                        </div>
                                        {/* 组名 */}
                                        <span onClick={() => toggleGroup(grp.key)} style={{ fontSize: 12, fontWeight: isActive ? 600 : 400, color: isActive ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.35)', flex: 1, cursor: 'pointer' }}>{grp.label}</span>
                                        {/* 字段数量 & 展开箭头 */}
                                        {isActive && <span style={{ fontSize: 10, color: `${grp.color}99`, marginRight: 4 }}>{grpFields.length}项</span>}
                                        {grp.note && <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.2)', marginRight: 4 }}>{grp.note}</span>}
                                        <div onClick={() => setExpandedGroup(isExpanded ? null : grp.key)} style={{ cursor: 'pointer', color: 'rgba(255,255,255,0.25)', fontSize: 11, transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', userSelect: 'none' }}>▾</div>
                                    </div>
                                    {/* 展开的子字段 */}
                                    {isExpanded && (
                                        <div style={{ padding: '2px 13px 8px 36px', background: 'rgba(255,255,255,0.02)' }}>
                                            {grp.fields.map(f => {
                                                const checked = isActive && grpFields.includes(f.key);
                                                return (
                                                    <div key={f.key} onClick={() => { if (!isActive) return; toggleFieldInGroup(grp.key, f.key); }} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '4px 0', cursor: isActive ? 'pointer' : 'default', opacity: isActive ? 1 : 0.4 }}>
                                                        <div style={{ width: 12, height: 12, borderRadius: 2, border: checked ? `1.5px solid ${grp.color}` : '1.5px solid rgba(255,255,255,0.12)', background: checked ? `${grp.color}22` : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'all 0.12s' }}>
                                                            {checked && <svg width="8" height="8" viewBox="0 0 12 12" fill="none"><polyline points="2,6 5,9 10,3" stroke={grp.color} strokeWidth="2" strokeLinecap="round" /></svg>}
                                                        </div>
                                                        <span style={{ fontSize: 11, color: checked ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.28)' }}>{f.label}</span>
                                                    </div>
                                                );
                                            })}
                                            <div onClick={() => {
                                                const all = grp.fields.map(f => f.key);
                                                const cur = grpFields;
                                                setSelectedFields(prev => ({ ...prev, [grp.key]: cur.length === all.length ? [] : all }));
                                                if (!isActive) toggleGroup(grp.key);
                                            }} style={{ marginTop: 4, fontSize: 10, color: `${grp.color}88`, cursor: 'pointer', textDecoration: 'underline' }}>
                                                {grpFields.length === grp.fields.length ? '取消全选' : '全选本组'}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* 下载按钮 */}
                    <div style={{ padding: '8px 13px 11px', borderTop: '1px solid rgba(255,255,255,0.07)', position: 'sticky', bottom: 0, background: 'rgba(8,12,24,0.97)' }}>
                        <button onClick={handleDownload} disabled={loading || totalFields === 0 || activeGroups.length === 0}
                            style={{ width: '100%', padding: '7px 0', borderRadius: 7, cursor: totalFields === 0 ? 'not-allowed' : 'pointer', fontSize: 12, fontWeight: 600, fontFamily: 'system-ui,-apple-system,sans-serif', background: totalFields === 0 ? 'rgba(255,255,255,0.05)' : 'rgba(34,197,94,0.2)', color: totalFields === 0 ? 'rgba(255,255,255,0.2)' : 'rgba(34,210,100,0.9)', border: totalFields === 0 ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(34,197,94,0.4)', transition: 'all 0.15s', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                            {loading ? '正在生成CSV...' : (
                                <>
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                                    下载 CSV {totalFields > 0 && <span style={{ fontSize: 10, opacity: 0.6 }}>({totalFields} 列)</span>}
                                </>
                            )}
                        </button>
                        {totalFields === 0 && <div style={{ fontSize: 10, color: 'rgba(255,100,100,0.6)', textAlign: 'center', marginTop: 5 }}>请至少勾选一个指标组</div>}
                    </div>
                </div>
            )}
        </div>
    );
}

// ── 右上角控制 ────────────────────────────────
function TopRightControls({ vis, onToggleVis, mapStyle, onStyleChange }) {
    const [showStyleMenu, setShowStyleMenu] = useState(false);
    const MAP_STYLES = [
        { key: 'dark', label: 'Dark', style: 'mapbox://styles/mapbox/dark-v10' },
        { key: 'street', label: 'Street', style: 'mapbox://styles/mapbox/streets-v12' },
    ];
    const btnBase = { width: 34, height: 34, borderRadius: '50%', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(12px)', boxShadow: '0 2px 10px rgba(0,0,0,0.4)', transition: 'all 0.18s', fontSize: 15, border: 'none', fontFamily: 'system-ui,-apple-system,sans-serif' };
    return (
        <div style={{ position: 'absolute', top: 16, right: 16, display: 'flex', alignItems: 'center', gap: 7, zIndex: 200 }}>
            <button onClick={() => onToggleVis('lines')} title="公交线路" style={{ ...btnBase, background: vis?.lines ? 'rgba(0,200,170,0.22)' : 'rgba(8,12,24,0.82)', border: vis?.lines ? '1.5px solid rgba(0,200,170,0.55)' : '1px solid rgba(255,255,255,0.1)', color: vis?.lines ? 'rgba(0,220,180,0.95)' : 'rgba(255,255,255,0.4)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M3 12h18M3 6h18M3 18h18" /></svg>
            </button>
            <button onClick={() => onToggleVis('stops')} title="公交站点" style={{ ...btnBase, background: vis?.stops ? 'rgba(251,191,36,0.2)' : 'rgba(8,12,24,0.82)', border: vis?.stops ? '1.5px solid rgba(251,191,36,0.55)' : '1px solid rgba(255,255,255,0.1)', color: vis?.stops ? 'rgba(251,200,50,0.95)' : 'rgba(255,255,255,0.4)' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2" /></svg>
            </button>
            <div style={{ width: 1, height: 22, background: 'rgba(255,255,255,0.1)' }} />
            <DownloadPanel />
            <div style={{ width: 1, height: 22, background: 'rgba(255,255,255,0.1)' }} />
            <div style={{ position: 'relative' }}>
                <button onClick={() => setShowStyleMenu(v => !v)} title="地图样式" style={{ ...btnBase, background: showStyleMenu ? 'rgba(59,130,246,0.25)' : 'rgba(8,12,24,0.82)', border: showStyleMenu ? '1.5px solid rgba(59,130,246,0.6)' : '1px solid rgba(255,255,255,0.1)', color: showStyleMenu ? '#60a5fa' : 'rgba(255,255,255,0.4)' }}>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polygon points="3,6 9,3 15,6 21,3 21,18 15,21 9,18 3,21" /><line x1="9" y1="3" x2="9" y2="18" /><line x1="15" y1="6" x2="15" y2="21" /></svg>
                </button>
                {showStyleMenu && (
                    <div style={{ position: 'absolute', top: 40, right: 0, background: 'rgba(8,12,24,0.97)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 9, overflow: 'hidden', boxShadow: '0 8px 24px rgba(0,0,0,0.6)', backdropFilter: 'blur(16px)', minWidth: 110 }}>
                        {MAP_STYLES.map((s, i) => (
                            <div key={s.key} onClick={() => { onStyleChange(s.style); setShowStyleMenu(false); }} style={{ padding: '9px 13px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, borderBottom: i < MAP_STYLES.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none', background: mapStyle === s.style ? 'rgba(59,130,246,0.14)' : 'transparent', transition: 'background 0.12s', fontFamily: 'system-ui,-apple-system,sans-serif' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
                                onMouseLeave={e => e.currentTarget.style.background = mapStyle === s.style ? 'rgba(59,130,246,0.14)' : 'transparent'}
                            >
                                <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: mapStyle === s.style ? '#3b82f6' : 'rgba(255,255,255,0.18)' }} />
                                <span style={{ fontSize: 12, color: mapStyle === s.style ? '#93c5fd' : 'rgba(200,215,235,0.7)', fontWeight: mapStyle === s.style ? 600 : 400 }}>{s.label}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

// ── 搜索框 ────────────────────────────────────
function SearchBox({ stopsData, onFlyTo, onHighlight }) {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [focused, setFocused] = useState(false);
    const handleChange = (e) => {
        const q = e.target.value; setQuery(q);
        if (!q.trim() || q.length < 2) { setResults([]); onHighlight(null); return; }
        if (!stopsData?.features) return;
        setResults(stopsData.features.filter(f => (f.properties?.name || '').includes(q)).slice(0, 8));
    };
    const handleGeoSearch = async (q) => {
        if (!q.trim()) return;
        try {
            const res = await fetch(`https://restapi.amap.com/v3/geocode/geo?address=${encodeURIComponent(q)}&city=北京&key=${AMAP_KEY}`);
            const data = await res.json();
            if (data.status === '1' && data.geocodes?.length > 0) {
                const [lon, lat] = data.geocodes[0].location.split(',').map(Number);
                onFlyTo(lon, lat, 15); setResults([]);
            }
        } catch (e) { }
    };
    const handleKeyDown = async (e) => {
        if (e.key !== 'Enter') return;
        if (results.length > 0) { selectStop(results[0]); return; }
        handleGeoSearch(query);
    };
    const selectStop = (feat) => {
        const [lon, lat] = feat.geometry.coordinates;
        onFlyTo(lon, lat, 16); onHighlight(feat);
        setQuery(feat.properties?.name || ''); setResults([]);
    };
    return (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 200, width: 300 }}>
            <div style={{ display: 'flex', alignItems: 'center', background: focused ? 'rgba(12,18,36,0.97)' : 'rgba(8,12,24,0.85)', border: focused ? '1.5px solid rgba(59,130,246,0.45)' : '1px solid rgba(255,255,255,0.1)', borderRadius: results.length > 0 ? '10px 10px 0 0' : 10, boxShadow: focused ? '0 0 0 3px rgba(59,130,246,0.1),0 4px 16px rgba(0,0,0,0.5)' : '0 4px 16px rgba(0,0,0,0.4)', padding: '0 12px', backdropFilter: 'blur(16px)', transition: 'all 0.15s' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={focused ? 'rgba(96,165,250,0.8)' : 'rgba(255,255,255,0.25)'} strokeWidth="2.5" style={{ marginRight: 9, flexShrink: 0 }}>
                    <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                </svg>
                <input value={query} onChange={handleChange} onKeyDown={handleKeyDown}
                    onFocus={() => setFocused(true)} onBlur={() => setTimeout(() => setFocused(false), 200)}
                    placeholder="搜索站点，或输入地点 Enter 跳转"
                    style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'rgba(220,232,248,0.9)', fontSize: 13, fontFamily: 'system-ui,-apple-system,sans-serif', padding: '10px 0' }}
                />
                {query && <button onClick={() => { setQuery(''); setResults([]); onHighlight(null); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.22)', fontSize: 17, padding: '0 2px', lineHeight: 1 }}>×</button>}
            </div>
            {results.length > 0 && (
                <div style={{ background: 'rgba(8,12,24,0.97)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.08)', borderTop: 'none', borderRadius: '0 0 10px 10px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
                    {results.map((feat, i) => (
                        <div key={i} onClick={() => selectStop(feat)} style={{ padding: '9px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, borderBottom: i < results.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none', transition: 'background 0.1s', fontFamily: 'system-ui,-apple-system,sans-serif' }} onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'} onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 8v4l3 3" /></svg>
                            <div>
                                <div style={{ color: 'rgba(220,232,248,0.88)', fontSize: 13 }}>{feat.properties?.name}</div>
                                {feat.properties?.line_count > 0 && <div style={{ color: 'rgba(251,191,36,0.65)', fontSize: 11, marginTop: 1 }}>{feat.properties.line_count} 条线路</div>}
                            </div>
                        </div>
                    ))}
                    <div onClick={() => handleGeoSearch(query)} style={{ padding: '9px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, borderTop: '1px solid rgba(255,255,255,0.05)', background: 'rgba(59,130,246,0.05)', transition: 'background 0.1s', fontFamily: 'system-ui,-apple-system,sans-serif' }} onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.13)'} onMouseLeave={e => e.currentTarget.style.background = 'rgba(59,130,246,0.05)'}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="rgba(96,165,250,0.7)" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>
                        <span style={{ color: 'rgba(96,165,250,0.85)', fontSize: 13 }}>搜索地点「{query}」</span>
                    </div>
                </div>
            )}
        </div>
    );
}

// ── 底部面板 ──────────────────────────────────
function GridDetailPanel({ grid, onClose, tciSession, hasIsochrone, selectedZone, zoneIsoSession, onZoneIsoSessionChange }) {
    if (!grid && !selectedZone) return null;
    if (selectedZone) {
        const z = ZONES.find(x => x.id === selectedZone);
        return (
            <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', width: 480, background: 'rgba(8,12,24,0.94)', border: '1px solid rgba(255,255,255,0.09)', borderRadius: 13, backdropFilter: 'blur(20px)', boxShadow: '0 -4px 24px rgba(0,0,0,0.5)', zIndex: 300, fontFamily: 'system-ui,-apple-system,sans-serif' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(96,196,255,0.75)', letterSpacing: '0.09em', textTransform: 'uppercase' }}>交通小区等时圈</span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.7)' }}>{z?.name}</span>
                        <div style={{ display: 'flex', gap: 3 }}>
                            {[{ k: 'morning', l: '早高峰' }, { k: 'midday', l: '平峰' }].map(s => (
                                <button key={s.k} onClick={() => onZoneIsoSessionChange(s.k)} style={{ padding: '2px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 11, fontWeight: 600, fontFamily: 'system-ui,-apple-system,sans-serif', background: zoneIsoSession === s.k ? 'rgba(255,255,255,0.12)' : 'transparent', color: zoneIsoSession === s.k ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.3)', border: zoneIsoSession === s.k ? '1px solid rgba(255,255,255,0.2)' : '1px solid transparent' }}>
                                    {s.l}
                                </button>
                            ))}
                        </div>
                    </div>
                    <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 5, color: 'rgba(255,255,255,0.35)', cursor: 'pointer', width: 20, height: 20, fontSize: 12, lineHeight: '20px', textAlign: 'center' }}>×</button>
                </div>
                <div style={{ padding: '10px 14px 12px' }}>
                    <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: 20, height: 3, background: 'rgba(50,255,180,0.9)', borderRadius: 2 }} />
                            <span style={{ fontSize: 11, color: 'rgba(200,220,245,0.6)' }}>公交 45 分钟等时圈</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: 20, height: 3, background: 'rgba(255,140,0,0.9)', borderRadius: 2 }} />
                            <span style={{ fontSize: 11, color: 'rgba(200,220,245,0.6)' }}>小汽车 30 分钟等时圈</span>
                        </div>
                    </div>
                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', lineHeight: 1.7 }}>
                        点击地图其他位置关闭等时圈显示。等时圈由射线采样插值法构建，采集时段：{zoneIsoSession === 'morning' ? '早高峰 08:00' : '平峰 15:00'}。
                    </div>
                </div>
            </div>
        );
    }

    const p = grid.properties || {};
    const POI_CATS = [
        { key: 'poi_医疗保健', label: '医疗', color: '#f87171' },
        { key: 'poi_科教文化', label: '科教', color: '#60a5fa' },
        { key: 'poi_购物消费', label: '购物', color: '#fbbf24' },
        { key: 'poi_公司企业', label: '企业', color: '#a78bfa' },
        { key: 'poi_生活服务', label: '生活', color: '#34d399' },
        { key: 'poi_休闲娱乐', label: '休闲', color: '#f472b6' },
        { key: 'poi_运动健身', label: '运动', color: '#fb923c' },
        { key: 'poi_商务住宅', label: '住宅', color: '#94a3b8' },
    ].map(c => ({ ...c, value: p[c.key] || 0 }));
    const maxVal = Math.max(...POI_CATS.map(c => c.value), 1);
    const SCORES = [
        { label: '需求密度', val: p.demand_final ?? p.demand_kde_norm, color: '#fbbf24' },
        { label: '覆盖度', val: p.coverage_score, color: '#34d399' },
        { label: '等时圈', val: p.iso_score_combined, color: '#818cf8' },
        // FIX 3: Show composite score in detail panel
        { label: '综合可达性', val: p.composite, color: '#22c55e' },
    ].filter(s => s.val != null && s.val > 0);
    const sess = TCI_SESSIONS.find(s => s.key === tciSession);
    const tciVal = sess ? p[sess.raw] : p.tci_mean;
    const tciLabel = sess ? `TCI(${sess.label})` : 'TCI均值';
    return (
        <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', width: 520, height: 168, background: 'rgba(8,12,24,0.94)', border: '1px solid rgba(255,255,255,0.09)', borderRadius: 13, backdropFilter: 'blur(20px)', boxShadow: '0 -4px 24px rgba(0,0,0,0.5)', zIndex: 300, display: 'flex', flexDirection: 'column', fontFamily: 'system-ui,-apple-system,sans-serif', animation: 'slideUp 0.2s ease' }}>
            <style>{`@keyframes slideUp{from{transform:translateX(-50%) translateY(14px);opacity:0}to{transform:translateX(-50%) translateY(0);opacity:1}}`}</style>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 13px 6px', borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(96,196,255,0.75)', letterSpacing: '0.09em', textTransform: 'uppercase' }}>网格详情</span>
                    {p.cx != null && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)' }}>{Number(p.cx).toFixed(3)}°E {Number(p.cy).toFixed(3)}°N</span>}
                    {hasIsochrone && (
                        <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: 'rgba(100,180,255,0.12)', border: '1px solid rgba(100,180,255,0.3)', color: 'rgba(100,200,255,0.8)', fontWeight: 600 }}>
                            ◎ 等时圈已显示
                        </span>
                    )}
                    {SCORES.map(s => (
                        <div key={s.label} style={{ padding: '1px 7px', borderRadius: 4, background: `${s.color}15`, border: `1px solid ${s.color}30`, display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span style={{ fontSize: 10, color: 'rgba(180,200,225,0.45)' }}>{s.label}</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: s.color }}>{Number(s.val).toFixed(1)}</span>
                        </div>
                    ))}
                    {tciVal != null && (
                        <div style={{ padding: '1px 7px', borderRadius: 4, background: 'rgba(251,146,60,0.12)', border: '1px solid rgba(251,146,60,0.3)', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span style={{ fontSize: 10, color: 'rgba(180,200,225,0.45)' }}>{tciLabel}</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: '#fb923c' }}>{Number(tciVal).toFixed(3)}</span>
                            <span style={{ fontSize: 9, fontWeight: 700, color: tciVal >= 0.7 ? '#4ade80' : tciVal >= 0.5 ? '#fbbf24' : '#f87171', marginLeft: 2 }}>{tciVal >= 0.7 ? '强' : tciVal >= 0.5 ? '中' : '弱'}</span>
                        </div>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.16)' }}>{p.poi_count || 0} POI</span>
                    <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 5, color: 'rgba(255,255,255,0.35)', cursor: 'pointer', width: 20, height: 20, fontSize: 12, lineHeight: '20px', textAlign: 'center' }}>×</button>
                </div>
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', padding: '6px 14px 5px', gap: 5 }}>
                {POI_CATS.map(c => (
                    <div key={c.key} style={{ flex: 1, maxWidth: 56, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: c.value > 0 ? c.color : 'rgba(255,255,255,0.1)' }}>{c.value > 0 ? c.value : '—'}</span>
                        <div style={{ width: '100%', height: 46, display: 'flex', alignItems: 'flex-end', background: 'rgba(255,255,255,0.04)', borderRadius: '3px 3px 0 0', overflow: 'hidden' }}>
                            <div style={{ width: '100%', height: c.value > 0 ? `${Math.max((c.value / maxVal) * 100, 4)}%` : '0%', background: `linear-gradient(180deg,${c.color},${c.color}88)`, borderRadius: '2px 2px 0 0', transition: 'height 0.4s ease' }} />
                        </div>
                        <div style={{ fontSize: 10, color: c.value > 0 ? 'rgba(200,215,240,0.6)' : 'rgba(255,255,255,0.12)', textAlign: 'center' }}>{c.label}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ══════════════════════════════════════════════
const MapContainer = ({ data, vis, onToggleVis, tciSession, onSessionChange }) => {
    const [demandData, setDemandData] = useState(null);
    const [isochroneData, setIsochroneData] = useState(null);
    const [coverageData, setCoverageData] = useState(null);
    const [tciData, setTciData] = useState(null);
    const [busLinesData, setBusLinesData] = useState(null);
    const [stopsData, setStopsData] = useState(null);
    const [zoneIsoData, setZoneIsoData] = useState(null);
    const [zonesData, setZonesData] = useState(null);
    const [hoverInfo, setHoverInfo] = useState(null);
    const [selectedGrid, setSelectedGrid] = useState(null);
    const [highlightStop, setHighlightStop] = useState(null);
    const [mapStyle, setMapStyle] = useState('mapbox://styles/mapbox/dark-v10');
    const [viewState, setViewState] = useState({ longitude: 116.4074, latitude: 39.920, zoom: 10.0, pitch: 0, bearing: 0 });

    const [isoPolysData, setIsoPolysData] = useState(null);
    const isoPolysLoading = useRef(false);
    const [selectedIsoPoly, setSelectedIsoPoly] = useState(null);

    const [selectedZone, setSelectedZone] = useState(null);
    const [zoneIsoSession, setZoneIsoSession] = useState('morning');
    const [compositeData, setCompositeData] = useState(null);
    const zoneIsoLoading = useRef(false);

    useEffect(() => { fetch('/data/output/demand_grid_beijing.geojson').then(r => r.json()).then(setDemandData).catch(() => { }); }, []);
    useEffect(() => { fetch('/data/output/isochrone_grid_beijing.geojson').then(r => r.json()).then(setIsochroneData).catch(() => { }); }, []);
    useEffect(() => { fetch('/data/output/coverage_grid_beijing.geojson').then(r => r.json()).then(setCoverageData).catch(() => { }); }, []);
    useEffect(() => { fetch('/data/output/tci_grid_beijing.geojson').then(r => r.json()).then(setTciData).catch(() => { }); }, []);
    useEffect(() => {
        fetch('/data/output/bus_lines_beijing.geojson').then(r => r.json()).then(setBusLinesData).catch(() => { });
        fetch('/data/output/bus_stops_beijing.geojson').then(r => r.json()).then(setStopsData).catch(() => { });
    }, []);
    useEffect(() => {
        if (vis?.tci) {
            fetch('/data/output/zones_beijing.geojson')
                .then(r => r.json()).then(setZonesData).catch(() => { });
        }
    }, [vis?.tci]);
    useEffect(() => {
        if (vis?.composite || vis?.imbalance) {
            if (!compositeData) {
                fetch('/data/output/composite_xicheng.geojson')
                    .then(r => r.json()).then(setCompositeData).catch(() => { });
            }
        }
    }, [vis?.composite, vis?.imbalance]);

    const loadZoneIso = useCallback(() => {
        if (zoneIsoData || zoneIsoLoading.current) return;
        zoneIsoLoading.current = true;
        fetch('/data/output/zone_isochrones.geojson')
            .then(r => r.json())
            .then(d => { setZoneIsoData(d); })
            .catch(() => { zoneIsoLoading.current = false; });
    }, [zoneIsoData]);

    const loadIsoPolys = useCallback(() => {
        if (isoPolysData || isoPolysLoading.current) return;
        isoPolysLoading.current = true;
        fetch('/data/output/isochrone_polys.geojson')
            .then(r => r.json())
            .then(d => { setIsoPolysData(d); })
            .catch(() => { isoPolysLoading.current = false; });
    }, [isoPolysData]);

    const handleGridClick = useCallback((info) => {
        const obj = info?.object || null;
        setSelectedGrid(obj);
        setSelectedIsoPoly(null);
        setSelectedZone(null);
        if (!obj) return;
        const isoIdx = obj.properties?.iso_index;
        if (isoIdx == null || isoIdx < 0) return;
        if (isoPolysData) {
            const feat = isoPolysData.features[isoIdx];
            if (feat) setSelectedIsoPoly(feat);
        } else {
            loadIsoPolys();
        }
    }, [isoPolysData, loadIsoPolys]);

    useEffect(() => {
        if (!isoPolysData || !selectedGrid) return;
        const isoIdx = selectedGrid.properties?.iso_index;
        if (isoIdx == null || isoIdx < 0) return;
        const feat = isoPolysData.features[isoIdx];
        if (feat) setSelectedIsoPoly(feat);
    }, [isoPolysData, selectedGrid]);

    const handleZoneClick = useCallback((zoneId) => {
        if (selectedZone === zoneId) {
            setSelectedZone(null);
            return;
        }
        setSelectedZone(zoneId);
        setSelectedGrid(null);
        setSelectedIsoPoly(null);
        loadZoneIso();
        const z = ZONES.find(x => x.id === zoneId);
        if (z) setViewState(v => ({ ...v, longitude: z.cx, latitude: z.cy, zoom: 13, transitionDuration: 600 }));
    }, [selectedZone, loadZoneIso]);

    const handleFlyTo = useCallback((lon, lat, zoom) => {
        setViewState(v => ({ ...v, longitude: lon, latitude: lat, zoom, transitionDuration: 700 }));
    }, []);

    const handleClose = useCallback(() => {
        setSelectedGrid(null);
        setSelectedIsoPoly(null);
        setSelectedZone(null);
    }, []);

    const tciField = useMemo(() => {
        const sess = TCI_SESSIONS.find(s => s.key === tciSession);
        return sess?.field ?? 'tci_morning_norm';
    }, [tciSession]);

    const zoneIsoFeatures = useMemo(() => {
        if (!zoneIsoData || !selectedZone) return { bus: null, car: null };
        const bus = zoneIsoData.features.find(f => f.properties.zone_id === selectedZone && f.properties.mode === 'bus' && f.properties.session === zoneIsoSession) || null;
        const car = zoneIsoData.features.find(f => f.properties.zone_id === selectedZone && f.properties.mode === 'car' && f.properties.session === zoneIsoSession) || null;
        return { bus, car };
    }, [zoneIsoData, selectedZone, zoneIsoSession]);

    const layers = useMemo(() => {
        const out = [];

        // ── 底层：各类网格热力图 ──────────────────────────────────────────────
        if (vis?.demand && demandData) out.push(new GeoJsonLayer({
            id: 'demand-grid', data: demandData, pickable: true, stroked: false, filled: true,
            parameters: { depthTest: false },
            getFillColor: f => interpolate(DEMAND_STOPS, f.properties?.demand_final ?? f.properties?.demand_kde_norm ?? 0),
            onHover: info => setHoverInfo(info?.object ? info : null),
            onClick: handleGridClick,
            updateTriggers: { getFillColor: [vis?.demand] },
        }));

        if (vis?.isochrone && isochroneData) out.push(new GeoJsonLayer({
            id: 'isochrone-grid', data: isochroneData, pickable: true, stroked: false, filled: true,
            parameters: { depthTest: false },
            getFillColor: f => {
                const raw = f.properties?.iso_score_combined ?? 0;
                if (!raw || raw <= 0) return [0, 0, 0, 0];
                const logScore = Math.log1p(raw) / Math.log1p(100) * 100;
                return interpolate(ISO_STOPS, logScore);
            },
            onHover: info => setHoverInfo(info?.object ? info : null),
            onClick: info => { handleGridClick(info); if (info?.object?.properties?.iso_index != null) loadIsoPolys(); },
        }));

        if (vis?.coverage && coverageData) out.push(new GeoJsonLayer({
            id: 'coverage-grid', data: coverageData, pickable: true, stroked: false, filled: true,
            parameters: { depthTest: false },
            getFillColor: f => interpolate(COV_STOPS, f.properties?.coverage_score ?? 0),
            onHover: info => setHoverInfo(info?.object ? info : null),
            onClick: handleGridClick,
        }));

        if (vis?.tci && zonesData) out.push(new GeoJsonLayer({
            id: 'zones-boundary', data: zonesData,
            pickable: false, stroked: true, filled: true,
            getFillColor: [255, 255, 255, 8],
            getLineColor: [255, 255, 255, 60],
            getLineWidth: 1, lineWidthMinPixels: 1,
        }));

        if (vis?.tci && zonesData && selectedZone) {
            const highlighted = {
                type: 'FeatureCollection',
                features: zonesData.features.filter(f => f.properties.id === selectedZone)
            };
            out.push(new GeoJsonLayer({
                id: 'zones-highlight', data: highlighted,
                pickable: false, stroked: true, filled: true,
                getFillColor: [255, 255, 255, 30],
                getLineColor: [255, 255, 255, 200],
                getLineWidth: 2, lineWidthMinPixels: 2,
            }));
        }

        // 综合评价两层：composite 用对数压缩，imbalance 用低 alpha
        if (vis?.composite && compositeData) out.push(new GeoJsonLayer({
            id: 'composite-grid', data: compositeData,
            pickable: true, stroked: false, filled: true,
            parameters: { depthTest: false, blend: true, blendFunc: [770, 771], blendEquation: 32774 },
            getFillColor: f => {
                const raw = f.properties?.composite ?? 0;
                if (!raw || raw <= 0) return [0, 0, 0, 0];
                const color = interpolate(COMPOSITE_STOPS, raw); color[3] = f.properties?.alpha ?? 60; return color;
            },
            onHover: info => setHoverInfo(info?.object ? info : null),
            onClick: handleGridClick,
        }));

        if (vis?.imbalance && compositeData) out.push(new GeoJsonLayer({
            id: 'imbalance-grid', data: compositeData,
            pickable: true, stroked: false, filled: true,
            parameters: { depthTest: false, blend: true, blendFunc: [770, 771], blendEquation: 32774 },
            getFillColor: f => {
                const r = f.properties?.fill_r ?? 0;
                const g = f.properties?.fill_g ?? 0;
                const b = f.properties?.fill_b ?? 0;
                if (r === 0 && g === 0 && b === 0) return [0, 0, 0, 0];
                return [r, g, b, 60];
            },
            onHover: info => setHoverInfo(info?.object ? info : null),
            onClick: handleGridClick,
        }));

        // ── 等时圈轮廓（在网格之上，在站点之下）────────────────────────────────
        if (selectedIsoPoly) {
            out.push(new GeoJsonLayer({
                id: 'selected-iso-fill',
                data: { type: 'FeatureCollection', features: [selectedIsoPoly] },
                pickable: false, stroked: false, filled: true,
                getFillColor: [255, 200, 50, 12],
            }));
            out.push(new GeoJsonLayer({
                id: 'selected-iso-outline',
                data: { type: 'FeatureCollection', features: [selectedIsoPoly] },
                pickable: false, stroked: true, filled: false,
                getLineColor: [50, 255, 180, 240], getLineWidth: 2, lineWidthMinPixels: 1.5,
            }));
        }

        if (zoneIsoFeatures.bus) {
            out.push(new GeoJsonLayer({
                id: 'zone-bus-fill',
                data: { type: 'FeatureCollection', features: [zoneIsoFeatures.bus] },
                pickable: false, stroked: false, filled: true,
                getFillColor: [50, 255, 180, 18],
            }));
            out.push(new GeoJsonLayer({
                id: 'zone-bus-outline',
                data: { type: 'FeatureCollection', features: [zoneIsoFeatures.bus] },
                pickable: false, stroked: true, filled: false,
                getLineColor: [50, 255, 180, 230], getLineWidth: 2.5, lineWidthMinPixels: 2,
            }));
        }

        if (zoneIsoFeatures.car) {
            out.push(new GeoJsonLayer({
                id: 'zone-car-fill',
                data: { type: 'FeatureCollection', features: [zoneIsoFeatures.car] },
                pickable: false, stroked: false, filled: true,
                getFillColor: [255, 140, 0, 18],
            }));
            out.push(new GeoJsonLayer({
                id: 'zone-car-outline',
                data: { type: 'FeatureCollection', features: [zoneIsoFeatures.car] },
                pickable: false, stroked: true, filled: false,
                getLineColor: [255, 140, 0, 230], getLineWidth: 2.5, lineWidthMinPixels: 2,
            }));
        }

        if (selectedZone) {
            const z = ZONES.find(x => x.id === selectedZone);
            if (z) {
                const pt = { type: 'Feature', geometry: { type: 'Point', coordinates: [z.cx, z.cy] }, properties: {} };
                out.push(new GeoJsonLayer({
                    id: 'zone-center', data: { type: 'FeatureCollection', features: [pt] },
                    pickable: false, stroked: true, filled: true, pointType: 'circle',
                    getFillColor: [255, 255, 255, 220], getLineColor: [0, 0, 0, 180],
                    getLineWidth: 2, pointRadiusUnits: 'pixels', getPointRadius: 6,
                }));
            }
        }

        // ── 顶层：公交线路和站点始终渲染在所有网格层之上 ─────────────────────
        const linesSource = busLinesData;
        if (vis?.lines && linesSource?.features?.length > 0) out.push(new GeoJsonLayer({
            id: 'bus-lines', data: linesSource, pickable: false, stroked: true, filled: false,
            getLineColor: [0, 200, 170, 140], getLineWidth: 1.2, lineWidthMinPixels: 1,
        }));

        const stopsSource = stopsData;
        if (vis?.stops && stopsSource?.features?.length > 0) out.push(new GeoJsonLayer({
            id: 'bus-stops', data: stopsSource, pickable: true, stroked: true, filled: true, pointType: 'circle',
            getFillColor: [255, 210, 60, 215], getLineColor: [20, 20, 30, 140],
            getLineWidth: 1, pointRadiusUnits: 'pixels', getPointRadius: 3.5,
            onHover: info => setHoverInfo(info?.object ? info : null),
        }));

        // 用户上传的数据：独立图层，不受 vis 开关影响
        if (data?.features?.length > 0) {
            const uploadedLines = data.features.filter(f => f.geometry?.type?.includes('Line'));
            const uploadedPoints = data.features.filter(f => f.geometry?.type === 'Point');
            if (uploadedLines.length > 0) out.push(new GeoJsonLayer({
                id: 'uploaded-lines',
                data: { type: 'FeatureCollection', features: uploadedLines },
                pickable: false, stroked: true, filled: false,
                getLineColor: [255, 100, 100, 200], getLineWidth: 1.5, lineWidthMinPixels: 1.5,
            }));
            if (uploadedPoints.length > 0) out.push(new GeoJsonLayer({
                id: 'uploaded-stops',
                data: { type: 'FeatureCollection', features: uploadedPoints },
                pickable: false, stroked: true, filled: true, pointType: 'circle',
                getFillColor: [255, 100, 100, 220], getLineColor: [255,255,255,140],
                getLineWidth: 1, pointRadiusUnits: 'pixels', getPointRadius: 5,
            }));
        }

        if (highlightStop) {
            out.push(new GeoJsonLayer({
                id: 'highlight-stop', data: { type: 'FeatureCollection', features: [highlightStop] },
                pickable: false, stroked: true, filled: true, pointType: 'circle',
                getFillColor: [255, 60, 60, 255], getLineColor: [255, 255, 255, 255],
                getLineWidth: 2, pointRadiusUnits: 'pixels', getPointRadius: 11,
            }));
        }

        return out;
    }, [data, stopsData, busLinesData, demandData, coverageData, isochroneData, tciData, vis, highlightStop, tciField, handleGridClick, loadIsoPolys, selectedIsoPoly, zoneIsoFeatures, selectedZone, zonesData, compositeData]);

    return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <DeckGL viewState={viewState} onViewStateChange={({ viewState: vs }) => setViewState(vs)} controller={true} layers={layers}>
                <Map mapboxAccessToken={MAPBOX_TOKEN} mapStyle={mapStyle} />
            </DeckGL>
            <SearchBox stopsData={stopsData} onFlyTo={handleFlyTo} onHighlight={setHighlightStop} />
            {/* FIX 2: tciSession/onSessionChange props removed from TopRightControls */}
            <TopRightControls vis={vis} onToggleVis={onToggleVis} mapStyle={mapStyle} onStyleChange={setMapStyle} />
            <MapLegend vis={vis} tciSession={tciSession} />
            <Tooltip info={hoverInfo} tciSession={tciSession} />
            <GridDetailPanel
                grid={selectedGrid}
                onClose={handleClose}
                tciSession={tciSession}
                hasIsochrone={!!selectedIsoPoly}
                selectedZone={selectedZone}
                zoneIsoSession={zoneIsoSession}
                onZoneIsoSessionChange={setZoneIsoSession}
            />
            {vis?.tci && (
                <div style={{ position: 'absolute', bottom: selectedZone ? 220 : 28, left: 16, display: 'flex', flexDirection: 'column', gap: 5, zIndex: 200, transition: 'bottom 0.2s' }}>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 2, fontFamily: 'system-ui,-apple-system,sans-serif', letterSpacing: '0.06em' }}>交通小区等时圈</div>
                    {ZONES.map(z => (
                        <button key={z.id} onClick={() => handleZoneClick(z.id)} style={{
                            padding: '5px 11px', borderRadius: 7, cursor: 'pointer',
                            fontSize: 11, fontWeight: selectedZone === z.id ? 700 : 400,
                            fontFamily: 'system-ui,-apple-system,sans-serif',
                            background: selectedZone === z.id ? 'rgba(255,255,255,0.12)' : 'rgba(8,12,24,0.82)',
                            color: selectedZone === z.id ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.4)',
                            border: selectedZone === z.id ? '1.5px solid rgba(255,255,255,0.3)' : '1px solid rgba(255,255,255,0.1)',
                            backdropFilter: 'blur(12px)', transition: 'all 0.15s', textAlign: 'left',
                        }}>
                            {selectedZone === z.id ? '▶ ' : ''}{z.name}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};

export default MapContainer;