import React, { useMemo } from 'react';
import Map from 'react-map-gl';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer } from '@deck.gl/layers';
import 'mapbox-gl/dist/mapbox-gl.css';

const MAPBOX_TOKEN = 'pk.eyJ1IjoidDl1N2IiLCJhIjoiY21nbWwybGpoMWVvYTJtcHJpbWR5eWZibCJ9.pwDsck55gI0bezF6yIx3ew';

const MapContainer = ({ data, showStops }) => {
    const layers = useMemo(() => [
        new GeoJsonLayer({
            id: 'bus-network-layer',
            data: data,
            pickable: true,
            stroked: true,
            filled: true,

            // 线路：始终显示
            getLineColor: [0, 255, 255, 180],
            getLineWidth: 2,
            lineWidthMinPixels: 1,

            // 站点：受 showStops 状态控制
            pointType: 'circle',
            getFillColor: [255, 255, 255, 255],
            pointRadiusUnits: 'pixels',
            // 关键：如果 showStops 为 false，半径设为 0
            getPointRadius: showStops ? 4 : 0,

            updateTriggers: {
                getPointRadius: [showStops]
            }
        })
    ], [data, showStops]);

    return (
        <div className="map-view">
            <DeckGL
                initialViewState={{ longitude: 114.05, latitude: 22.54, zoom: 11 }}
                controller={true}
                layers={layers}
            >
                <Map mapboxAccessToken={MAPBOX_TOKEN} mapStyle="mapbox://styles/mapbox/dark-v10" />
            </DeckGL>
        </div>
    );
};

export default MapContainer;