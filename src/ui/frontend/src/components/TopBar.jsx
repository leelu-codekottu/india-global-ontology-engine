import React, { useEffect, useState } from 'react';
import { fetchHealth } from '../api';

export default function TopBar({ title, titleHi }) {
  const [online, setOnline] = useState(null);

  useEffect(() => {
    fetchHealth()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));
    const interval = setInterval(() => {
      fetchHealth()
        .then(() => setOnline(true))
        .catch(() => setOnline(false));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="top-bar">
      <div className="top-bar-left">
        <h1 className="page-title">
          {title}
          <span className="page-title-hi">{titleHi}</span>
        </h1>
      </div>
      <div className="top-bar-right">
        {online !== null && (
          <span className={`status-badge ${online ? 'online' : 'offline'}`}>
            <span className="status-dot"></span>
            {online ? 'Engine Online' : 'Engine Offline'}
          </span>
        )}
      </div>
    </div>
  );
}
