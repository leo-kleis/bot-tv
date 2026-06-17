export async function apiGet(path) {
  try { return await (await fetch(path)).json(); } catch (e) { return { ok: false }; }
}

export async function apiPost(path, body) {
  try {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return await r.json();
  } catch (e) { return { ok: false, error: e.message }; }
}
