/**
 * LoadingGraphBuild.jsx — Pre-response "graph building" loading animation.
 *
 * Shows SVG nodes fading/scaling in, then edges drawing (stroke-dashoffset).
 * Loops until `active` prop becomes false.
 * Uses anime.js timeline for sequencing.
 * Respects prefers-reduced-motion.
 *
 * Displays rotating phase messages mimicking the real pipeline stages.
 */
import React, { useEffect, useRef, useMemo, useState } from 'react';
import anime from 'animejs';

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const NODE_COLORS = {
  Country: '#FF9933',
  Resource: '#00695C',
  Location: '#3949AB',
  Event: '#C75B39',
  Indicator: '#FFB300',
};

// Simulated graph layout for the loading animation
const SIM_NODES = [
  { x: 200, y: 80, label: 'Country', r: 12 },
  { x: 100, y: 140, label: 'Location', r: 9 },
  { x: 300, y: 140, label: 'Resource', r: 10 },
  { x: 60, y: 220, label: 'Event', r: 8 },
  { x: 180, y: 240, label: 'Indicator', r: 9 },
  { x: 340, y: 220, label: 'Country', r: 11 },
  { x: 140, y: 300, label: 'Resource', r: 8 },
  { x: 260, y: 300, label: 'Country', r: 10 },
  { x: 50, y: 80, label: 'Indicator', r: 7 },
  { x: 350, y: 80, label: 'Event', r: 7 },
  { x: 200, y: 160, label: 'Country', r: 13 },
  { x: 120, y: 60, label: 'Resource', r: 8 },
  { x: 280, y: 60, label: 'Location', r: 7 },
  { x: 240, y: 200, label: 'Indicator', r: 9 },
];

const SIM_EDGES = [
  [0, 1], [0, 2], [1, 3], [1, 4], [2, 5], [3, 6], [4, 7],
  [5, 7], [0, 10], [10, 4], [10, 2], [8, 1], [9, 5], [10, 13],
  [11, 0], [12, 2], [6, 7], [13, 7],
];

export default function LoadingGraphBuild({ active }) {
  const svgRef = useRef(null);
  const tlRef = useRef(null);
  const [phaseIndex, setPhaseIndex] = useState(0);

  const PHASES = useMemo(() => [
    { text: 'Decomposing your question into sub-queries...', icon: '◇' },
    { text: 'Searching 1,000+ nodes for relevant entities...', icon: '◈' },
    { text: 'Traversing geopolitical relationships...', icon: '⬡' },
    { text: 'Mapping causal chains across domains...', icon: '⬢' },
    { text: 'Cross-referencing economic indicators...', icon: '◆' },
    { text: 'Verifying edge confidence scores...', icon: '◇' },
    { text: 'Synthesizing analytical response...', icon: '◈' },
  ], []);

  // Rotate through phases every 3 seconds
  useEffect(() => {
    if (!active) { setPhaseIndex(0); return; }
    const timer = setInterval(() => {
      setPhaseIndex((prev) => (prev + 1) % PHASES.length);
    }, 3000);
    return () => clearInterval(timer);
  }, [active, PHASES.length]);

  useEffect(() => {
    if (!active || REDUCED || !svgRef.current) return;

    const nodes = svgRef.current.querySelectorAll('.lg-node');
    const edges = svgRef.current.querySelectorAll('.lg-edge');
    const labels = svgRef.current.querySelectorAll('.lg-label');

    // Reset
    anime.set(nodes, { opacity: 0, scale: 0 });
    anime.set(edges, { strokeDashoffset: anime.stagger([200, 400]) });
    anime.set(labels, { opacity: 0 });

    const tl = anime.timeline({
      loop: true,
      direction: 'normal',
      easing: 'easeOutExpo',
    });

    // Phase 1: Nodes appear with staggered scale-in
    tl.add({
      targets: nodes,
      opacity: [0, 1],
      scale: [0, 1],
      duration: 1200,
      delay: anime.stagger(60, { from: 'center' }),
    });

    // Phase 2: Edges draw in
    tl.add({
      targets: edges,
      strokeDashoffset: [anime.stagger([200, 400]), 0],
      opacity: [0, 0.7],
      duration: 1400,
      delay: anime.stagger(50),
    }, '-=600');

    // Phase 3: Labels fade
    tl.add({
      targets: labels,
      opacity: [0, 0.6],
      duration: 600,
      delay: anime.stagger(40),
    }, '-=800');

    // Phase 4: Pulse nodes
    tl.add({
      targets: nodes,
      scale: [1, 1.2, 1],
      duration: 800,
      delay: anime.stagger(30, { from: 'center' }),
    });

    // Phase 5: Fade everything out before loop restart
    tl.add({
      targets: [nodes, edges, labels],
      opacity: 0,
      duration: 600,
    });

    tlRef.current = tl;

    return () => {
      tl.pause();
      tl.seek(0);
    };
  }, [active]);

  // Pause when inactive
  useEffect(() => {
    if (!active && tlRef.current) {
      tlRef.current.pause();
    }
  }, [active]);

  if (!active) return null;

  /* If reduced motion, show simple spinner */
  if (REDUCED) {
    return (
      <div className="loading-graph-build" role="status" aria-label="Analyzing knowledge graph">
        <div className="spinner" style={{ width: 32, height: 32 }}></div>
        <p style={{ marginTop: 12, color: 'var(--grey-warm)', fontSize: 13 }}>
          {PHASES[phaseIndex].icon} {PHASES[phaseIndex].text}
        </p>
      </div>
    );
  }

  return (
    <div className="loading-graph-build" role="status" aria-label="Building knowledge graph visualization">
      <svg ref={svgRef} viewBox="0 0 400 360" width="400" height="360" className="lg-svg">
        {/* Edges first (behind nodes) */}
        {SIM_EDGES.map(([from, to], i) => {
          const a = SIM_NODES[from];
          const b = SIM_NODES[to];
          return (
            <line
              key={`edge-${i}`}
              className="lg-edge"
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke="var(--indigo-muted, #5C6BC0)"
              strokeWidth="1.5"
              strokeDasharray="200"
              strokeDashoffset="200"
              opacity="0"
            />
          );
        })}

        {/* Nodes */}
        {SIM_NODES.map((n, i) => (
          <g key={`node-${i}`}>
            <circle
              className="lg-node"
              cx={n.x} cy={n.y} r={n.r}
              fill={NODE_COLORS[n.label] || '#9E9EB0'}
              opacity="0"
              style={{ transformOrigin: `${n.x}px ${n.y}px` }}
            />
            <text
              className="lg-label"
              x={n.x} y={n.y + n.r + 12}
              textAnchor="middle"
              fontSize="8"
              fill="var(--grey-warm, #6B6B80)"
              opacity="0"
            >
              {n.label}
            </text>
          </g>
        ))}
      </svg>
      <p className="lg-text" key={phaseIndex}>
        <span className="lg-phase-icon">{PHASES[phaseIndex].icon}</span>{' '}
        {PHASES[phaseIndex].text}
      </p>
    </div>
  );
}
