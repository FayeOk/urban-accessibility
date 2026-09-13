import React, { useState, useRef, useEffect } from 'react';

// ── 通用组件 ──────────────────────────────────

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 10, fontWeight: 600,
      color: 'rgba(255,255,255,0.22)',
      letterSpacing: '0.1em', textTransform: 'uppercase',
      marginBottom: 8, marginTop: 14,
    }}>{children}</div>
  );
}

// 问号 tooltip
function HintIcon({ text }) {
  const [show, setShow] = useState(false);
  const ref = useRef(null);
  return (
    <div style={{ position: 'relative', display: 'inline-flex' }} ref={ref}>
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        style={{
          width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
          border: '1px solid rgba(255,255,255,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'help', color: 'rgba(255,255,255,0.3)', fontSize: 9, fontWeight: 700,
          userSelect: 'none',
        }}
      >?</div>
      {show && (
        <div style={{
          position: 'fixed',
          marginLeft: 20,
          background: 'rgba(15,20,35,0.98)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 7, padding: '7px 10px',
          fontSize: 11, color: 'rgba(200,215,235,0.8)',
          lineHeight: 1.65, whiteSpace: 'pre-line',
          zIndex: 9999, width: 180,
          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
          pointerEvents: 'none',
        }}>{text}</div>
      )}
    </div>
  );
}

function SliderRow({ label, value, min, max, step = 1, unit = '', onChange, hint }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>{label}</span>
          {hint && <HintIcon text={hint} />}
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.7)', fontVariantNumeric: 'tabular-nums' }}>
          {value}{unit}
        </span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{ width: '100%', height: 3, cursor: 'pointer', accentColor: 'rgba(255,255,255,0.5)' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.18)' }}>{min}{unit}</span>
        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.18)' }}>{max}{unit}</span>
      </div>
    </div>
  );
}

function DualSlider({ labelA, labelB, valueA, onChange, hint }) {
  const pct = Math.round(valueA * 100);
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>{labelA}</span>
          {hint && <HintIcon text={hint} />}
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.55)', fontVariantNumeric: 'tabular-nums' }}>
          {pct}% · {100 - pct}%
        </span>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>{labelB}</span>
      </div>
      <div style={{ height: 3, borderRadius: 2, overflow: 'hidden', background: 'rgba(255,255,255,0.08)', display: 'flex', marginBottom: 4 }}>
        <div style={{ width: `${pct}%`, background: 'rgba(255,255,255,0.4)', transition: 'width 0.1s' }} />
        <div style={{ flex: 1, background: 'rgba(255,255,255,0.12)' }} />
      </div>
      <input type="range" min={0} max={100} step={5} value={pct}
        onChange={e => onChange(Number(e.target.value) / 100)}
        style={{ width: '100%', height: 3, cursor: 'pointer', accentColor: 'rgba(255,255,255,0.5)' }}
      />
    </div>
  );
}

function PoiWeightTable({ weights, onChange }) {
  const CATS = [
    { key: '医疗保健', max: 5 }, { key: '科教文化', max: 5 },
    { key: '购物消费', max: 4 }, { key: '商务住宅', max: 4 },
    { key: '公司企业', max: 4 }, { key: '生活服务', max: 3 },
    { key: '休闲娱乐', max: 3 }, { key: '运动健身', max: 3 },
    { key: '餐饮美食', max: 3 }, { key: '交通设施', max: 2 },
    { key: '汽车相关', max: 2 },
  ];
  return (
    <div>
      {CATS.map(c => (
        <div key={c.key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', width: 52, flexShrink: 0 }}>{c.key}</span>
          <input type="range" min={0} max={c.max} step={0.5} value={weights[c.key] ?? 1.0}
            onChange={e => onChange(c.key, Number(e.target.value))}
            style={{ flex: 1, height: 3, cursor: 'pointer', accentColor: 'rgba(255,255,255,0.5)' }}
          />
          <span style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.6)', width: 22, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
            {(weights[c.key] ?? 1.0).toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

function RecalcButton({ onClick }) {
  const [clicked, setClicked] = useState(false);
  const handle = () => {
    setClicked(true);
    setTimeout(() => setClicked(false), 2000);
    if (onClick) onClick(); else alert('后端接口待接入');
  };
  return (
    <button onClick={handle} style={{
      width: '100%', height: 28, marginTop: 12,
      background: 'transparent',
      border: '1px solid rgba(255,255,255,0.15)',
      borderRadius: 6, cursor: 'pointer',
      color: clicked ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.3)',
      fontSize: 11, fontWeight: 500,
      fontFamily: 'system-ui,-apple-system,sans-serif',
      transition: 'all 0.15s', letterSpacing: '0.03em',
    }}
      onMouseEnter={e => e.target.style.borderColor = 'rgba(255,255,255,0.3)'}
      onMouseLeave={e => e.target.style.borderColor = 'rgba(255,255,255,0.15)'}
    >
      {clicked ? '待接入后端...' : '重新计算'}
    </button>
  );
}

function Toggle({ active, onClick }) {
  return (
    <div onClick={e => { e.stopPropagation(); onClick(); }} style={{
      width: 28, height: 15, borderRadius: 8, flexShrink: 0, cursor: 'pointer',
      background: active ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.1)',
      position: 'relative', transition: 'background 0.2s',
    }}>
      <div style={{
        position: 'absolute', top: 2, left: active ? 15 : 2,
        width: 11, height: 11, borderRadius: '50%',
        background: active ? '#111' : 'rgba(255,255,255,0.5)',
        transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
      }} />
    </div>
  );
}

// TCI 时段 Tab
const TCI_SESSIONS = [
  { key: 'morning', label: '早高峰', mean: '0.523' },
  { key: 'midday', label: '平峰', mean: '0.509' },
  { key: 'evening', label: '晚高峰', mean: '0.444' },
];

function TciSessionTab({ tciSession, onSessionChange }) {
  return (
    <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
      {TCI_SESSIONS.map(s => (
        <button key={s.key} onClick={() => onSessionChange(s.key)} style={{
          flex: 1, padding: '5px 0', borderRadius: 6, cursor: 'pointer',
          fontSize: 11, fontWeight: tciSession === s.key ? 600 : 400,
          fontFamily: 'system-ui,-apple-system,sans-serif',
          transition: 'all 0.15s',
          background: tciSession === s.key ? 'rgba(255,255,255,0.1)' : 'transparent',
          color: tciSession === s.key ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.3)',
          border: tciSession === s.key ? '1px solid rgba(255,255,255,0.2)' : '1px solid transparent',
        }}>{s.label}</button>
      ))}
    </div>
  );
}

// TCI 统计行
function TciStatRow({ session }) {
  const s = TCI_SESSIONS.find(x => x.key === session);
  if (!s) return null;
  const val = parseFloat(s.mean);
  const label = val >= 0.7 ? '中' : val >= 0.5 ? '弱' : '较弱';
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.05)',
      marginBottom: 10,
    }}>
      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>东西城均值</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,0.75)', fontVariantNumeric: 'tabular-nums' }}>
          {s.mean}
        </span>
        <span style={{
          fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
          background: 'rgba(255,255,255,0.07)', color: 'rgba(255,255,255,0.35)',
          border: '1px solid rgba(255,255,255,0.12)',
        }}>{label}</span>
      </div>
    </div>
  );
}

// ── 指标配置 ──────────────────────────────────
const LAYERS = [
  {
    key: 'demand', label: '需求密度',
    hint: '以POI加权密度表征居民出行需求，并引入人口数据校准',
  },
  {
    key: 'isochrone', label: '机会可达性',
    hint: '45分钟公交等时圈内可达POI的加权数量，反映公交能到达多少城市资源',
  },
  {
    key: 'coverage', label: '网络覆盖度',
    hint: '步行便捷度与线路多样性的加权综合，衡量公交站点对居民的覆盖质量',
  },
  {
    key: 'tci', label: '公交竞争力',
    hint: '公交与小汽车出行时间之比（含换乘惩罚）\nTCI<1：开车更快\nTCI>1：公交更快',
  },
];

const DEFAULT_PARAMS = {
  demand: {
    kde_weight: 0.7, smooth_r: 800, smooth_sigma: 400,
    poi_weights: {
      '医疗保健': 3.0, '科教文化': 2.5, '购物消费': 2.0,
      '商务住宅': 2.0, '公司企业': 2.0, '生活服务': 1.5,
      '休闲娱乐': 1.5, '运动健身': 1.5, '餐饮美食': 1.0,
      '交通设施': 0.5, '汽车相关': 0.3,
    },
  },
  isochrone: { sigma: 15, max_time: 45 },
  coverage: { walk_full: 300, walk_zero: 800, walk_weight: 0.6, diversity_r: 500 },
  tci: { alpha: 8, bus_max: 70, car_max: 30 },
};

// ── 主组件 ────────────────────────────────────
const AnalysisPanel = ({ vis, onToggleVis, tciSession, onSessionChange }) => {
  const [openKey, setOpenKey] = useState(null);
  const [params, setParams] = useState(DEFAULT_PARAMS);

  const setDemand = (k, v) => setParams(p => ({ ...p, demand: { ...p.demand, [k]: v } }));
  const setIso = (k, v) => setParams(p => ({ ...p, isochrone: { ...p.isochrone, [k]: v } }));
  const setCov = (k, v) => setParams(p => ({ ...p, coverage: { ...p.coverage, [k]: v } }));
  const setTci = (k, v) => setParams(p => ({ ...p, tci: { ...p.tci, [k]: v } }));
  const setPoiWeight = (cat, val) =>
    setParams(p => ({ ...p, demand: { ...p.demand, poi_weights: { ...p.demand.poi_weights, [cat]: val } } }));

  return (
    <div style={{ fontFamily: 'system-ui,-apple-system,sans-serif', padding: '8px 0' }}>
      {LAYERS.map(layer => {
        const active = vis?.[layer.key] ?? false;
        const isOpen = openKey === layer.key;
        return (
          <div key={layer.key}>
            {/* 指标行 */}
            <div onClick={() => setOpenKey(isOpen ? null : layer.key)} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '9px 14px',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              cursor: 'pointer', userSelect: 'none',
              background: isOpen ? 'rgba(255,255,255,0.03)' : 'transparent',
              transition: 'background 0.15s',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{
                  fontSize: 12,
                  fontWeight: active ? 600 : 400,
                  color: active ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.38)',
                  transition: 'all 0.15s',
                }}>{layer.label}</span>
                <HintIcon text={layer.hint} />
              </div>
              <Toggle active={active} onClick={() => onToggleVis(layer.key)} />
            </div>

            {/* 参数面板 */}
            {isOpen && (
              <div style={{
                padding: '10px 14px 6px',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                background: 'rgba(255,255,255,0.015)',
              }}>

                {/* 需求密度 */}
                {layer.key === 'demand' && (<>
                  <SectionLabel>空间平滑</SectionLabel>
                  <SliderRow label="平滑半径 R" value={params.demand.smooth_r} min={200} max={2000} step={100} unit="m"
                    hint={"邻域平滑的搜索半径\n越大则空间扩散越广"} onChange={v => setDemand('smooth_r', v)} />
                  <SliderRow label="衰减系数 σ" value={params.demand.smooth_sigma} min={100} max={1000} step={50} unit="m"
                    hint={"高斯衰减带宽\n越小则中心权重越集中"} onChange={v => setDemand('smooth_sigma', v)} />
                  <SectionLabel>人口校准</SectionLabel>
                  <DualSlider labelA="POI密度" labelB="人口" valueA={params.demand.kde_weight}
                    hint={"两者加权合成最终需求密度"} onChange={v => setDemand('kde_weight', v)} />
                  <SectionLabel>POI 权重</SectionLabel>
                  <PoiWeightTable weights={params.demand.poi_weights} onChange={setPoiWeight} />
                  <RecalcButton />
                </>)}

                {/* 机会可达性 */}
                {layer.key === 'isochrone' && (<>
                  <SectionLabel>时间衰减</SectionLabel>
                  <SliderRow label="衰减系数 σ" value={params.isochrone.sigma} min={5} max={30} step={1} unit=" min"
                    hint={"控制时间衰减速率\nσ=15时，30min处权重≈0.14"} onChange={v => setIso('sigma', v)} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', marginTop: 2 }}>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)' }}>等时圈时间上限</span>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontWeight: 600 }}>45 min</span>
                  </div>
                  <RecalcButton />
                </>)}

                {/* 网络覆盖度 */}
                {layer.key === 'coverage' && (<>
                  <SectionLabel>步行便捷度</SectionLabel>
                  <SliderRow label="满分阈值" value={params.coverage.walk_full} min={100} max={500} step={50} unit="m"
                    hint={"步行到站距离低于此值得满分"} onChange={v => setCov('walk_full', v)} />
                  <SliderRow label="零分阈值" value={params.coverage.walk_zero} min={500} max={1500} step={100} unit="m"
                    hint={"步行到站距离超过此值得零分"} onChange={v => setCov('walk_zero', v)} />
                  <SectionLabel>综合权重</SectionLabel>
                  <DualSlider labelA="步行" labelB="多样性" valueA={params.coverage.walk_weight}
                    hint={"步行便捷度与线路多样性的权重分配"} onChange={v => setCov('walk_weight', v)} />
                  <SectionLabel>线路多样性</SectionLabel>
                  <SliderRow label="统计半径" value={params.coverage.diversity_r} min={200} max={1000} step={100} unit="m"
                    hint={"统计该范围内不重复线路数量"} onChange={v => setCov('diversity_r', v)} />
                  <RecalcButton />
                </>)}

                {/* 公交竞争力 */}
                {layer.key === 'tci' && (<>
                  <SectionLabel>时段</SectionLabel>
                  <TciSessionTab tciSession={tciSession} onSessionChange={onSessionChange} />
                  <TciStatRow session={tciSession} />

                  <SectionLabel>模型参数</SectionLabel>
                  <SliderRow label="换乘惩罚 α" value={params.tci.alpha} min={0} max={20} step={1} unit=" min/次"
                    hint={"每次换乘折算的额外时间惩罚\n用于修正公交出行时间"} onChange={v => setTci('alpha', v)} />
                  <SliderRow label="公交时间上限" value={params.tci.bus_max} min={30} max={90} step={5} unit=" min"
                    hint={"超出此值的目的地不纳入计算"} onChange={v => setTci('bus_max', v)} />
                  <SliderRow label="小汽车时间上限" value={params.tci.car_max} min={15} max={60} step={5} unit=" min"
                    hint={"超出此值的目的地不纳入计算"} onChange={v => setTci('car_max', v)} />

                  <div style={{
                    marginTop: 10, padding: '7px 10px', borderRadius: 6,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.07)',
                    fontSize: 10, color: 'rgba(255,255,255,0.25)', lineHeight: 1.8,
                  }}>
                    采集日期：2026-05-06&nbsp;&nbsp;范围：东西城 261 格网&nbsp;&nbsp;目的地：17 处
                  </div>
                </>)}

              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default AnalysisPanel;