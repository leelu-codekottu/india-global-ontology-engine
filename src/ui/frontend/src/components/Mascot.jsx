/**
 * Mascot.jsx — Displays the mascot PNG image.
 * Props:
 *   size: number (default 160)
 */
import React from 'react';

export default function Mascot({ size = 160 }) {
  return (
    <div
      className="mascot-wrap"
      style={{ width: size, height: size }}
      role="img"
      aria-label="Ontology Engine mascot"
    >
      <img
        src="/mascot.png"
        alt="Ontology Engine mascot"
        width={size}
        height={size}
        style={{ objectFit: 'contain', borderRadius: 12 }}
        draggable={false}
      />
    </div>
  );
}
