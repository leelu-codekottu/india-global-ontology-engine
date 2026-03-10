import React from 'react';

export default function Sidebar({ pages, activePage, onNavigate }) {
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">◈</div>
          <div className="logo-text">
            <span className="en">Ontology Engine</span>
            <span className="hi">भारत ज्ञान तंत्र</span>
          </div>
        </div>
      </div>

      <div className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {Object.entries(pages).map(([key, page]) => (
          <button
            key={key}
            className={`nav-item${activePage === key ? ' active' : ''}`}
            onClick={() => onNavigate(key)}
          >
            <span className="nav-icon">{page.icon}</span>
            <span>{page.label}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <div style={{ fontSize: '14px', color: 'rgba(255,255,255,0.55)', fontWeight: 500 }}>
          सत्यमेव जयते
        </div>
        <div style={{ marginTop: '4px', fontSize: '10px' }}>
          India Global Ontology v1.0
        </div>
      </div>
    </nav>
  );
}
