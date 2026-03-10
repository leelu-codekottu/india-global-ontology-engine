/**
 * ResponsePanel.jsx — Three-column response view.
 * Layout: Mascot (left) | Flowchart (middle) | Answer (right)
 *         Connections dropdown (bottom full-width)
 *
 * Props:
 *   payload: raw backend response (null while loading)
 *   loading: boolean
 *   onFlag: (source, relationship, target, reason) => Promise
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { normalizePayload } from '../demoData';
import Mascot from './Mascot';
import LoadingGraphBuild from './LoadingGraphBuild';
import FlowchartSteps from './FlowchartSteps';
import AnswerPane from './AnswerPane';
import ConnectionsDropdown from './ConnectionsDropdown';

export default function ResponsePanel({ payload, loading, onFlag }) {
  const [activeStep, setActiveStep] = useState(-1);

  const data = useMemo(() => {
    if (!payload) return null;
    try {
      return normalizePayload(payload);
    } catch (e) {
      console.error('normalizePayload failed', e);
      return null;
    }
  }, [payload]);

  // Reset step highlight when new data arrives
  useEffect(() => {
    setActiveStep(-1);
  }, [data]);

  const handleStepClick = useCallback((index) => {
    setActiveStep(index);
  }, []);

  const handleFlagEdge = useCallback(async (edge, reason, severity) => {
    if (onFlag) {
      await onFlag(edge.source, edge.relation, edge.target, reason);
    }
  }, [onFlag]);

  // Loading state — show graph-building animation
  if (loading && !data) {
    return (
      <div className="response-panel rp-loading">
        <LoadingGraphBuild active={true} />
      </div>
    );
  }

  // No data — render nothing
  if (!data) return null;

  return (
    <div className="response-panel rp-visible">
      <div className="rp-columns">
        {/* Left: Mascot */}
        <div className="rp-left" role="complementary" aria-label="Mascot">
          <Mascot size={140} />
        </div>

        {/* Middle: Flowchart */}
        <div className="rp-middle" role="navigation" aria-label="Reasoning steps">
          <FlowchartSteps
            steps={data.step_sequence}
            activeStep={activeStep}
            onStepClick={handleStepClick}
            animating={true}
          />
        </div>

        {/* Right: Answer */}
        <div className="rp-right" role="main" aria-label="Analysis answer">
          <AnswerPane
            answer={data.answer}
            usedEdges={data.used_edges}
            keyImpacts={data.key_impacts}
            uncertainties={data.uncertainties}
            animating={true}
            fullPayload={payload}
          />
        </div>
      </div>

      {/* Bottom: Connections dropdown */}
      <ConnectionsDropdown
        edges={data.used_edges}
        onFlag={handleFlagEdge}
      />
    </div>
  );
}
