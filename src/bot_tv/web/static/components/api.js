export async function apiGet(path, options = {}) {
  try {
    const r = await fetch(path, { signal: options.signal });
    const data = await r.json();
    if (!r.ok) return { ok: false, error: data.error || `HTTP ${r.status}` };
    return data;
  } catch (e) {
    if (e && e.name === 'AbortError') {
      return { ok: false, aborted: true, error: e.message };
    }
    return { ok: false, error: e.message };
  }
}

export async function apiPost(path, body = {}, options = {}) {
  try {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: options.signal,
    });
    const data = await r.json();
    if (!r.ok) return { ok: false, error: data.error || `HTTP ${r.status}` };
    return data;
  } catch (e) {
    if (e && e.name === 'AbortError') {
      return { ok: false, aborted: true, error: e.message };
    }
    return { ok: false, error: e.message };
  }
}
