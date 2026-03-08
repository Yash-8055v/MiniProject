import { useEffect, useRef, useMemo } from 'react';

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const NetworkBackground = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const frameRef = useRef<number>(0);

  // Generate initial nodes
  const initialNodes = useMemo(() => {
    const nodes: Node[] = [];
    const nodeCount = 35;
    
    for (let i = 0; i < nodeCount; i++) {
      nodes.push({
        x: Math.random() * 100,
        y: Math.random() * 100,
        vx: (Math.random() - 0.5) * 0.015,
        vy: (Math.random() - 0.5) * 0.015,
      });
    }
    return nodes;
  }, []);

  useEffect(() => {
    nodesRef.current = [...initialNodes];
    
    const animate = () => {
      const svg = svgRef.current;
      if (!svg) return;

      // Update node positions with gentle movement
      nodesRef.current.forEach((node) => {
        node.x += node.vx;
        node.y += node.vy;

        // Bounce off edges
        if (node.x <= 0 || node.x >= 100) node.vx *= -1;
        if (node.y <= 0 || node.y >= 100) node.vy *= -1;

        // Keep within bounds
        node.x = Math.max(0, Math.min(100, node.x));
        node.y = Math.max(0, Math.min(100, node.y));
      });

      // Update SVG elements
      const nodeElements = svg.querySelectorAll('.network-node');
      const lineElements = svg.querySelectorAll('.network-line');

      nodesRef.current.forEach((node, i) => {
        const el = nodeElements[i] as SVGCircleElement;
        if (el) {
          el.setAttribute('cx', String(node.x));
          el.setAttribute('cy', String(node.y));
        }
      });

      // Update lines based on proximity
      let lineIndex = 0;
      for (let i = 0; i < nodesRef.current.length; i++) {
        for (let j = i + 1; j < nodesRef.current.length; j++) {
          const line = lineElements[lineIndex] as SVGLineElement;
          if (line) {
            const n1 = nodesRef.current[i];
            const n2 = nodesRef.current[j];
            const distance = Math.sqrt(
              Math.pow(n1.x - n2.x, 2) + Math.pow(n1.y - n2.y, 2)
            );

            if (distance < 25) {
              const opacity = Math.max(0, (25 - distance) / 25) * 0.12;
              line.setAttribute('x1', String(n1.x));
              line.setAttribute('y1', String(n1.y));
              line.setAttribute('x2', String(n2.x));
              line.setAttribute('y2', String(n2.y));
              line.setAttribute('stroke-opacity', String(opacity));
            } else {
              line.setAttribute('stroke-opacity', '0');
            }
            lineIndex++;
          }
        }
      }

      // Animate dash offset for flowing effect
      lineElements.forEach((line) => {
        const currentOffset = parseFloat(line.getAttribute('stroke-dashoffset') || '0');
        line.setAttribute('stroke-dashoffset', String(currentOffset - 0.05));
      });

      frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [initialNodes]);

  // Pre-generate all possible line elements
  const lines = useMemo(() => {
    const result = [];
    for (let i = 0; i < initialNodes.length; i++) {
      for (let j = i + 1; j < initialNodes.length; j++) {
        result.push(
          <line
            key={`line-${i}-${j}`}
            className="network-line"
            stroke="hsl(0 65% 50%)"
            strokeWidth="0.15"
            strokeOpacity="0"
            strokeDasharray="2 3"
            strokeDashoffset="0"
            strokeLinecap="round"
          />
        );
      }
    }
    return result;
  }, [initialNodes]);

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      <svg
        ref={svgRef}
        className="w-full h-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <radialGradient id="bgGradient" cx="50%" cy="30%" r="70%">
            <stop offset="0%" stopColor="hsl(0 65% 45% / 0.04)" />
            <stop offset="50%" stopColor="hsl(0 65% 40% / 0.02)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="0.3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        
        <rect width="100" height="100" fill="url(#bgGradient)" />
        
        {/* Connection lines */}
        <g>{lines}</g>
        
        {/* Nodes */}
        <g filter="url(#glow)">
          {initialNodes.map((node, i) => (
            <circle
              key={`node-${i}`}
              className="network-node"
              cx={node.x}
              cy={node.y}
              r={Math.random() > 0.7 ? 0.4 : 0.25}
              fill="hsl(0 65% 55% / 0.5)"
            >
              <animate
                attributeName="opacity"
                values="0.3;0.7;0.3"
                dur={`${3 + Math.random() * 2}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))}
        </g>
      </svg>
      
      {/* Gradient overlay for depth */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-background/30 to-background pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-r from-background/40 via-transparent to-background/40 pointer-events-none" />
    </div>
  );
};

export default NetworkBackground;
