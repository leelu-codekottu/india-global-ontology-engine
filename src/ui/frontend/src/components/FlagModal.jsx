import React from 'react';

export default function FlagModal({ claim, onClose, onSubmit }) {
  const [reason, setReason] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    await onSubmit(reason);
    setLoading(false);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">
          ⚐ Flag Claim for Review
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--slate)', marginBottom: '12px' }}>
          This will mark the relationship as <strong style={{ color: 'var(--disputed)' }}>disputed</strong> and
          trigger automated re-verification.
        </p>

        <div style={{
          background: 'var(--saffron-light)',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
          fontSize: '13px',
          marginBottom: '16px',
          borderLeft: '3px solid var(--saffron)',
        }}>
          <div style={{ fontWeight: 600, color: 'var(--ink)' }}>
            {claim.source} → {claim.relationship} → {claim.target}
          </div>
          <div style={{ color: 'var(--grey-warm)', fontSize: '12px', marginTop: '4px' }}>
            Confidence: {((claim.confidence || 0) * 100).toFixed(0)}%
          </div>
        </div>

        <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--slate)', display: 'block', marginBottom: '6px' }}>
          Reason for flagging (optional)
        </label>
        <textarea
          className="textarea"
          placeholder="Explain why this claim may be inaccurate..."
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={loading}
            style={{ background: 'linear-gradient(135deg, #C62828, #E53935)' }}
          >
            {loading ? <span className="spinner" style={{ width: 14, height: 14, borderTopColor: 'white' }}></span> : '⚐'}{' '}
            Flag as Disputed
          </button>
        </div>
      </div>
    </div>
  );
}
