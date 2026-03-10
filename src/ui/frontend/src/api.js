const API_BASE = '';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function fetchSnapshot() {
  const res = await fetch(`${API_BASE}/api/snapshot`);
  return res.json();
}

export async function askQuestion(question) {
  const res = await fetch(`${API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function flagClaim(subject, relationship, object, reason) {
  const res = await fetch(`${API_BASE}/api/flag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ subject, relationship, object, reason }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchGraph({ limit = 500, label, search } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set('limit', limit);
  if (label) params.set('label', label);
  if (search) params.set('search', search);
  const res = await fetch(`${API_BASE}/api/graph?${params}`);
  return res.json();
}

export async function fetchGraphLabels() {
  const res = await fetch(`${API_BASE}/api/graph/labels`);
  return res.json();
}

export async function fetchThreats() {
  const res = await fetch(`${API_BASE}/api/threats`);
  return res.json();
}

export async function triggerVerification() {
  const res = await fetch(`${API_BASE}/api/verify`, { method: 'POST' });
  return res.json();
}
