import React, { useMemo } from 'react';
import Map from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer } from '@deck.gl/layers';
import 'mapbox-gl/dist/mapbox-gl.css';

// 你的 Mapbox Token
const MAPBOX_TOKEN = 'pk.eyJ1IjoidDl1N2IiLCJhIjoiY21rZ3QyNW9yMDZqMTNocTBtcnQ4bHNwayJ9.TXuMEieHqq40puj2P893Rw';

const MapContainer = ({ data, showStops }) => {
    // 1. 优化图层配置：使用 useMemo 确保数据不变时不重新渲染
    const layers = useMemo(() => [
        new GeoJsonLayer({
            id: 'bus-network-layer',
            data: data,
            pickable: true,
            stroked: true,
            filled: true,
            lineCapRounded: true,
            lineJoinRounded: true,

            // 线路样式：青色，带透明度
            getLineColor: [0, 255, 255, 180],
            getLineWidth: 2,
            lineWidthMinPixels: 1.5,

            // 站点样式：受 showStops 状态控制
            pointType: 'circle',
            getFillColor: [255, 255, 255, 255],
            pointRadiusUnits: 'pixels',
            getPointRadius: showStops ? 4 : 0,

            // 只有当数据或显隐状态改变时才更新渲染
            updateTriggers: {
                getPointRadius: [showStops]
            }
        })
    ], [data, showStops]);

    // 2. 初始视图设置：聚焦中国深圳（根据你之前的经纬度）
    const INITIAL_VIEW_STATE = {
        longitude: 114.05,
        latitude: 22.54,
        zoom: 11,
        pitch: 0,
        bearing: 0
    };

    return (
        <div className="map-view" style={{ width: '100%', height: '100vh', position: 'relative', background: '#111' }}>
            <DeckGL
                initialViewState={INITIAL_VIEW_STATE}
                controller={true}
                layers={layers}
                // 【关键性能优化】针对不同设备智能调整渲染像素
                // Mac 等高分屏限制为 2 倍，普通屏幕保持原生 1 倍，兼顾流畅与清晰
                useDevicePixels={window.devicePixelRatio > 2 ? 2 : true}
            >
                <Map
                    mapboxAccessToken={MAPBOX_TOKEN}
                    // 【加载速度优化】使用 navigation-night-v1，比 dark-v10 更轻量，适合中国网络
                    mapStyle="mapbox://styles/mapbox/navigation-night-v1"
                    // 【性能优化】开启地图复用，避免 React 刷新时重新创建地图实例
                    reuseMaps
                    // 【字体优化】优先调用用户本地电脑的中文字体，减少几 MB 的网络字体下载
                    localIdeographFontFamily="'Microsoft YaHei', 'PingFang SC', sans-serif"
                    // 限制缩放范围，防止用户滑到外太空导致多余瓦片请求
                    minZoom={3}
                    maxZoom={18}
                />
            </DeckGL>
        </div>
    );
};

export default MapContainer;