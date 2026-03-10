/**
 * AnswerPane.jsx — Right column: human-readable answer, evidence, actions.
 *
 * Props:
 *   answer: { text, confidence, timestamp }
 *   usedEdges: Array<{ id, source, target, relation, confidence, snippet, source_url }>
 *   keyImpacts: Array<{ domain, severity, description }>
 *   uncertainties: string[]
 *   animating: boolean
 *   fullPayload: object — for JSON export
 */
import React, { useState, useEffect, useRef } from 'react';
import anime from 'animejs';

const REDUCED = typeof window !== 'undefined'
  && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export default function AnswerPane({
  answer,
  usedEdges = [],
  keyImpacts = [],
  uncertainties = [],
  animating = false,
  fullPayload = null,
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [impactsOpen, setImpactsOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const paneRef = useRef(null);

  // Animate answer text fade-in
  useEffect(() => {
    if (!animating || REDUCED || !paneRef.current) return;
    anime({
      targets: paneRef.current.querySelector('.ap-text'),
      opacity: [0, 1],
      translateY: [16, 0],
      duration: 800,
      easing: 'easeOutQuad',
    });
  }, [animating]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(answer?.text || '');
      showToast('Answer copied to clipboard');
    } catch {
      showToast('Copy failed');
    }
  };

  const handleExportJSON = () => {
    const blob = new Blob([JSON.stringify(fullPayload || answer, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ontology_answer_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('JSON exported');
  };

  const handleExportCSV = () => {
    if (!usedEdges.length) return;
    const header = 'source,relation,target,confidence\n';
    const rows = usedEdges.map((e) => `"${e.source}","${e.relation}","${e.target}",${e.confidence}`).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ontology_edges_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('CSV exported');
  };

  const handleScreenshot = async () => {
    try {
      const html2canvas = (await import('html2canvas')).default;
      const target = document.querySelector('.response-panel') || paneRef.current;
      const canvas = await html2canvas(target, { backgroundColor: '#FFFDF6' });
      const link = document.createElement('a');
      link.download = `ontology_view_${Date.now()}.png`;
      link.href = canvas.toDataURL();
      link.click();
      showToast('Screenshot saved');
    } catch {
      showToast('Screenshot failed');
    }
  };

  const getConfClass = (c) => c >= 0.7 ? 'high' : c >= 0.4 ? 'medium' : 'low';
  const severityColors = { high: 'var(--terracotta)', medium: 'var(--turmeric)', low: 'var(--peacock-teal)' };

  if (!answer) return null;

  return (
    <div className="answer-pane" ref={paneRef}>
      {/* Actions bar */}
      <div className="ap-actions">
        <button className="ap-action-btn" onClick={handleCopy} title="Copy answer" aria-label="Copy answer to clipboard">
          📋 Copy
        </button>
        <button className="ap-action-btn" onClick={handleExportJSON} title="Export JSON" aria-label="Export full payload as JSON">
          📦 JSON
        </button>
        <button className="ap-action-btn" onClick={handleExportCSV} title="Export edges CSV" aria-label="Export edges as CSV">
          📊 CSV
        </button>
        <button className="ap-action-btn" onClick={handleScreenshot} title="Screenshot" aria-label="Save screenshot as PNG">
          📸 PNG
        </button>
      </div>

      {/* Confidence + Timestamp */}
      <div className="ap-meta">
        <span className={`confidence-badge ${getConfClass(answer.confidence)}`}>
          ◈ Confidence: {(answer.confidence * 100).toFixed(0)}%
        </span>
        <span className="ap-timestamp">
          {new Date(answer.timestamp).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
        </span>
      </div>

      {/* Answer text */}
      <div className="ap-text">{answer.text}</div>

      {/* Key impacts */}
      {keyImpacts.length > 0 && (
        <div className="ap-section">
          <button
            className="ap-section-toggle"
            onClick={() => setImpactsOpen(!impactsOpen)}
            aria-expanded={impactsOpen}
          >
            <span>Key Impacts ({keyImpacts.length})</span>
            <span>{impactsOpen ? '▾' : '▸'}</span>
          </button>
          {impactsOpen && (
            <div className="ap-impacts">
              {keyImpacts.map((imp, i) => (
                <div key={i} className="ap-impact-item">
                  <span className="ap-impact-badge" style={{ background: severityColors[imp.severity] || 'var(--grey-mid)' }}>
                    {imp.severity}
                  </span>
                  <span className="ap-impact-domain">{imp.domain}</span>
                  <span className="ap-impact-desc">{imp.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Uncertainties */}
      {uncertainties.length > 0 && (
        <div className="ap-uncertainty">
          <strong>⚠ Uncertainties:</strong>
          <ul>
            {uncertainties.map((u, i) => <li key={i}>{typeof u === 'string' ? u : JSON.stringify(u)}</li>)}
          </ul>
        </div>
      )}

      {/* Evidence list */}
      {usedEdges.length > 0 && (
        <div className="ap-section">
          <button
            className="ap-section-toggle"
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            aria-expanded={evidenceOpen}
          >
            <span>Evidence ({usedEdges.length} edges)</span>
            <span>{evidenceOpen ? '▾' : '▸'}</span>
          </button>
          {evidenceOpen && (
            <div className="ap-evidence-list">
              {usedEdges.map((e, i) => (
                <div key={i} className="ap-evidence-item">
                  <span className="ap-ev-source">{e.source}</span>
                  <span className="ap-ev-rel">{e.relation}</span>
                  <span className="ap-ev-target">{e.target}</span>
                  <span className={`confidence-badge ${getConfClass(e.confidence)}`} style={{ fontSize: '10px', padding: '1px 6px' }}>
                    {(e.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="ap-toast" role="status">{toast}</div>
      )}
    </div>
  );
}
