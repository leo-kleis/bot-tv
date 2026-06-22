export async function apiGet(path) {
  try {
    const r = await fetch(path);
    const data = await r.json();
    if (!r.ok) return { ok: false, error: data.error || `HTTP ${r.status}` };
    return data;
  } catch (e) { return { ok: false, error: e.message }; }
}

export async function apiPost(path, body) {
  try {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) return { ok: false, error: data.error || `HTTP ${r.status}` };
    return data;
  } catch (e) { return { ok: false, error: e.message }; }
}
