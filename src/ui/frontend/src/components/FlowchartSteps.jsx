/**
 * FlowchartSteps.jsx — Vertical causal flowchart with animated step cards.
 *
 * Props:
 *   steps: Array<{ step, title, detail, raw }>
 *   activeStep: number | null   — currently highlighted step
 *   onStepClick: (index) => void
 *   animating: boolean          — triggers sequential slide-in
 */
import React, { useEffect, useRef, useCallback } from 'react';
import anime from 'animejs';

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export default function FlowchartSteps({ steps = [], activeStep = null, onStepClick, animating = false }) {
  const containerRef = useRef(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!animating || REDUCED || !containerRef.current || hasAnimated.current) return;
    hasAnimated.current = true;

    const cards = containerRef.current.querySelectorAll('.fc-card');
    const connectors = containerRef.current.querySelectorAll('.fc-connector');

    // Reset
    anime.set(cards, { opacity: 0, translateX: -30 });
    anime.set(connectors, { scaleY: 0 });

    const tl = anime.timeline({ easing: 'easeOutExpo' });

    steps.forEach((_, i) => {
      tl.add({
        targets: cards[i],
        opacity: [0, 1],
        translateX: [-30, 0],
        duration: 500,
      }, i * 400);

      if (connectors[i]) {
        tl.add({
          targets: connectors[i],
          scaleY: [0, 1],
          duration: 300,
        }, i * 400 + 200);
      }
    });
  }, [animating, steps]);

  const getConfColor = (text) => {
    const match = text?.match(/confidence=([\d.]+)/);
    if (!match) return 'var(--grey-warm)';
    const c = parseFloat(match[1]);
    if (c >= 0.7) return 'var(--trusted, #2E7D32)';
    if (c >= 0.4) return '#F57F17';
    return 'var(--terracotta, #C75B39)';
  };

  const getConfValue = (text) => {
    const match = text?.match(/confidence=([\d.]+)/);
    return match ? `${(parseFloat(match[1]) * 100).toFixed(0)}%` : null;
  };

  if (!steps.length) return null;

  return (
    <div className="flowchart-steps" ref={containerRef} role="list" aria-label="Causal reasoning steps">
      <div className="fc-header">Reasoning Chain</div>
      {steps.map((s, i) => (
        <React.Fragment key={i}>
          <div
            className={`fc-card ${activeStep === i ? 'fc-active' : ''}`}
            onClick={() => onStepClick?.(i)}
            onKeyDown={(e) => e.key === 'Enter' && onStepClick?.(i)}
            role="listitem"
            tabIndex={0}
            aria-label={`Step ${s.step}: ${s.title}`}
          >
            <div className="fc-step-num">{s.step}</div>
            <div className="fc-body">
              <div className="fc-title">{s.title}</div>
              <div className="fc-detail">{s.detail}</div>
              {getConfValue(s.raw) && (
                <span className="fc-conf" style={{ color: getConfColor(s.raw) }}>
                  ◈ {getConfValue(s.raw)}
                </span>
              )}
            </div>
          </div>
          {i < steps.length - 1 && (
            <div className="fc-connector" aria-hidden="true">
              <svg width="2" height="24" viewBox="0 0 2 24">
                <line x1="1" y1="0" x2="1" y2="24" stroke="var(--saffron, #FF9933)" strokeWidth="2" strokeDasharray="4 3"/>
              </svg>
              <span className="fc-arrow">▼</span>
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
