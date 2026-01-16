import React, { useState } from 'react';
import MapContainer from '../components/Map/MapContainer';
import SidebarPanel from '../components/Sidebar/SidebarPanel';
import '../styles/MainPage.css';

const MainPage = () => {
    const [geoData, setGeoData] = useState({ type: 'FeatureCollection', features: [] });
    const [showStops, setShowStops] = useState(true);

    return (
        <div className="dashboard-container">
            <header className="dashboard-header">
                <div className="logo">URBAN ACCESSIBILITY</div>
            </header>

            <div className="map-view">
                <MapContainer data={geoData} showStops={showStops} />
            </div>

            <div className="floating-sidebar">
                {/* 务必检查此处的 prop 传递 */}
                <SidebarPanel
                    onDataUpdate={setGeoData}
                    geoData={geoData}
                    showStops={showStops}
                    onShowStopsChange={setShowStops}
                />
            </div>
        </div>
    );
};

export default MainPage;