/**
 * demoData.js — Mock payload matching the real backend response shape.
 * Used for development/testing of the ResponsePanel without a live backend.
 *
 * Real data comes from POST /api/ask → graphrag.answer_question()
 * Shape: { answer, overall_confidence, causal_chain[], evidence[], subgraph{nodes,edges},
 *          key_impacts[], uncertainties[], timestamp, question }
 */

export const DEMO_PAYLOAD = {
  answer:
    "Iran-USA tensions will likely increase India's oil import costs and inflation due to potential disruption of oil supplies through the Strait of Hormuz. As Iran and the USA are in conflict, there is a risk of the Strait of Hormuz being closed, which would lead to an oil supply shock and increased oil prices. This, in turn, would affect India's import bill, inflation, and currency exchange rate. India imports approximately 85% of its crude oil needs, and the Strait of Hormuz is a critical transport route.",
  overall_confidence: 0.8,
  timestamp: new Date().toISOString(),
  question: "How will Iran–USA tensions affect India's oil imports and inflation?",
  causal_chain: [
    "Step 1: Iran-USA tensions lead to a potential disruption of the Strait of Hormuz (iran -[CONFLICT_WITH]-> usa, confidence=0.85).",
    "Step 2: The disruption of the Strait of Hormuz leads to an oil supply shock (iran -[DISRUPTS]-> strait of hormuz, confidence=0.80).",
    "Step 3: The oil supply shock leads to increased oil prices (Oil_Supply_Shock -[AFFECTS]-> Oil Price, confidence=0.60).",
    "Step 4: The increased oil prices affect India's import bill (Oil Price -[AFFECTS]-> Import Bill, confidence=0.70).",
    "Step 5: The increased import bill leads to higher inflation in India (crude oil -[AFFECTS]-> inflation, confidence=0.90).",
  ],
  evidence: [
    { subject: "iran", relationship: "CONFLICT_WITH", object: "usa", confidence: 0.85, source_url: "None" },
    { subject: "iran", relationship: "DISRUPTS", object: "strait of hormuz", confidence: 0.8, source_url: "None" },
    { subject: "strait of hormuz", relationship: "TRANSPORT_ROUTE_FOR", object: "crude oil", confidence: 0.91, source_url: "None" },
    { subject: "india", relationship: "IMPORTS", object: "crude oil", confidence: 0.89, source_url: "None" },
    { subject: "crude oil", relationship: "AFFECTS", object: "inflation", confidence: 0.9, source_url: "None" },
  ],
  subgraph: {
    nodes: [
      { name: "Iran", labels: ["Country"] },
      { name: "USA", labels: ["Country"] },
      { name: "Strait of Hormuz", labels: ["Location"] },
      { name: "Crude Oil", labels: ["Resource"] },
      { name: "India", labels: ["Country"] },
      { name: "Inflation", labels: ["Indicator"] },
      { name: "Oil Price", labels: ["Indicator"] },
      { name: "Import Bill", labels: ["Indicator"] },
      { name: "LNG", labels: ["Resource"] },
      { name: "Saudi Arabia", labels: ["Country"] },
    ],
    edges: [
      { source: "Iran", target: "USA", relationship: "CONFLICT_WITH", confidence: 0.85, status: "active", trust: "trusted" },
      { source: "Iran", target: "Strait of Hormuz", relationship: "CONTROLS_ACCESS_TO", confidence: 0.8, status: "active", trust: "trusted" },
      { source: "Strait of Hormuz", target: "Crude Oil", relationship: "TRANSPORT_ROUTE_FOR", confidence: 0.91, status: "active", trust: "trusted" },
      { source: "India", target: "Crude Oil", relationship: "IMPORTS", confidence: 0.89, status: "active", trust: "trusted" },
      { source: "Crude Oil", target: "Oil Price", relationship: "INFLUENCES", confidence: 0.75, status: "active", trust: "untrusted" },
      { source: "Oil Price", target: "Inflation", relationship: "AFFECTS", confidence: 0.9, status: "active", trust: "trusted" },
      { source: "Inflation", target: "India", relationship: "AFFECTS", confidence: 0.7, status: "active", trust: "untrusted" },
      { source: "Saudi Arabia", target: "Crude Oil", relationship: "EXPORTS", confidence: 0.85, status: "active", trust: "trusted" },
    ],
  },
  key_impacts: [
    { domain: "energy", severity: "high", description: "Potential disruption of oil supplies through the Strait of Hormuz" },
    { domain: "inflation", severity: "high", description: "Increased oil prices leading to higher inflation in India" },
    { domain: "currency", severity: "medium", description: "Depreciation of the Indian rupee due to increased import bill" },
    { domain: "industrial_production", severity: "medium", description: "Reduced industrial output due to higher input costs" },
  ],
  uncertainties: [
    "The confidence score for the relationship between Oil_Supply_Shock and Oil Price is low, indicating uncertainty in this link.",
  ],
};

/**
 * Transforms the raw backend response into the normalized shape
 * expected by our UI components (step_sequence + used_edges).
 */
export function normalizePayload(raw) {
  // Build step_sequence from causal_chain strings
  const step_sequence = (raw.causal_chain || []).map((text, i) => {
    const titleMatch = text.match(/Step \d+:\s*(.+?)(?:\s*\(|$)/);
    const detailMatch = text.match(/\((.+?)\)/);
    return {
      step: i + 1,
      title: titleMatch ? titleMatch[1].trim() : `Step ${i + 1}`,
      detail: detailMatch ? detailMatch[1].trim() : text,
      raw: text,
    };
  });

  // Build used_edges from evidence array
  const used_edges = (raw.evidence || []).map((ev, i) => ({
    id: `e${i}`,
    source: ev.subject,
    target: ev.object,
    relation: ev.relationship,
    confidence: ev.confidence ?? 0,
    snippet: `${ev.subject} → ${ev.relationship} → ${ev.object}`,
    source_url: ev.source_url !== "None" ? ev.source_url : null,
  }));

  // Normalize subgraph nodes to have ids
  const nodes = (raw.subgraph?.nodes || []).map((n, i) => ({
    id: `n${i}`,
    name: n.name,
    label: n.labels?.[0] || "Entity",
    confidence: 0.8,
  }));

  const edges = (raw.subgraph?.edges || []).map((e, i) => {
    const srcNode = nodes.find((n) => n.name.toLowerCase() === e.source?.toLowerCase());
    const tgtNode = nodes.find((n) => n.name.toLowerCase() === e.target?.toLowerCase());
    return {
      id: `e${i}`,
      source: srcNode?.id || `n_${e.source}`,
      target: tgtNode?.id || `n_${e.target}`,
      sourceName: e.source,
      targetName: e.target,
      relation: e.relationship,
      confidence: e.confidence ?? 0,
      trust: e.trust || "untrusted",
    };
  });

  return {
    answer: {
      text: raw.answer || "",
      confidence: raw.overall_confidence ?? 0,
      timestamp: raw.timestamp || new Date().toISOString(),
    },
    subgraph: { nodes, edges },
    step_sequence,
    used_edges,
    key_impacts: raw.key_impacts || [],
    uncertainties: raw.uncertainties || [],
  };
}
