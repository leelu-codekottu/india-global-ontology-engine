import React, { useEffect, useState } from 'react';
import { fetchSnapshot, fetchThreats } from '../api';

export default function DashboardPage({ onNavigate }) {
  const [snapshot, setSnapshot] = useState(null);
  const [threats, setThreats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchSnapshot().catch(() => null),
      fetchThreats().catch(() => null),
    ]).then(([snap, thr]) => {
      setSnapshot(snap);
      setThreats(thr);
      setLoading(false);
    });
  }, []);

  const labelColors = {
    Country: 'var(--saffron)',
    Resource: 'var(--peacock-teal)',
    Location: 'var(--indigo-light)',
    Event: 'var(--terracotta)',
    Indicator: 'var(--turmeric)',
    Organization: 'var(--lotus-pink)',
    Company: '#7B1FA2',
    Policy: 'var(--henna)',
  };

  return (
    <>
      {/* Hero */}
      <div className="hero-section mandala-bg">
        <div className="hero-title-hi">भारत वैश्विक ज्ञान तंत्र</div>
        <h1 className="hero-title">India Global Ontology Engine</h1>
        <p className="hero-desc">
          Real-time geopolitical intelligence powered by knowledge graphs.
          Analyzing how global events ripple through India's economy, energy security, and strategic interests.
        </p>
        <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
          <button className="btn btn-primary" onClick={() => onNavigate('chat')}>
            ⊛ Ask a Question / प्रश्न पूछें
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate('graph')}>
            ◎ Explore Graph
          </button>
        </div>
      </div>

      {/* Stats */}
      {loading ? (
        <div className="grid-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card" style={{ padding: '32px' }}>
              <div className="skeleton" style={{ height: 40, width: '60%', margin: '0 auto 8px' }}></div>
              <div className="skeleton" style={{ height: 14, width: '80%', margin: '0 auto' }}></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid-4" style={{ marginBottom: '24px' }}>
          <div className="card accent-saffron stat-card">
            <div className="stat-value">{snapshot?.total_nodes ?? '—'}</div>
            <div className="stat-label">Total Nodes</div>
            <div className="stat-label-hi">कुल नोड्स</div>
          </div>
          <div className="card accent-indigo stat-card">
            <div className="stat-value">{snapshot?.total_edges ?? '—'}</div>
            <div className="stat-label">Relationships</div>
            <div className="stat-label-hi">संबंध</div>
          </div>
          <div className="card accent-teal stat-card">
            <div className="stat-value">{threats?.count ?? '—'}</div>
            <div className="stat-label">India Impact Edges</div>
            <div className="stat-label-hi">भारत प्रभाव</div>
          </div>
          <div className="card accent-terracotta stat-card">
            <div className="stat-value">
              {snapshot?.label_counts
                ? Object.keys(snapshot.label_counts).length
                : '—'}
            </div>
            <div className="stat-label">Entity Types</div>
            <div className="stat-label-hi">इकाई प्रकार</div>
          </div>
        </div>
      )}

      {/* Label Distribution + Quick Threats */}
      <div className="grid-2">
        {/* Label Distribution */}
        <div className="card accent-saffron">
          <div className="card-header">
            <div>
              <div className="card-title">◈ Entity Distribution</div>
              <div className="card-title-hi">इकाई वितरण</div>
            </div>
          </div>
          {snapshot?.label_counts ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {Object.entries(snapshot.label_counts).map(([label, count]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: labelColors[label] || 'var(--grey-mid)',
                      flexShrink: 0,
                    }}
                  ></div>
                  <span style={{ fontSize: '13px', fontWeight: 500, flex: 1 }}>{label}</span>
                  <div style={{ flex: 2, height: 6, background: 'var(--grey-light)', borderRadius: 3, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(100, (count / Math.max(...Object.values(snapshot.label_counts))) * 100)}%`,
                        height: '100%',
                        background: labelColors[label] || 'var(--grey-mid)',
                        borderRadius: 3,
                        transition: 'width 0.8s var(--ease-out)',
                      }}
                    ></div>
                  </div>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--slate)', minWidth: 30, textAlign: 'right' }}>
                    {count}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--grey-warm)', fontSize: '13px' }}>No data available</div>
          )}
        </div>

        {/* Quick Threats */}
        <div className="card accent-terracotta">
          <div className="card-header">
            <div>
              <div className="card-title">⚠ Top Threats to India</div>
              <div className="card-title-hi">भारत के लिए प्रमुख ख़तरे</div>
            </div>
            <button className="btn btn-ghost" onClick={() => onNavigate('threats')} style={{ fontSize: '12px' }}>
              View All →
            </button>
          </div>

          {threats?.threats?.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {threats.threats.slice(0, 6).map((t, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '8px 12px',
                    background: i % 2 === 0 ? 'var(--cream)' : 'transparent',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '13px',
                  }}
                >
                  <span style={{ fontWeight: 500, flex: 1, textTransform: 'capitalize' }}>
                    {t.source}
                  </span>
                  <span style={{
                    background: 'var(--indigo-pale)',
                    color: 'var(--indigo)',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '10px',
                    fontWeight: 600,
                    letterSpacing: '0.3px',
                  }}>
                    {t.relationship}
                  </span>
                  <span style={{ fontWeight: 500, flex: 1, textTransform: 'capitalize' }}>
                    {t.target}
                  </span>
                  <span
                    className={`trust-tag ${t.trust || 'untrusted'}`}
                    style={{ fontSize: '10px' }}
                  >
                    {t.trust || 'untrusted'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--grey-warm)', fontSize: '13px' }}>No threat data — run the pipeline first.</div>
          )}
        </div>
      </div>

      {/* Decorative divider */}
      <div className="divider-ornament">
        <span className="ornament-symbol">✦</span>
      </div>

      {/* Quick Actions */}
      <div style={{ textAlign: 'center', fontSize: '13px', color: 'var(--grey-warm)' }}>
        <span style={{ fontFamily: 'var(--font-devanagari)' }}>वसुधैव कुटुम्बकम्</span>
        {' — '}
        <em>The world is one family</em>
      </div>
    </>
  );
}
