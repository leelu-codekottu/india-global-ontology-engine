/**
 * ThoughtBubbleGraph.jsx — Mini subgraph that renders inside the mascot's
 * thought bubble. Animates nodes + edges; highlights edges in step order.
 *
 * Props:
 *   subgraph: { nodes[], edges[] }  — normalized (ids, names, labels)
 *   activeStepIndex: number          — which step is currently highlighted (-1 = none)
 *   visible: boolean                 — controls fade in/out
 */
import React, { useEffect, useRef, useMemo } from 'react';
import anime from 'animejs';

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const LABEL_COLORS = {
  Country: '#FF9933',
  Resource: '#00695C',
  Location: '#3949AB',
  Event: '#C75B39',
  Indicator: '#FFB300',
  Organization: '#EC407A',
  Entity: '#9E9EB0',
};

function forceLayout(nodes, edges, width, height) {
  // Simple circular layout — good enough for a small thought bubble
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.min(width, height) * 0.35;
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    return {
      ...n,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  });
}

export default function ThoughtBubbleGraph({ subgraph, activeStepIndex = -1, visible = false }) {
  const svgRef = useRef(null);
  const W = 260;
  const H = 200;

  const laidOut = useMemo(() => {
    if (!subgraph?.nodes?.length) return { nodes: [], edges: [] };
    const n = forceLayout(subgraph.nodes.slice(0, 12), subgraph.edges, W, H);
    const nodeMap = Object.fromEntries(n.map((nd) => [nd.id, nd]));
    const e = (subgraph.edges || []).slice(0, 16).map((edge) => {
      const src = nodeMap[edge.source];
      const tgt = nodeMap[edge.target];
      if (!src || !tgt) return null;
      return { ...edge, x1: src.x, y1: src.y, x2: tgt.x, y2: tgt.y };
    }).filter(Boolean);
    return { nodes: n, edges: e };
  }, [subgraph]);

  // Animate nodes in on visibility
  useEffect(() => {
    if (REDUCED || !visible || !svgRef.current) return;
    const nodes = svgRef.current.querySelectorAll('.tb-node');
    const edges = svgRef.current.querySelectorAll('.tb-edge');
    anime({
      targets: nodes,
      opacity: [0, 1],
      scale: [0, 1],
      duration: 800,
      easing: 'easeOutBack',
      delay: anime.stagger(60),
    });
    anime({
      targets: edges,
      strokeDashoffset: [100, 0],
      opacity: [0, 0.5],
      duration: 1000,
      easing: 'easeOutQuad',
      delay: anime.stagger(80, { start: 400 }),
    });
  }, [visible, laidOut]);

  if (!visible || !laidOut.nodes.length) return null;

  return (
    <div className="thought-bubble" role="img" aria-label="Knowledge subgraph visualization">
      {/* Bubble pointer */}
      <div className="thought-bubble-pointer"></div>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width={W} height={H}>
        {/* Edges */}
        {laidOut.edges.map((e, i) => {
          const isHighlighted = activeStepIndex >= 0 && i <= activeStepIndex;
          return (
            <line
              key={`te-${i}`}
              className="tb-edge"
              x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
              stroke={isHighlighted ? '#FF9933' : '#5C6BC0'}
              strokeWidth={isHighlighted ? 2.5 : 1}
              strokeDasharray="100"
              strokeDashoffset="100"
              opacity="0"
            />
          );
        })}
        {/* Nodes */}
        {laidOut.nodes.map((n, i) => (
          <g key={`tn-${i}`}>
            <circle
              className="tb-node"
              cx={n.x} cy={n.y} r={8}
              fill={LABEL_COLORS[n.label] || '#9E9EB0'}
              opacity="0"
              style={{ transformOrigin: `${n.x}px ${n.y}px` }}
            />
            <text
              x={n.x} y={n.y + 16}
              textAnchor="middle"
              fontSize="7"
              fill="var(--slate, #4A4A6A)"
              opacity="0.7"
            >
              {n.name?.length > 10 ? n.name.slice(0, 9) + '…' : n.name}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
