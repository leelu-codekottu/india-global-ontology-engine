import React, { useEffect, useState } from 'react';
import { fetchThreats, flagClaim } from '../api';
import FlagModal from '../components/FlagModal';

export default function ThreatsPage() {
  const [threats, setThreats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [flagTarget, setFlagTarget] = useState(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchThreats()
      .then((data) => {
        setThreats(data.threats || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleFlag = async (reason) => {
    if (!flagTarget) return;
    try {
      await flagClaim(
        flagTarget.source,
        flagTarget.relationship,
        flagTarget.target,
        reason
      );
      setThreats((prev) =>
        prev.map((t) =>
          t.source === flagTarget.source &&
          t.relationship === flagTarget.relationship &&
          t.target === flagTarget.target
            ? { ...t, status: 'disputed', trust: 'disputed' }
            : t
        )
      );
    } catch {
      // silently handle
    }
  };

  const filteredThreats =
    filter === 'all'
      ? threats
      : threats.filter((t) => t.trust === filter || t.status === filter);

  const getSeverity = (confidence) => {
    if (confidence >= 0.7) return 'high';
    if (confidence >= 0.4) return 'medium';
    return 'low';
  };

  const trustCounts = {
    all: threats.length,
    trusted: threats.filter((t) => t.trust === 'trusted').length,
    untrusted: threats.filter((t) => t.trust === 'untrusted').length,
    disputed: threats.filter((t) => t.status === 'disputed').length,
  };

  return (
    <>
      {/* Summary */}
      <div className="card accent-terracotta" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <div>
            <div className="card-title">⚠ India Threat & Impact Matrix</div>
            <div className="card-title-hi">भारत ख़तरा एवं प्रभाव मैट्रिक्स</div>
            <div className="card-subtitle">
              All relationships involving India, sorted by confidence/severity.
              Flag any claim you believe is inaccurate.
            </div>
          </div>
        </div>

        {/* Filter pills */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { key: 'all', label: 'All', labelHi: 'सभी' },
            { key: 'trusted', label: 'Trusted', labelHi: 'विश्वसनीय' },
            { key: 'untrusted', label: 'Untrusted', labelHi: 'अविश्वसनीय' },
            { key: 'disputed', label: 'Disputed', labelHi: 'विवादित' },
          ].map((f) => (
            <button
              key={f.key}
              className={`btn ${filter === f.key ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setFilter(f.key)}
              style={{ fontSize: '12px', padding: '6px 16px' }}
            >
              {f.label} ({trustCounts[f.key]})
              <span style={{
                fontFamily: 'var(--font-devanagari)',
                marginLeft: '6px',
                fontSize: '10px',
                opacity: 0.7,
              }}>
                {f.labelHi}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '48px', textAlign: 'center' }}>
            <div className="spinner" style={{ width: 28, height: 28, margin: '0 auto 12px' }}></div>
            <div style={{ fontSize: '13px', color: 'var(--grey-warm)' }}>Loading threat data...</div>
          </div>
        ) : filteredThreats.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--grey-warm)' }}>
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>◈</div>
            <div style={{ fontSize: '14px' }}>No threats found. Run the pipeline to populate data.</div>
            <div style={{ fontFamily: 'var(--font-devanagari)', fontSize: '12px', marginTop: '4px' }}>
              कोई ख़तरा नहीं मिला
            </div>
          </div>
        ) : (
          <table className="threat-table">
            <thead>
              <tr>
                <th>Source Entity</th>
                <th>Relationship</th>
                <th>Target Entity</th>
                <th>Confidence</th>
                <th>Severity</th>
                <th>Trust</th>
                <th>Status</th>
                <th style={{ width: 80 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredThreats.map((t, i) => {
                const severity = getSeverity(t.confidence || 0);
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>{t.source}</td>
                    <td>
                      <span style={{
                        background: 'var(--indigo-pale)',
                        color: 'var(--indigo)',
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: '11px',
                        fontWeight: 600,
                      }}>
                        {t.relationship}
                      </span>
                    </td>
                    <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>{t.target}</td>
                    <td>
                      <span style={{ fontWeight: 600, fontSize: '13px' }}>
                        {((t.confidence || 0) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td>
                      <div className={`severity-bar severity-${severity}`}>
                        <div
                          className="severity-bar-fill"
                          style={{ width: `${(t.confidence || 0) * 100}%` }}
                        ></div>
                      </div>
                    </td>
                    <td>
                      <span className={`trust-tag ${t.trust || 'untrusted'}`}>
                        {t.trust || 'untrusted'}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontSize: '12px',
                        color: t.status === 'disputed' ? 'var(--disputed)' : 'var(--slate)',
                        fontWeight: t.status === 'disputed' ? 600 : 400,
                      }}>
                        {t.status || 'active'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="flag-btn"
                        onClick={() =>
                          setFlagTarget({
                            source: t.source,
                            relationship: t.relationship,
                            target: t.target,
                            confidence: t.confidence,
                          })
                        }
                        disabled={t.status === 'disputed'}
                      >
                        ⚐ Flag
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Evidence footer */}
      {filteredThreats.length > 0 && (
        <div style={{
          marginTop: '16px',
          padding: '12px 16px',
          background: 'var(--saffron-light)',
          borderRadius: 'var(--radius-md)',
          borderLeft: '3px solid var(--saffron)',
          fontSize: '12px',
          color: 'var(--slate)',
        }}>
          <strong>Note / ध्यान दें:</strong> Confidence scores are computed from source count and LLM extraction agreement.
          Flag any claim that appears inaccurate — it will trigger re-verification through the feedback loop.
        </div>
      )}

      {/* Flag Modal */}
      {flagTarget && (
        <FlagModal
          claim={flagTarget}
          onClose={() => setFlagTarget(null)}
          onSubmit={handleFlag}
        />
      )}
    </>
  );
}
