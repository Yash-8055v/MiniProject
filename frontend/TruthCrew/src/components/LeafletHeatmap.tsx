import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import HeatmapLegend from './HeatmapLegend';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
export interface HeatmapPoint {
  name: string;
  value: number;
  coords: [number, number]; // [lat, lng]
}

interface LeafletHeatmapProps {
  data: Record<string, number> | null;
  isLoading: boolean;
  claim?: string;
  onRegionClick?: (region: HeatmapPoint) => void;
}

/* ------------------------------------------------------------------ */
/*  State → Lat/Lng mapping                                            */
/* ------------------------------------------------------------------ */
const STATE_COORDINATES: Record<string, { coords: [number, number]; label: string }> = {
  'delhi':              { coords: [28.7041, 77.1025], label: 'Delhi' },
  'maharashtra':        { coords: [19.0760, 72.8777], label: 'Maharashtra' },
  'west bengal':        { coords: [22.5726, 88.3639], label: 'West Bengal' },
  'karnataka':          { coords: [12.9716, 77.5946], label: 'Karnataka' },
  'kerala':             { coords: [10.8505, 76.2711], label: 'Kerala' },
  'tamil nadu':         { coords: [13.0827, 80.2707], label: 'Tamil Nadu' },
  'telangana':          { coords: [17.3850, 78.4867], label: 'Telangana' },
  'andhra pradesh':     { coords: [15.9129, 79.7400], label: 'Andhra Pradesh' },
  'gujarat':            { coords: [23.0225, 72.5714], label: 'Gujarat' },
  'rajasthan':          { coords: [26.9124, 75.7873], label: 'Rajasthan' },
  'uttar pradesh':      { coords: [26.8468, 80.9462], label: 'Uttar Pradesh' },
  'madhya pradesh':     { coords: [23.2599, 77.4126], label: 'Madhya Pradesh' },
  'bihar':              { coords: [25.6093, 85.1376], label: 'Bihar' },
  'punjab':             { coords: [31.1471, 75.3412], label: 'Punjab' },
  'haryana':            { coords: [29.0588, 76.0856], label: 'Haryana' },
  'odisha':             { coords: [20.2961, 85.8245], label: 'Odisha' },
  'assam':              { coords: [26.2006, 92.9376], label: 'Assam' },
  'jharkhand':          { coords: [23.6102, 85.2799], label: 'Jharkhand' },
  'chhattisgarh':       { coords: [21.2787, 81.8661], label: 'Chhattisgarh' },
  'uttarakhand':        { coords: [30.0668, 79.0193], label: 'Uttarakhand' },
  'himachal pradesh':   { coords: [31.1048, 77.1734], label: 'Himachal Pradesh' },
  'goa':                { coords: [15.2993, 74.1240], label: 'Goa' },
  'jammu & kashmir':    { coords: [34.0837, 74.7973], label: 'J&K' },
  'tripura':            { coords: [23.9408, 91.9882], label: 'Tripura' },
  'meghalaya':          { coords: [25.4670, 91.3662], label: 'Meghalaya' },
  'manipur':            { coords: [24.6637, 93.9063], label: 'Manipur' },
  'mizoram':            { coords: [23.1645, 92.9376], label: 'Mizoram' },
  'nagaland':           { coords: [26.1584, 94.5624], label: 'Nagaland' },
  'arunachal pradesh':  { coords: [28.2180, 94.7278], label: 'Arunachal Pradesh' },
  'sikkim':             { coords: [27.5330, 88.5122], label: 'Sikkim' },
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */
function getIntensityLabel(score: number): string {
  if (score >= 70) return 'High';
  if (score >= 40) return 'Medium';
  return 'Low';
}

function getIntensityColor(score: number): string {
  if (score >= 70) return '#ef4444';   // red-500
  if (score >= 40) return '#f97316';   // orange-500
  return '#94a3b8';                     // slate-400
}

function getGlowColor(score: number): string {
  if (score >= 70) return 'rgba(239, 68, 68, 0.35)';
  if (score >= 40) return 'rgba(249, 115, 22, 0.25)';
  return 'rgba(148, 163, 184, 0.15)';
}

function getPulseClass(score: number): string {
  if (score >= 70) return 'heatmap-pulse-fast';
  if (score >= 40) return 'heatmap-pulse-medium';
  return 'heatmap-pulse-slow';
}

function getRadius(score: number): number {
  return 8 + (score / 100) * 22;
}

function getGlowRadius(score: number): number {
  return 18 + (score / 100) * 35;
}

/** Haversine distance in km */
function haversine(a: [number, number], b: [number, number]): number {
  const R = 6371;
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLng = ((b[1] - a[1]) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a[0] * Math.PI) / 180) * Math.cos((b[0] * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

function convertToPoints(data: Record<string, number>): HeatmapPoint[] {
  const points: HeatmapPoint[] = [];
  Object.entries(data).forEach(([state, score]) => {
    const key = state.toLowerCase().trim();
    const entry = STATE_COORDINATES[key];
    if (entry && score > 0) {
      points.push({ name: entry.label, value: score, coords: entry.coords });
    }
  });
  return points.sort((a, b) => a.value - b.value); // dim first, bright on top
}

/* ------------------------------------------------------------------ */
/*  Pulse overlay (uses Leaflet DivIcon as CSS-animated DOM elements)  */
/* ------------------------------------------------------------------ */
function PulseMarkers({ points }: { points: HeatmapPoint[] }) {
  const map = useMap();
  const layerRef = useRef<L.LayerGroup>(L.layerGroup());

  useEffect(() => {
    const group = layerRef.current;
    group.clearLayers();
    group.addTo(map);

    points.forEach((pt) => {
      const r = getRadius(pt.value);
      const pulseClass = getPulseClass(pt.value);
      const color = getIntensityColor(pt.value);
      const ringCount = pt.value >= 70 ? 3 : pt.value >= 40 ? 2 : 1;

      let ringsHtml = '';
      for (let i = 0; i < ringCount; i++) {
        ringsHtml += `<div class="heatmap-ring ${pulseClass}" style="
          width:${r * 2 + 20}px;
          height:${r * 2 + 20}px;
          border:2px solid ${color};
          border-radius:50%;
          position:absolute;
          top:50%;left:50%;
          transform:translate(-50%,-50%);
          animation-delay:${i * 0.6}s;
          opacity:0;
        "></div>`;
      }

      const icon = L.divIcon({
        className: 'heatmap-pulse-container',
        html: `<div style="position:relative;width:${r * 2 + 30}px;height:${r * 2 + 30}px;">${ringsHtml}</div>`,
        iconSize: [r * 2 + 30, r * 2 + 30],
        iconAnchor: [(r * 2 + 30) / 2, (r * 2 + 30) / 2],
      });

      L.marker(pt.coords, { icon, interactive: false }).addTo(group);
    });

    return () => {
      group.clearLayers();
      group.remove();
    };
  }, [map, points]);

  return null;
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */
const LeafletHeatmap = ({ data, isLoading, claim, onRegionClick }: LeafletHeatmapProps) => {
  const [points, setPoints] = useState<HeatmapPoint[]>([]);
  const [visiblePoints, setVisiblePoints] = useState<HeatmapPoint[]>([]);

  useEffect(() => {
    if (data && Object.keys(data).length > 0) {
      const pts = convertToPoints(data);
      setPoints(pts);
      // Stagger the appearance of points
      setVisiblePoints([]);
      pts.forEach((_, i) => {
        setTimeout(() => {
          setVisiblePoints((prev) => [...prev, pts[i]]);
        }, i * 100);
      });
    } else {
      setPoints([]);
      setVisiblePoints([]);
    }
  }, [data]);

  /* Loading state */
  if (isLoading) {
    return (
      <div className="leaflet-loading-skeleton">
        <div className="leaflet-loading-spinner" />
        <p className="leaflet-loading-text">Analyzing regional spread...</p>
      </div>
    );
  }

  /* Empty state */
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="leaflet-empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="leaflet-empty-icon">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 16v-4"/>
          <path d="M12 8h.01"/>
        </svg>
        <p>No significant regional trend detected for this claim.</p>
      </div>
    );
  }

  /* Compute network lines between nearby hotspots */
  const networkLines: Array<{ from: [number, number]; to: [number, number]; opacity: number }> = [];
  for (let i = 0; i < visiblePoints.length; i++) {
    for (let j = i + 1; j < visiblePoints.length; j++) {
      const dist = haversine(visiblePoints[i].coords, visiblePoints[j].coords);
      if (dist < 800) {
        const strength = Math.min(visiblePoints[i].value, visiblePoints[j].value) / 100;
        networkLines.push({
          from: visiblePoints[i].coords,
          to: visiblePoints[j].coords,
          opacity: 0.1 + strength * 0.2,
        });
      }
    }
  }

  return (
    <div className="leaflet-heatmap-wrapper">
      <MapContainer
        center={[22.5937, 78.9629]}
        zoom={4.5}
        className="leaflet-heatmap-container"
        zoomControl={false}
        attributionControl={false}
        scrollWheelZoom={true}
        dragging={true}
        doubleClickZoom={true}
        maxBounds={[[5, 60], [38, 100]]}
        minZoom={4}
        maxZoom={8}
      >
        {/* Dark OSM tiles */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
        />

        {/* Network lines */}
        {networkLines.map((line, idx) => (
          <Polyline
            key={`net-${idx}`}
            positions={[line.from, line.to]}
            pathOptions={{
              color: '#ef4444',
              weight: 1,
              opacity: line.opacity,
              dashArray: '6 8',
            }}
          />
        ))}

        {/* Glow layer (large blurred circles) */}
        {visiblePoints.map((pt) => (
          <CircleMarker
            key={`glow-${pt.name}`}
            center={pt.coords}
            radius={getGlowRadius(pt.value)}
            pathOptions={{
              fillColor: getGlowColor(pt.value),
              fillOpacity: 0.4 + (pt.value / 100) * 0.3,
              color: 'transparent',
              weight: 0,
            }}
            interactive={false}
          />
        ))}

        {/* Core circles (interactive) */}
        {visiblePoints.map((pt) => (
          <CircleMarker
            key={`core-${pt.name}`}
            center={pt.coords}
            radius={getRadius(pt.value)}
            pathOptions={{
              fillColor: getIntensityColor(pt.value),
              fillOpacity: 0.5 + (pt.value / 100) * 0.4,
              color: getIntensityColor(pt.value),
              weight: 2,
              opacity: 0.7,
            }}
            eventHandlers={{
              click: () => onRegionClick?.(pt),
            }}
          >
            <Tooltip
              direction="top"
              offset={[0, -getRadius(pt.value)]}
              className="heatmap-tooltip"
            >
              <div className="heatmap-tooltip-content">
                <div className="heatmap-tooltip-header">{pt.name}</div>
                <div className="heatmap-tooltip-score">
                  Score: <strong>{pt.value}</strong>
                  <span
                    className="heatmap-tooltip-badge"
                    style={{ color: getIntensityColor(pt.value) }}
                  >
                    {getIntensityLabel(pt.value)}
                  </span>
                </div>
                <div className="heatmap-tooltip-avg">
                  {pt.value >= 70
                    ? '↑ High compared to national average'
                    : pt.value >= 40
                      ? '→ Moderate compared to national average'
                      : '↓ Low compared to national average'}
                </div>
              </div>
            </Tooltip>
          </CircleMarker>
        ))}

        {/* Center dots */}
        {visiblePoints.map((pt) => (
          <CircleMarker
            key={`dot-${pt.name}`}
            center={pt.coords}
            radius={4}
            pathOptions={{
              fillColor: '#fff',
              fillOpacity: 0.9,
              color: getIntensityColor(pt.value),
              weight: 1.5,
            }}
            interactive={false}
          />
        ))}

        {/* Animated pulse rings (CSS-based) */}
        <PulseMarkers points={visiblePoints} />
      </MapContainer>

      {/* Legend overlay */}
      <HeatmapLegend />

      {/* Disclaimer */}
      <p className="heatmap-disclaimer">
        Visualization based on search trends and news signals, not exact user counts.
      </p>
    </div>
  );
};

export default LeafletHeatmap;
