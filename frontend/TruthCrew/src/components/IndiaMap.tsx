import { useEffect, useState } from 'react';
import indiaSvg from '@/assets/india-outline.svg';

interface MapMarker {
  id: string;
  x: number;
  y: number;
  intensity: number;
  label: string;
}

interface IndiaMapProps {
  variant: 'overview' | 'verified' | 'misleading' | 'unverified';
}

const IndiaMap = ({ variant }: IndiaMapProps) => {
  const [animatedMarkers, setAnimatedMarkers] = useState<MapMarker[]>([]);

  // Marker positions adjusted for the authentic India SVG (viewBox: 0 0 612 696)
  const overviewMarkers: MapMarker[] = [
    { id: 'delhi', x: 208, y: 165, intensity: 0.9, label: 'Delhi' },
    { id: 'mumbai', x: 140, y: 350, intensity: 0.85, label: 'Mumbai' },
    { id: 'kolkata', x: 390, y: 280, intensity: 0.7, label: 'Kolkata' },
    { id: 'chennai', x: 260, y: 480, intensity: 0.6, label: 'Chennai' },
    { id: 'bangalore', x: 195, y: 460, intensity: 0.75, label: 'Bangalore' },
    { id: 'hyderabad', x: 220, y: 390, intensity: 0.65, label: 'Hyderabad' },
    { id: 'jaipur', x: 175, y: 200, intensity: 0.5, label: 'Jaipur' },
    { id: 'lucknow', x: 275, y: 200, intensity: 0.55, label: 'Lucknow' },
    { id: 'ahmedabad', x: 115, y: 270, intensity: 0.45, label: 'Ahmedabad' },
    { id: 'pune', x: 155, y: 385, intensity: 0.5, label: 'Pune' },
  ];

  const verifiedMarkers: MapMarker[] = [
    { id: 'delhi', x: 208, y: 165, intensity: 0.4, label: 'Delhi' },
    { id: 'mumbai', x: 140, y: 350, intensity: 0.35, label: 'Mumbai' },
    { id: 'bangalore', x: 195, y: 460, intensity: 0.3, label: 'Bangalore' },
  ];

  const misleadingMarkers: MapMarker[] = [
    { id: 'delhi', x: 208, y: 165, intensity: 0.95, label: 'Delhi' },
    { id: 'mumbai', x: 140, y: 350, intensity: 0.9, label: 'Mumbai' },
    { id: 'kolkata', x: 390, y: 280, intensity: 0.85, label: 'Kolkata' },
    { id: 'chennai', x: 260, y: 480, intensity: 0.8, label: 'Chennai' },
    { id: 'bangalore', x: 195, y: 460, intensity: 0.85, label: 'Bangalore' },
    { id: 'hyderabad', x: 220, y: 390, intensity: 0.75, label: 'Hyderabad' },
    { id: 'jaipur', x: 175, y: 200, intensity: 0.7, label: 'Jaipur' },
    { id: 'lucknow', x: 275, y: 200, intensity: 0.72, label: 'Lucknow' },
    { id: 'ahmedabad', x: 115, y: 270, intensity: 0.65, label: 'Ahmedabad' },
    { id: 'pune', x: 155, y: 385, intensity: 0.68, label: 'Pune' },
    { id: 'patna', x: 335, y: 215, intensity: 0.6, label: 'Patna' },
    { id: 'bhopal', x: 200, y: 290, intensity: 0.55, label: 'Bhopal' },
  ];

  const unverifiedMarkers: MapMarker[] = [
    { id: 'delhi', x: 208, y: 165, intensity: 0.25, label: 'Delhi' },
    { id: 'chennai', x: 260, y: 480, intensity: 0.2, label: 'Chennai' },
    { id: 'lucknow', x: 275, y: 200, intensity: 0.15, label: 'Lucknow' },
  ];

  useEffect(() => {
    setAnimatedMarkers([]);
    let markers: MapMarker[];
    switch (variant) {
      case 'verified': 
        markers = verifiedMarkers;
        break;
      case 'misleading': 
        markers = misleadingMarkers;
        break;
      case 'unverified': 
        markers = unverifiedMarkers;
        break;
      default: 
        markers = overviewMarkers;
    }
    
    const timeouts: NodeJS.Timeout[] = [];
    markers.forEach((marker, index) => {
      const timeout = setTimeout(() => {
        setAnimatedMarkers(prev => [...prev, marker]);
      }, index * 100);
      timeouts.push(timeout);
    });
    
    return () => {
      timeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [variant]);

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
            <g key={marker.id} className="animate-scale-in" filter="url(#markerGlow)">
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

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-6 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-primary/40" />
          <span>Lower spread</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-primary/80" />
          <span>Higher spread</span>
        </div>
      </div>

      {/* Caption */}
      <p className="text-center text-xs text-muted-foreground/60 mt-4 italic">
        Visualization shown for awareness and demonstration purposes.
      </p>
    </div>
  );
};

export default IndiaMap;