import React from 'react';
import { Tabs } from 'antd';
import DataUpload from './DataUpload';

const SidebarPanel = ({ onDataUpdate, geoData, showStops, onShowStopsChange }) => {
    const items = [
        {
            key: '1',
            label: '数据管理',
            children: (
                <DataUpload
                    onDataUpdate={onDataUpdate}
                    geoData={geoData}
                    showStops={showStops}
                    onShowStopsChange={onShowStopsChange}
                />
            ),
        },
        {
            key: '2',
            label: '分析设置',
            children: <div style={{ padding: '24px', color: '#9ba3af' }}>分析功能开发中...</div>,
        },
    ];

    return (
        /* 使用 sidebar-panel 类名来匹配你刚写的 CSS */
        <div className="sidebar-panel" style={{ height: '100%', background: 'transparent' }}>
            <Tabs
                defaultActiveKey="1"
                size="small"
                tabPosition="left"
                items={items}
                // 移除自带的内外边距，让布局更紧凑
                style={{ height: '100%' }}
                className="custom-sidebar-tabs"
            />
        </div>
    );
};

export default SidebarPanel;