export default function HeatmapLegend() {
  return (
    <div className="heatmap-legend">
      <h4 className="heatmap-legend-title">Spread Intensity</h4>
      <div className="heatmap-legend-items">
        <div className="heatmap-legend-item">
          <span className="heatmap-legend-dot" style={{ backgroundColor: '#ef4444', boxShadow: '0 0 6px #ef444480' }} />
          <span>High (70–100)</span>
        </div>
        <div className="heatmap-legend-item">
          <span className="heatmap-legend-dot" style={{ backgroundColor: '#f97316', boxShadow: '0 0 6px #f9731680' }} />
          <span>Medium (40–70)</span>
        </div>
        <div className="heatmap-legend-item">
          <span className="heatmap-legend-dot" style={{ backgroundColor: '#94a3b8', boxShadow: '0 0 6px #94a3b840' }} />
          <span>Low (0–40)</span>
        </div>
      </div>
      {/* Gradient bar */}
      <div className="heatmap-legend-gradient" />
    </div>
  );
}
