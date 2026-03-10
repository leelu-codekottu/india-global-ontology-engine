import React, { useEffect, useState } from 'react';

export default function IntroAnimation({ onComplete }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setPhase(1), 1800),
      setTimeout(() => setPhase(2), 4000),
      setTimeout(onComplete, 5000),
    ];
    return () => timers.forEach(clearTimeout);
  }, [onComplete]);

  const createDots = (count, radius, baseDelay, size) => {
    const colors = ['#FF9933', '#FFFFFF', '#138808'];
    return Array.from({ length: count }).map((_, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      const color = colors[i % 3];
      return (
        <div
          key={i}
          className="r-dot"
          style={{
            width: size,
            height: size,
            left: `calc(50% + ${x}px)`,
            top: `calc(50% + ${y}px)`,
            background: color,
            boxShadow: `0 0 ${size * 2}px ${color}60`,
            animationDelay: `${baseDelay + i * 0.06}s`,
          }}
        />
      );
    });
  };

  return (
    <div className={`intro-overlay ${phase >= 2 ? 'intro-exit' : ''}`}>
      {/* Floating background particles */}
      <div className="intro-particles">
        {Array.from({ length: 25 }).map((_, i) => (
          <div
            key={i}
            className="intro-particle"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 3}s`,
              animationDuration: `${3 + Math.random() * 4}s`,
            }}
          />
        ))}
      </div>

      {/* Rangoli / Muggulu pattern */}
      <div className="rangoli-field">
        {/* Outer ring — slow rotation */}
        <div className="rangoli-ring ring-outer">
          {createDots(20, 155, 0, 7)}
        </div>

        {/* Middle ring — counter rotation */}
        <div className="rangoli-ring ring-mid">
          {createDots(12, 100, 0.5, 10)}
        </div>

        {/* Inner ring — static */}
        {createDots(8, 52, 0.9, 11)}

        {/* Radial lines from center */}
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={`l-${i}`}
            className="r-line"
            style={{
              transform: `rotate(${i * 45}deg)`,
              animationDelay: `${0.3 + i * 0.08}s`,
            }}
          />
        ))}

        {/* Diamond accents between rings */}
        {Array.from({ length: 8 }).map((_, i) => {
          const angle = (2 * Math.PI * i) / 8 + Math.PI / 8;
          return (
            <div
              key={`d-${i}`}
              className="r-diamond"
              style={{
                left: `calc(50% + ${Math.cos(angle) * 128}px)`,
                top: `calc(50% + ${Math.sin(angle) * 128}px)`,
                animationDelay: `${0.7 + i * 0.06}s`,
              }}
            />
          );
        })}

        {/* Curved petal arcs */}
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={`arc-${i}`}
            className="r-arc"
            style={{
              transform: `rotate(${i * 60}deg)`,
              animationDelay: `${1.0 + i * 0.1}s`,
            }}
          />
        ))}

        {/* Center emblem */}
        <div className="rangoli-core">
          <span>◈</span>
        </div>
      </div>

      {/* Branding text */}
      <div className={`intro-brand ${phase >= 1 ? 'show' : ''}`}>
        <div className="intro-brand-hi">भारत वैश्विक ज्ञान तंत्र</div>
        <h1 className="intro-brand-en">India Global Ontology Engine</h1>
        <p className="intro-brand-tag">
          Geopolitical Intelligence · Knowledge Graphs · Real-time Analysis
        </p>
      </div>

      {/* Tricolor bar at bottom */}
      <div className={`intro-tricolor ${phase >= 1 ? 'show' : ''}`}>
        <div className="tricolor-saffron"></div>
        <div className="tricolor-white"></div>
        <div className="tricolor-green"></div>
      </div>
    </div>
  );
}
