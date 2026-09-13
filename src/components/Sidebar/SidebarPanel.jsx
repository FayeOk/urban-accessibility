import React from 'react';
import { Tabs } from 'antd';
import DataUpload from './DataUpload';
import AnalysisPanel from './AnalysisPanel';
import CompositePanel from './CompositePanel';

const SidebarPanel = ({ onDataUpdate, geoData, vis, onToggleVis, tciSession, onSessionChange }) => {
    const items = [
        {
            key: '1',
            label: '数据管理',
            children: (
                <DataUpload
                    onDataUpdate={onDataUpdate}
                    geoData={geoData}
                />
            ),
        },
        {
            key: '2',
            label: '分析设置',
            children: (
                <AnalysisPanel
                    vis={vis}
                    onToggleVis={onToggleVis}
                    tciSession={tciSession}
                    onSessionChange={onSessionChange}
                />
            ),
        },

    // items数组里加：
        {
            key: '3',
            label: '综合评价',
            children: (
                <CompositePanel
                    vis={vis}
                    onToggleVis={onToggleVis}
                />
            ),
        },
    ];

    return (
        <div className="sidebar-panel" style={{ height: '100%', background: 'transparent' }}>
            <Tabs
                defaultActiveKey="1"
                size="small"
                tabPosition="left"
                items={items}
                style={{ height: '100%' }}
                className="custom-sidebar-tabs"
            />
        </div>
    );
};

export default SidebarPanel;