// Cliente mínimo del backend. Rutas relativas: en desarrollo las sirve el proxy
// de Vite (vite.config.js) y en producción el mismo host que sirva el frontend.

export async function enviarMensaje({ userId, sessionId, message }) {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, session_id: sessionId, message }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `Error ${r.status}`)
  }
  return r.json() // { session_id, reply, blocked }
}

export async function cerrarSesion({ userId, sessionId }) {
  if (!sessionId) return
  await fetch(`/api/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' })
}

export async function estadoBackend() {
  const r = await fetch('/api/health')
  return r.ok ? r.json() : null
}
