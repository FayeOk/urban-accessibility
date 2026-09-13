import React from 'react';

const STATUS_COLORS = {
    '供给不足': '#e84c3d',
    '供需匹配': '#4ade80',
    '供给过剩': '#60a5fa',
    '低效区域': '#888888',
};

const STATUS_DESC = {
    '供给不足': '需求高、供给低，优先改善区域',
    '供需匹配': '需求与供给均衡',
    '供给过剩': '需求低、供给高，资源配置偏冗余',
    '低效区域': '需求低、供给低，次要关注区域',
};

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

const CompositePanel = ({ vis, onToggleVis }) => {
    return (
        <div style={{ fontFamily: 'system-ui,-apple-system,sans-serif', padding: '8px 0' }}>

            {/* 综合可达性得分 */}
            <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '9px 14px',
                }}>
                    <div>
                        <div style={{ fontSize: 12, fontWeight: vis?.composite ? 600 : 400, color: vis?.composite ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.38)' }}>综合可达性得分</div>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)', marginTop: 2 }}>熵权法合成 · 西城区格网</div>
                    </div>
                    <Toggle active={vis?.composite ?? false} onClick={() => onToggleVis('composite')} />
                </div>
                {vis?.composite && (
                    <div style={{ padding: '0 14px 10px' }}>
                        <div style={{ height: 10, borderRadius: 3, background: 'linear-gradient(to right, #1e3a5f, #2563eb, #22c55e, #fbbf24, #ef4444)', marginBottom: 4 }} />
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>低</span>
                            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>高</span>
                        </div>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)', marginTop: 6, lineHeight: 1.7 }}>
                            基于需求密度、网络覆盖度、机会可达性三项指标，采用熵权法计算综合得分。范围：西城区261格网。
                        </div>
                    </div>
                )}
            </div>

            {/* 供需失衡识别 */}
            <div style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '9px 14px',
                }}>
                    <div>
                        <div style={{ fontSize: 12, fontWeight: vis?.imbalance ? 600 : 400, color: vis?.imbalance ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.38)' }}>供需失衡识别</div>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)', marginTop: 2 }}>象限分析法 · 西城区格网</div>
                    </div>
                    <Toggle active={vis?.imbalance ?? false} onClick={() => onToggleVis('imbalance')} />
                </div>
                {vis?.imbalance && (
                    <div style={{ padding: '0 14px 10px' }}>
                        {Object.entries(STATUS_COLORS).map(([k, c]) => (
                            <div key={k} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 7 }}>
                                <div style={{ width: 10, height: 10, borderRadius: 2, background: c, flexShrink: 0, marginTop: 2 }} />
                                <div>
                                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}>{k}</div>
                                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)', lineHeight: 1.5 }}>{STATUS_DESC[k]}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ padding: '12px 14px' }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', lineHeight: 1.8 }}>
                    综合评价基于西城区范围内三项指标交叉覆盖的格网，以需求密度中位数与综合供给中位数为分割阈值进行象限划分。
                </div>
            </div>

        </div>
    );
};

export default CompositePanel;