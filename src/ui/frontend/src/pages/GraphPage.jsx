import React, { useEffect, useState, useRef, useCallback } from 'react';
import { fetchGraph, fetchGraphLabels } from '../api';

const NODE_COLORS = {
  Country: '#FF9933',
  Resource: '#00695C',
  Location: '#3949AB',
  Event: '#C75B39',
  Indicator: '#FFB300',
  Organization: '#EC407A',
  Company: '#7B1FA2',
  Policy: '#8D4E2C',
  Person: '#0097A7',
  Technology: '#558B2F',
  EconomicIndicator: '#F9A825',
  MilitaryAsset: '#C62828',
  Agreement: '#6A1B9A',
  Infrastructure: '#4E342E',
};

const DEFAULT_LIMIT = 300;

export default function GraphPage() {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [labels, setLabels] = useState([]);
  const [filterLabel, setFilterLabel] = useState('');
  const [searchText, setSearchText] = useState('');
  const [nodeLimit, setNodeLimit] = useState(DEFAULT_LIMIT);
  const [totalNodes, setTotalNodes] = useState(0);
  const [totalEdges, setTotalEdges] = useState(0);
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const nodesRef = useRef([]);
  const edgesRef = useRef([]);
  const panRef = useRef({ x: 0, y: 0 });
  const zoomRef = useRef(1);
  const dragRef = useRef(null);
  const isDraggingRef = useRef(false);
  const lastMouseRef = useRef({ x: 0, y: 0 });
  const simTickRef = useRef(0);

  const loadGraph = useCallback((opts = {}) => {
    setLoading(true);
    const params = {
      limit: opts.limit ?? nodeLimit,
      label: (opts.label ?? filterLabel) || undefined,
      search: (opts.search ?? searchText) || undefined,
    };
    Promise.all([
      fetchGraph(params),
      labels.length ? Promise.resolve(null) : fetchGraphLabels(),
    ]).then(([data, lbls]) => {
      if (lbls) setLabels(lbls);
      setTotalNodes(data.total_nodes ?? data.nodes?.length ?? 0);
      setTotalEdges(data.total_edges ?? data.edges?.length ?? 0);
      setGraphData(data);
      initPhysics(data);
      simTickRef.current = 0;
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [nodeLimit, filterLabel, searchText, labels.length]);

  useEffect(() => { loadGraph(); }, []);  // initial load only

  const initPhysics = (data) => {
    if (!data?.nodes?.length) return;
    const cx = 400, cy = 300;
    nodesRef.current = data.nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / data.nodes.length;
      const r = 120 + Math.random() * 80;
      return {
        ...n,
        x: cx + r * Math.cos(angle),
        y: cy + r * Math.sin(angle),
        vx: 0,
        vy: 0,
        radius: n.labels?.includes('Country') ? 22 : 14,
        color: NODE_COLORS[n.labels?.[0]] || '#9E9EB0',
      };
    });
    edgesRef.current = data.edges
      .map((e) => {
        const sourceNode = nodesRef.current.find((n) => n.id === e.source);
        const targetNode = nodesRef.current.find((n) => n.id === e.target);
        if (!sourceNode || !targetNode) return null;
        return { ...e, sourceNode, targetNode };
      })
      .filter(Boolean);
  };

  const simulate = useCallback(() => {
    const nodes = nodesRef.current;
    const edges = edgesRef.current;
    if (!nodes.length) return;
    // Stop simulation after 200 ticks to save CPU
    simTickRef.current += 1;
    if (simTickRef.current > 200 && !dragRef.current) return;

    const repulsion = 3000;
    const attraction = 0.005;
    const damping = 0.85;
    const centerPull = 0.001;
    const cx = 400, cy = 300;

    // Repulsion — use grid-based approximation for large graphs
    const cellSize = 120;
    const grid = {};
    for (const n of nodes) {
      const key = `${Math.floor(n.x / cellSize)},${Math.floor(n.y / cellSize)}`;
      (grid[key] ||= []).push(n);
    }
    for (const n of nodes) {
      const gx = Math.floor(n.x / cellSize);
      const gy = Math.floor(n.y / cellSize);
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          const neighbors = grid[`${gx + dx},${gy + dy}`];
          if (!neighbors) continue;
          for (const m of neighbors) {
            if (m === n) continue;
            const ddx = m.x - n.x;
            const ddy = m.y - n.y;
            const dist = Math.sqrt(ddx * ddx + ddy * ddy) || 1;
            if (dist > cellSize * 2) continue;
            const force = repulsion / (dist * dist);
            n.vx -= (ddx / dist) * force;
            n.vy -= (ddy / dist) * force;
          }
        }
      }
    }

    // Attraction along edges
    for (const edge of edges) {
      const dx = edge.targetNode.x - edge.sourceNode.x;
      const dy = edge.targetNode.y - edge.sourceNode.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 150) * attraction;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      edge.sourceNode.vx += fx;
      edge.sourceNode.vy += fy;
      edge.targetNode.vx -= fx;
      edge.targetNode.vy -= fy;
    }

    // Center pull + damping
    for (const node of nodes) {
      if (dragRef.current === node) continue;
      node.vx += (cx - node.x) * centerPull;
      node.vy += (cy - node.y) * centerPull;
      node.vx *= damping;
      node.vy *= damping;
      node.x += node.vx;
      node.y += node.vy;
    }
  }, []);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const nodes = nodesRef.current;
    const edges = edgesRef.current;

    ctx.clearRect(0, 0, w, h);

    // Dark background with subtle pattern
    ctx.fillStyle = '#0F1124';
    ctx.fillRect(0, 0, w, h);

    // Subtle grid
    ctx.strokeStyle = 'rgba(255,255,255,0.02)';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    ctx.save();
    ctx.translate(panRef.current.x, panRef.current.y);
    ctx.scale(zoomRef.current, zoomRef.current);

    // Draw edges
    for (const edge of edges) {
      const conf = edge.confidence || 0.3;
      const alpha = 0.15 + conf * 0.5;
      const statusColor =
        edge.status === 'disputed'
          ? '#C62828'
          : edge.trust === 'trusted'
          ? '#2E7D32'
          : '#5C6BC0';

      ctx.strokeStyle = statusColor;
      ctx.globalAlpha = alpha;
      ctx.lineWidth = 1 + conf * 2;
      ctx.beginPath();
      ctx.moveTo(edge.sourceNode.x, edge.sourceNode.y);
      ctx.lineTo(edge.targetNode.x, edge.targetNode.y);
      ctx.stroke();

      // Edge label
      const mx = (edge.sourceNode.x + edge.targetNode.x) / 2;
      const my = (edge.sourceNode.y + edge.targetNode.y) / 2;
      ctx.globalAlpha = 0.5;
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '8px Inter';
      ctx.textAlign = 'center';
      ctx.fillText(edge.relationship, mx, my - 4);

      // Arrowhead
      ctx.globalAlpha = alpha;
      const angle = Math.atan2(
        edge.targetNode.y - edge.sourceNode.y,
        edge.targetNode.x - edge.sourceNode.x
      );
      const arrowLen = 8;
      const tx = edge.targetNode.x - Math.cos(angle) * edge.targetNode.radius;
      const ty = edge.targetNode.y - Math.sin(angle) * edge.targetNode.radius;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(
        tx - arrowLen * Math.cos(angle - 0.3),
        ty - arrowLen * Math.sin(angle - 0.3)
      );
      ctx.lineTo(
        tx - arrowLen * Math.cos(angle + 0.3),
        ty - arrowLen * Math.sin(angle + 0.3)
      );
      ctx.closePath();
      ctx.fillStyle = statusColor;
      ctx.fill();
    }

    ctx.globalAlpha = 1;

    // Draw nodes
    for (const node of nodes) {
      const isHovered = hoveredNode === node.id;
      const isSelected = selectedNode === node.id;
      const r = node.radius + (isHovered ? 4 : 0) + (isSelected ? 6 : 0);

      // Glow
      if (isHovered || isSelected) {
        const grd = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, r * 2.5);
        grd.addColorStop(0, node.color + '40');
        grd.addColorStop(1, 'transparent');
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(node.x, node.y, r * 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.fill();
      ctx.strokeStyle = isSelected ? '#FFFFFF' : 'rgba(255,255,255,0.3)';
      ctx.lineWidth = isSelected ? 2.5 : 1;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#FFFFFF';
      ctx.font = `${isHovered ? '600 11px' : '500 10px'} Inter`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      ctx.fillText(node.name, node.x, node.y + r + 4);
    }

    ctx.restore();

    simulate();
    animRef.current = requestAnimationFrame(draw);
  }, [hoveredNode, selectedNode, simulate]);

  useEffect(() => {
    if (!graphData || loading) return;
    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [graphData, loading, draw]);

  const getNodeAt = (mx, my) => {
    const px = (mx - panRef.current.x) / zoomRef.current;
    const py = (my - panRef.current.y) / zoomRef.current;
    for (const node of nodesRef.current) {
      const dx = px - node.x;
      const dy = py - node.y;
      if (dx * dx + dy * dy <= (node.radius + 4) * (node.radius + 4)) return node;
    }
    return null;
  };

  const handleMouseMove = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (isDraggingRef.current && dragRef.current) {
      const dx = (e.clientX - lastMouseRef.current.x) / zoomRef.current;
      const dy = (e.clientY - lastMouseRef.current.y) / zoomRef.current;
      dragRef.current.x += dx;
      dragRef.current.y += dy;
      dragRef.current.vx = 0;
      dragRef.current.vy = 0;
    } else if (isDraggingRef.current) {
      panRef.current.x += e.clientX - lastMouseRef.current.x;
      panRef.current.y += e.clientY - lastMouseRef.current.y;
    } else {
      const node = getNodeAt(mx, my);
      setHoveredNode(node?.id || null);
      canvasRef.current.style.cursor = node ? 'pointer' : 'grab';
    }
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseDown = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    isDraggingRef.current = true;
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
    const node = getNodeAt(mx, my);
    if (node) {
      dragRef.current = node;
      setSelectedNode(node.id);
    }
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
    dragRef.current = null;
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    zoomRef.current = Math.max(0.3, Math.min(3, zoomRef.current * factor));
  };

  const selectedNodeData = selectedNode
    ? nodesRef.current.find((n) => n.id === selectedNode)
    : null;

  const selectedEdges = selectedNode
    ? edgesRef.current.filter(
        (e) => e.sourceNode?.id === selectedNode || e.targetNode?.id === selectedNode
      )
    : [];

  return (
    <div style={{ position: 'relative' }}>
      <div className="card accent-indigo" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="card-header" style={{ padding: '16px 20px', margin: 0, borderBottom: '1px solid var(--grey-light)' }}>
          <div>
            <div className="card-title">◎ Knowledge Graph Visualization</div>
            <div className="card-title-hi">ज्ञान ग्राफ़ दृश्यकरण</div>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--grey-warm)' }}>
            {graphData
              ? `Showing ${graphData.nodes?.length || 0} / ${totalNodes} nodes • ${totalEdges} total edges`
              : '...'}
          </div>
        </div>

        {/* Filter toolbar */}
        <div style={{
          display: 'flex', gap: 8, padding: '10px 20px', flexWrap: 'wrap',
          alignItems: 'center', borderBottom: '1px solid var(--grey-light)',
          background: 'var(--cream)',
        }}>
          <input
            type="text"
            placeholder="Search nodes..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadGraph()}
            style={{
              padding: '6px 10px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--grey-light)', fontSize: 13, width: 180,
            }}
          />
          <select
            value={filterLabel}
            onChange={(e) => { setFilterLabel(e.target.value); }}
            style={{
              padding: '6px 10px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--grey-light)', fontSize: 13,
            }}
          >
            <option value="">All labels</option>
            {labels.map((l) => (
              <option key={l.label} value={l.label}>{l.label} ({l.count})</option>
            ))}
          </select>
          <select
            value={nodeLimit}
            onChange={(e) => setNodeLimit(Number(e.target.value))}
            style={{
              padding: '6px 10px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--grey-light)', fontSize: 13,
            }}
          >
            {[100, 200, 300, 500, 800, 1000, 2000].map((n) => (
              <option key={n} value={n}>{n} nodes</option>
            ))}
          </select>
          <button
            className="btn btn-primary"
            onClick={() => loadGraph()}
            style={{ padding: '6px 16px', fontSize: 13 }}
          >
            Apply
          </button>
        </div>

        {loading ? (
          <div style={{
            height: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0F1124',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto 12px', borderTopColor: 'var(--saffron)' }}></div>
              <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '13px' }}>Loading graph data...</div>
            </div>
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            <canvas
              ref={canvasRef}
              width={900}
              height={550}
              style={{ width: '100%', height: '550px', display: 'block' }}
              onMouseMove={handleMouseMove}
              onMouseDown={handleMouseDown}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={handleWheel}
            />

            {/* Legend */}
            <div className="graph-legend">
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink)', marginBottom: '6px' }}>
                Labels / लेबल
              </div>
              {Object.entries(NODE_COLORS).map(([label, color]) => (
                <div key={label} className="legend-item">
                  <div className="legend-dot" style={{ background: color }}></div>
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Selected Node Detail */}
      {selectedNodeData && (
        <div className="card accent-saffron" style={{ marginTop: '16px' }}>
          <div className="card-header">
            <div>
              <div className="card-title" style={{ textTransform: 'capitalize' }}>
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    background: selectedNodeData.color,
                    display: 'inline-block',
                    marginRight: 8,
                  }}
                ></span>
                {selectedNodeData.name}
              </div>
              <div className="card-subtitle">
                {selectedNodeData.labels?.join(', ')} • {selectedEdges.length} connections
              </div>
            </div>
            <button className="btn btn-ghost" onClick={() => setSelectedNode(null)} style={{ fontSize: '12px' }}>
              ✕ Close
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {selectedEdges.map((edge, i) => {
              const isSource = edge.sourceNode?.id === selectedNode;
              const other = isSource ? edge.targetNode : edge.sourceNode;
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '6px 10px',
                    background: i % 2 === 0 ? 'var(--cream)' : 'transparent',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '13px',
                  }}
                >
                  <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>
                    {isSource ? selectedNodeData.name : other?.name}
                  </span>
                  <span style={{
                    background: 'var(--indigo-pale)',
                    color: 'var(--indigo)',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '10px',
                    fontWeight: 600,
                  }}>
                    {edge.relationship}
                  </span>
                  <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>
                    {isSource ? other?.name : selectedNodeData.name}
                  </span>
                  <span className={`trust-tag ${edge.trust || 'untrusted'}`} style={{ marginLeft: 'auto', fontSize: '10px' }}>
                    {edge.trust || 'untrusted'}
                  </span>
                  {edge.source_urls?.length > 0 && (
                    <a
                      href={edge.source_urls[0]}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`Source: ${edge.source_urls[0]}`}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 24,
                        height: 24,
                        borderRadius: 'var(--radius-full)',
                        background: 'var(--saffron)',
                        color: '#fff',
                        fontSize: '12px',
                        textDecoration: 'none',
                        flexShrink: 0,
                        cursor: 'pointer',
                        transition: 'transform 0.15s ease',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.15)')}
                      onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                    >
                      🔗
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
