import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, cerrarSesion, estadoBackend } from './api.js'
import Mensaje from './components/Mensaje.jsx'

const SALUDO = {
  role: 'assistant',
  text: 'Hola, soy Alpha, el asistente virtual de Alpha State. ¿Buscas alquilar, comprar o vender un inmueble?',
}

export default function App() {
  const [userId, setUserId] = useState(() => localStorage.getItem('alpha_user_id') || '')
  const [identificado, setIdentificado] = useState(() => Boolean(localStorage.getItem('alpha_user_id')))
  const [sessionId, setSessionId] = useState(null)
  const [mensajes, setMensajes] = useState([SALUDO])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [info, setInfo] = useState(null)
  const finRef = useRef(null)

  useEffect(() => { estadoBackend().then(setInfo).catch(() => setInfo(null)) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [mensajes, enviando])

  function identificar(e) {
    e.preventDefault()
    const id = userId.trim()
    if (!id) return
    localStorage.setItem('alpha_user_id', id)
    setIdentificado(true)
  }

  async function enviar(e) {
    e.preventDefault()
    const msg = texto.trim()
    if (!msg || enviando) return
    setTexto('')
    setMensajes((m) => [...m, { role: 'user', text: msg }])
    setEnviando(true)
    try {
      const r = await enviarMensaje({ userId, sessionId, message: msg })
      setSessionId(r.session_id)
      setMensajes((m) => [...m, { role: 'assistant', text: r.reply, blocked: r.blocked }])
    } catch (err) {
      setMensajes((m) => [...m, { role: 'assistant', text: `No pude contactar al agente: ${err.message}`, error: true }])
    } finally {
      setEnviando(false)
    }
  }

  async function nuevaConversacion() {
    await cerrarSesion({ userId, sessionId }).catch(() => {})
    setSessionId(null)
    setMensajes([SALUDO])
  }

  function cambiarUsuario() {
    nuevaConversacion()
    localStorage.removeItem('alpha_user_id')
    setUserId('')
    setIdentificado(false)
  }

  if (!identificado) {
    return (
      <main className="shell">
        <section className="card ident">
          <p className="brand">Alpha State</p>
          <h1>Asesor inmobiliario virtual</h1>
          <p className="muted">Escribe tu teléfono o correo. Con él el agente recuerda tu búsqueda la próxima vez que vuelvas.</p>
          <form onSubmit={identificar} className="fila">
            <input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="Ej. 19 99999 0000" autoFocus />
            <button type="submit">Empezar</button>
          </form>
        </section>
      </main>
    )
  }

  return (
    <main className="shell">
      <section className="card chat">
        <header className="top">
          <div>
            <p className="brand">Alpha State</p>
            <h1>Alpha · asesor virtual</h1>
          </div>
          <div className="acciones">
            <span className="pill" title="Identificador usado para tu memoria">{userId}</span>
            <button className="ghost" onClick={nuevaConversacion} disabled={enviando}>Nueva conversación</button>
            <button className="ghost" onClick={cambiarUsuario} disabled={enviando}>Cambiar usuario</button>
          </div>
        </header>

        <div className="lista">
          {mensajes.map((m, i) => <Mensaje key={i} {...m} />)}
          {enviando && <Mensaje role="assistant" typing />}
          <div ref={finRef} />
        </div>

        <form onSubmit={enviar} className="entrada">
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Escribe tu mensaje… (ej. busco kitnet en Barão Geraldo hasta 1500 reales)"
            disabled={enviando}
            autoFocus
          />
          <button type="submit" disabled={enviando || !texto.trim()}>Enviar</button>
        </form>

        <footer className="pie">
          {info ? `Agente ${info.agent_name} v${info.agent_version} · sesión ${sessionId ? sessionId.slice(0, 8) : 'nueva'}` : 'Backend no disponible: arranca uvicorn en :8000'}
        </footer>
      </section>
    </main>
  )
}
