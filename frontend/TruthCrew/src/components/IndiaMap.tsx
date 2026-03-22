import { useEffect, useState } from 'react';
import indiaSvg from '@/assets/india-outline.svg';

interface MapMarker {
  id: string;
  x: number;
  y: number;
  intensity: number;
  label: string;
  score: number;
}

interface IndiaMapProps {
  variant?: 'overview' | 'verified' | 'misleading' | 'unverified';
  dynamicStates?: Record<string, number>;
  isLoading?: boolean;
}

// State name → SVG coordinate mapping (viewBox: 0 0 612 696)
const STATE_COORDS: Record<string, { x: number; y: number; label: string }> = {
  'delhi': { x: 208, y: 165, label: 'Delhi' },
  'maharashtra': { x: 155, y: 360, label: 'Maharashtra' },
  'west bengal': { x: 390, y: 280, label: 'West Bengal' },
  'karnataka': { x: 195, y: 460, label: 'Karnataka' },
  'kerala': { x: 205, y: 545, label: 'Kerala' },
  'tamil nadu': { x: 260, y: 480, label: 'Tamil Nadu' },
  'telangana': { x: 220, y: 390, label: 'Telangana' },
  'andhra pradesh': { x: 260, y: 420, label: 'Andhra Pradesh' },
  'gujarat': { x: 115, y: 270, label: 'Gujarat' },
  'rajasthan': { x: 150, y: 200, label: 'Rajasthan' },
  'uttar pradesh': { x: 275, y: 200, label: 'Uttar Pradesh' },
  'madhya pradesh': { x: 200, y: 290, label: 'Madhya Pradesh' },
  'bihar': { x: 335, y: 215, label: 'Bihar' },
  'punjab': { x: 180, y: 125, label: 'Punjab' },
  'haryana': { x: 195, y: 150, label: 'Haryana' },
  'odisha': { x: 350, y: 330, label: 'Odisha' },
  'assam': { x: 445, y: 210, label: 'Assam' },
  'jharkhand': { x: 340, y: 265, label: 'Jharkhand' },
  'chhattisgarh': { x: 280, y: 310, label: 'Chhattisgarh' },
  'uttarakhand': { x: 235, y: 140, label: 'Uttarakhand' },
  'himachal pradesh': { x: 205, y: 110, label: 'Himachal Pradesh' },
  'goa': { x: 150, y: 430, label: 'Goa' },
  'jammu & kashmir': { x: 175, y: 70, label: 'J&K' },
  'tripura': { x: 455, y: 265, label: 'Tripura' },
  'meghalaya': { x: 435, y: 230, label: 'Meghalaya' },
  'manipur': { x: 470, y: 240, label: 'Manipur' },
  'mizoram': { x: 460, y: 270, label: 'Mizoram' },
  'nagaland': { x: 475, y: 225, label: 'Nagaland' },
  'arunachal pradesh': { x: 475, y: 185, label: 'Arunachal Pradesh' },
  'sikkim': { x: 400, y: 225, label: 'Sikkim' },
};

function getActivityLabel(score: number): string {
  if (score >= 70) return 'High';
  if (score >= 40) return 'Medium';
  return 'Low';
}

const IndiaMap = ({ variant = 'overview', dynamicStates, isLoading }: IndiaMapProps) => {
  const [animatedMarkers, setAnimatedMarkers] = useState<MapMarker[]>([]);
  const [hoveredMarker, setHoveredMarker] = useState<string | null>(null);

  // Static marker sets (for landing page demo)
  const overviewMarkers: MapMarker[] = [
    { id: 'delhi', x: 208, y: 165, intensity: 0.9, label: 'Delhi', score: 90 },
    { id: 'mumbai', x: 140, y: 350, intensity: 0.85, label: 'Mumbai', score: 85 },
    { id: 'kolkata', x: 390, y: 280, intensity: 0.7, label: 'Kolkata', score: 70 },
    { id: 'chennai', x: 260, y: 480, intensity: 0.6, label: 'Chennai', score: 60 },
    { id: 'bangalore', x: 195, y: 460, intensity: 0.75, label: 'Bangalore', score: 75 },
    { id: 'hyderabad', x: 220, y: 390, intensity: 0.65, label: 'Hyderabad', score: 65 },
    { id: 'jaipur', x: 175, y: 200, intensity: 0.5, label: 'Jaipur', score: 50 },
    { id: 'lucknow', x: 275, y: 200, intensity: 0.55, label: 'Lucknow', score: 55 },
    { id: 'ahmedabad', x: 115, y: 270, intensity: 0.45, label: 'Ahmedabad', score: 45 },
    { id: 'pune', x: 155, y: 385, intensity: 0.5, label: 'Pune', score: 50 },
  ];

  useEffect(() => {
    setAnimatedMarkers([]);
    let markers: MapMarker[] = [];

    if (dynamicStates && Object.keys(dynamicStates).length > 0) {
      // Dynamic mode: build markers from Google Trends data
      Object.entries(dynamicStates).forEach(([state, score]) => {
        const key = state.toLowerCase().trim();
        const coord = STATE_COORDS[key];
        if (coord && score > 0) {
          markers.push({
            id: key,
            x: coord.x,
            y: coord.y,
            label: coord.label,
            intensity: Math.min(score / 100, 1.0),
            score,
          });
        }
      });
      markers.sort((a, b) => a.intensity - b.intensity); // dimmer first, brighter on top
    } else {
      // Static fallback for landing page
      markers = overviewMarkers;
    }

    const timeouts: NodeJS.Timeout[] = [];
    markers.forEach((marker, index) => {
      const timeout = setTimeout(() => {
        setAnimatedMarkers(prev => [...prev, marker]);
      }, index * 80);
      timeouts.push(timeout);
    });

    return () => {
      timeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [variant, dynamicStates]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="relative w-full max-w-2xl mx-auto flex flex-col items-center justify-center min-h-[400px] bg-secondary/20 rounded-xl">
        <div className="w-14 h-14 border-[3px] border-t-primary border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin" />
        <p className="mt-4 text-muted-foreground font-medium text-sm animate-pulse">
          Analyzing regional spread...
        </p>
      </div>
    );
  }

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      {/* Container with SVG overlay */}
      <div className="relative">
        {/* SVG with markers overlay */}
        <svg
          viewBox="0 0 612 696"
          className="w-full h-auto absolute inset-0 z-10"
        >
          {/* Definitions for glow effect */}
          <defs>
            <filter id="redGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="markerGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Network lines inside map */}
          <g opacity="0.4">
            {animatedMarkers.map((marker, i) =>
              animatedMarkers.slice(i + 1).map((target) => {
                const distance = Math.sqrt(
                  Math.pow(marker.x - target.x, 2) + Math.pow(marker.y - target.y, 2)
                );
                if (distance < 180) {
                  return (
                    <line
                      key={`${marker.id}-${target.id}`}
                      x1={marker.x}
                      y1={marker.y}
                      x2={target.x}
                      y2={target.y}
                      stroke="hsl(0 65% 45% / 0.3)"
                      strokeWidth="1"
                      strokeDasharray="8 8"
                      className="animate-network"
                    />
                  );
                }
                return null;
              })
            )}
          </g>

          {/* Markers */}
          {animatedMarkers.map((marker) => (
            <g
              key={marker.id}
              className="animate-scale-in cursor-pointer"
              filter="url(#markerGlow)"
              onMouseEnter={() => setHoveredMarker(marker.id)}
              onMouseLeave={() => setHoveredMarker(null)}
            >
              {/* Outer pulse ring */}
              <circle
                cx={marker.x}
                cy={marker.y}
                r={16 + marker.intensity * 24}
                fill="none"
                stroke={`hsl(0 65% ${35 + marker.intensity * 20}% / ${marker.intensity * 0.2})`}
                strokeWidth="2"
                className="animate-pulse-ring"
                style={{ animationDelay: `${Math.random() * 2}s` }}
              />

              {/* Main circle */}
              <circle
                cx={marker.x}
                cy={marker.y}
                r={10 + marker.intensity * 16}
                fill={`hsl(0 65% ${35 + marker.intensity * 20}% / ${0.4 + marker.intensity * 0.4})`}
                stroke="hsl(0 65% 50% / 0.6)"
                strokeWidth="2"
                className="animate-pulse-slow"
                style={{ animationDelay: `${Math.random() * 2}s` }}
              />

              {/* Center dot */}
              <circle
                cx={marker.x}
                cy={marker.y}
                r={5}
                fill="hsl(0 65% 60%)"
              />

              {/* Tooltip */}
              {hoveredMarker === marker.id && (
                <g>
                  <rect
                    x={marker.x + 12}
                    y={marker.y - 40}
                    width={140}
                    height={52}
                    rx={6}
                    fill="hsl(0 0% 8% / 0.95)"
                    stroke="hsl(0 65% 45% / 0.5)"
                    strokeWidth="1"
                  />
                  <text
                    x={marker.x + 20}
                    y={marker.y - 22}
                    fill="white"
                    fontSize="12"
                    fontWeight="bold"
                  >
                    {marker.label}
                  </text>
                  <text
                    x={marker.x + 20}
                    y={marker.y - 5}
                    fill="hsl(0 65% 60%)"
                    fontSize="11"
                  >
                    Score: {marker.score} · {getActivityLabel(marker.score)}
                  </text>
                </g>
              )}
            </g>
          ))}
        </svg>

        {/* India map image with subtle red glow border */}
        <div
          className="relative"
          style={{
            filter: 'drop-shadow(0 0 5px hsl(0 65% 45% / 0.4)) drop-shadow(0 0 12px hsl(0 65% 45% / 0.15))',
          }}
        >
          <img
            src={indiaSvg}
            alt="India Map"
            className="w-full h-auto"
            style={{
              filter: 'brightness(0.15) saturate(0)',
            }}
          />
          {/* Red border overlay using CSS */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: `url(${indiaSvg})`,
              backgroundSize: 'contain',
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'center',
              WebkitMaskImage: `url(${indiaSvg})`,
              maskImage: `url(${indiaSvg})`,
              WebkitMaskSize: 'contain',
              maskSize: 'contain',
              WebkitMaskRepeat: 'no-repeat',
              maskRepeat: 'no-repeat',
              WebkitMaskPosition: 'center',
              maskPosition: 'center',
              border: 'none',
              boxShadow: 'inset 0 0 0 2px hsl(0 65% 45% / 0.8)',
            }}
          />
        </div>
      </div>

      {/* Legend — Low → Medium → High */}
      <div className="flex items-center justify-center gap-4 mt-6 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-primary/30" />
          <span>Low</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-primary/55" />
          <span>Medium</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3.5 h-3.5 rounded-full bg-primary/85" />
          <span>High</span>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-center text-xs text-muted-foreground/60 mt-3 italic">
        Visualization based on search trends and news signals, not exact user counts.
      </p>
    </div>
  );
};

export default IndiaMap;