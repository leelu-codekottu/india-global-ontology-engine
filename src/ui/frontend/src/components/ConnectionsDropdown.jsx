/**
 * ConnectionsDropdown.jsx — Bottom strip: all used edges with flag/export/copy.
 *
 * Props:
 *   edges: Array<{ id, source, target, relation, confidence, snippet, source_url }>
 *   onFlag: (edge, reason, severity) => Promise<void>
 */
import React, { useState, useCallback } from 'react';

export default function ConnectionsDropdown({ edges = [], onFlag }) {
  const [open, setOpen] = useState(false);
  const [flagging, setFlagging] = useState(null);   // edge being flagged
  const [reason, setReason] = useState('');
  const [severity, setSeverity] = useState('medium');
  const [flaggedIds, setFlaggedIds] = useState({});  // id → { timer, flagged }
  const [toast, setToast] = useState(null);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2500); };

  const handleFlag = useCallback(async (edge) => {
    if (!onFlag) return;
    setFlagging(null);
    try {
      await onFlag(edge, reason, severity);
      setFlaggedIds((prev) => {
        const id = edge.id;
        // Allow undo for 30s
        const timer = setTimeout(() => {
          setFlaggedIds((p) => ({ ...p, [id]: { ...p[id], undoable: false } }));
        }, 30000);
        return { ...prev, [id]: { flagged: true, undoable: true, timer } };
      });
      showToast(`Flagged: ${edge.source} → ${edge.relation} → ${edge.target}. Queued for review.`);
      setReason('');
      setSeverity('medium');
    } catch {
      showToast('Flag failed');
    }
  }, [onFlag, reason, severity]);

  const handleUndo = (id) => {
    const entry = flaggedIds[id];
    if (entry?.timer) clearTimeout(entry.timer);
    setFlaggedIds((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    showToast('Flag undone');
  };

  const handleCopyEdge = (edge) => {
    navigator.clipboard.writeText(`${edge.source} → ${edge.relation} → ${edge.target}`);
    showToast('Edge copied');
  };

  if (!edges.length) return null;

  return (
    <div className="connections-dropdown">
      <button
        className="cd-toggle"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={`Graph connections used: ${edges.length}`}
      >
        <span>◎ Connections Used ({edges.length})</span>
        <span style={{ fontSize: 14 }}>{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="cd-list">
          {edges.map((edge, i) => {
            const isFlagged = flaggedIds[edge.id]?.flagged;
            const canUndo = flaggedIds[edge.id]?.undoable;
            return (
              <div key={edge.id || i} className={`cd-item ${isFlagged ? 'cd-flagged' : ''}`}>
                <div className="cd-edge-info">
                  <span className="cd-source">{edge.source}</span>
                  <span className="cd-rel">{edge.relation}</span>
                  <span className="cd-target">{edge.target}</span>
                  <span className={`confidence-badge ${edge.confidence >= 0.7 ? 'high' : edge.confidence >= 0.4 ? 'medium' : 'low'}`}
                        style={{ fontSize: 10, padding: '1px 6px', marginLeft: 4 }}>
                    {(edge.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                {edge.snippet && <div className="cd-snippet">{edge.snippet}</div>}
                <div className="cd-actions">
                  {edge.source_url && (
                    <a href={edge.source_url} target="_blank" rel="noopener noreferrer" className="cd-action-link" aria-label="View source">
                      🔗 Source
                    </a>
                  )}
                  <button className="cd-action-btn" onClick={() => handleCopyEdge(edge)} aria-label="Copy edge">
                    📋 Copy
                  </button>
                  {isFlagged ? (
                    canUndo ? (
                      <button className="cd-action-btn cd-undo" onClick={() => handleUndo(edge.id)} aria-label="Undo flag">
                        ↩ Undo
                      </button>
                    ) : (
                      <span className="cd-queued">Queued for review</span>
                    )
                  ) : (
                    <button
                      className="cd-action-btn cd-flag-btn"
                      onClick={() => setFlagging(edge)}
                      aria-label="Flag this connection"
                    >
                      ⚐ Flag
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Flag modal */}
      {flagging && (
        <div className="modal-overlay" onClick={() => setFlagging(null)}>
          <div className="modal cd-flag-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">⚐ Flag Connection</h3>
            <div className="cd-flag-edge">
              {flagging.source} → {flagging.relation} → {flagging.target}
            </div>
            <label className="cd-label">
              Reason
              <textarea
                className="textarea"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why is this connection inaccurate?"
              />
            </label>
            <label className="cd-label">
              Severity
              <div className="cd-severity-group">
                {['low', 'medium', 'high'].map((s) => (
                  <button
                    key={s}
                    className={`cd-severity-btn ${severity === s ? 'cd-sev-active' : ''}`}
                    onClick={() => setSeverity(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </label>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setFlagging(null)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={() => handleFlag(flagging)}
                style={{ background: 'linear-gradient(135deg, #C62828, #E53935)' }}
              >
                ⚐ Submit Flag
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="ap-toast cd-toast" role="status">{toast}</div>}
    </div>
  );
}
