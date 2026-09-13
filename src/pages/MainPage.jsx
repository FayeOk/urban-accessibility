import React, { useState } from 'react';
import MapContainer from '../components/Map/MapContainer';
import SidebarPanel from '../components/Sidebar/SidebarPanel';
import '../styles/MainPage.css';

const MainPage = () => {
    const [geoData, setGeoData] = useState({ type: 'FeatureCollection', features: [] });
    const [vis, setVis] = useState({
        demand: true,
        isochrone: false,
        coverage: false,
        tci: false,
        lines: false,
        stops: false,
        composite: false,
        imbalance: false,
    });
    const [tciSession, setTciSession] = useState('morning');

    const toggleVis = key => setVis(v => ({ ...v, [key]: !v[key] }));

    return (
        <div className="dashboard-container">
            <div className="map-view">
                <MapContainer
                    data={geoData}
                    vis={vis}
                    onToggleVis={toggleVis}
                    tciSession={tciSession}
                    onSessionChange={setTciSession}
                />
            </div>
            <div className="floating-sidebar">
                <SidebarPanel
                    onDataUpdate={setGeoData}
                    geoData={geoData}
                    vis={vis}
                    onToggleVis={toggleVis}
                    tciSession={tciSession}
                    onSessionChange={setTciSession}
                />
            </div>
        </div>
    );
};

export default MainPage;