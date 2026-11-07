import { useEffect, useRef, useState } from 'react'
import { enviarMensaje, cerrarSesion, estadoBackend } from './api.js'
import Mensaje from './components/Mensaje.jsx'

const CLAVE_ID = 'girardota_ciudadano_id'
const CLAVE_NOMBRE = 'girardota_ciudadano_nombre'

// El ámbito de memoria del agente es un IDENTIFICADOR OPACO de esta sesión del
// navegador, nunca la cédula ni el teléfono. Así el agente puede recordar al
// ciudadano entre visitas sin que la app llegue a manejar un dato personal.
function nuevoIdCiudadano() {
  const aleatorio = crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2)
  return `ciudadano-${aleatorio.replace(/-/g, '').slice(0, 12)}`
}

const SUGERENCIAS = [
  '¿Qué necesito para un certificado de residencia?',
  '¿Hasta cuándo puedo pagar el predial con descuento?',
  'Quiero poner una queja por el alumbrado de mi vereda',
  '¿Cómo hago la encuesta del SISBÉN?',
]

function saludo(nombre) {
  return {
    role: 'assistant',
    text: nombre
      ? `Buen día, ${nombre}. Soy Girardo, el asistente virtual de la Alcaldía Municipal de Girardota. ¿Sobre qué trámite o servicio necesita información?`
      : 'Buen día. Soy Girardo, el asistente virtual de la Alcaldía Municipal de Girardota. ¿Sobre qué trámite o servicio necesita información?',
  }
}

export default function App() {
  const [nombre, setNombre] = useState(() => localStorage.getItem(CLAVE_NOMBRE) || '')
  const [identificado, setIdentificado] = useState(() => Boolean(localStorage.getItem(CLAVE_ID)))
  const [userId, setUserId] = useState(() => localStorage.getItem(CLAVE_ID) || '')
  const [sessionId, setSessionId] = useState(null)
  const [mensajes, setMensajes] = useState(() => [saludo(localStorage.getItem(CLAVE_NOMBRE) || '')])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [info, setInfo] = useState(null)
  const finRef = useRef(null)

  useEffect(() => { estadoBackend().then(setInfo).catch(() => setInfo(null)) }, [])
  useEffect(() => { finRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [mensajes, enviando])

  function entrar(e) {
    e.preventDefault()
    const limpio = nombre.trim()
    const id = localStorage.getItem(CLAVE_ID) || nuevoIdCiudadano()
    localStorage.setItem(CLAVE_ID, id)
    if (limpio) localStorage.setItem(CLAVE_NOMBRE, limpio)
    setUserId(id)
    setMensajes([saludo(limpio)])
    setIdentificado(true)
  }

  async function enviarTexto(mensaje) {
    const msg = mensaje.trim()
    if (!msg || enviando) return
    setTexto('')
    setMensajes((m) => [...m, { role: 'user', text: msg }])
    setEnviando(true)
    try {
      const r = await enviarMensaje({ userId, sessionId, message: msg })
      setSessionId(r.session_id)
      setMensajes((m) => [...m, { role: 'assistant', text: r.reply, blocked: r.blocked }])
    } catch (err) {
      setMensajes((m) => [...m, { role: 'assistant', text: `No pude contactar al asistente: ${err.message}`, error: true }])
    } finally {
      setEnviando(false)
    }
  }

  async function nuevaConversacion() {
    await cerrarSesion({ userId, sessionId }).catch(() => {})
    setSessionId(null)
    setMensajes([saludo(nombre.trim())])
  }

  async function olvidarme() {
    await cerrarSesion({ userId, sessionId }).catch(() => {})
    localStorage.removeItem(CLAVE_ID)
    localStorage.removeItem(CLAVE_NOMBRE)
    setSessionId(null)
    setUserId('')
    setNombre('')
    setMensajes([saludo('')])
    setIdentificado(false)
  }

  if (!identificado) {
    return (
      <main className="shell">
        <section className="card ident">
          <p className="brand">Alcaldía Municipal de Girardota · Antioquia</p>
          <h1>Asistente virtual de trámites y servicios</h1>
          <p className="muted">
            Le orienta sobre trámites, requisitos, plazos, horarios y dependencias del municipio.
            Si quiere, escriba su nombre de pila para un trato más cercano; puede continuar sin él.
          </p>
          <form onSubmit={entrar} className="fila">
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Nombre de pila (opcional)"
              maxLength={40}
              autoFocus
            />
            <button type="submit">Entrar</button>
          </form>
          <p className="aviso">
            <strong>No le pediremos su cédula, teléfono, dirección ni datos bancarios</strong>, y no debe
            escribirlos en el chat. El asistente informa sobre trámites; las gestiones que necesiten sus
            datos se hacen en la ventanilla de atención al ciudadano.
          </p>
          <p className="demo">Demostración del taller <em>Agentes con Azure AI Foundry</em>. No es un canal oficial de atención.</p>
        </section>
      </main>
    )
  }

  return (
    <main className="shell">
      <section className="card chat">
        <header className="top">
          <div className="titulo">
            <p className="brand">Alcaldía Municipal de Girardota</p>
            <h1>Girardo · asistente virtual</h1>
          </div>
          <div className="acciones">
            {nombre.trim() && <span className="pill">{nombre.trim()}</span>}
            <button className="ghost" onClick={nuevaConversacion} disabled={enviando}>Nueva conversación</button>
            <button className="ghost" onClick={olvidarme} disabled={enviando}>Olvidar mis datos</button>
          </div>
        </header>

        <div className="lista">
          {mensajes.map((m, i) => <Mensaje key={i} {...m} />)}
          {enviando && <Mensaje role="assistant" typing />}
          <div ref={finRef} />
        </div>

        {mensajes.length === 1 && (
          <div className="sugerencias">
            {SUGERENCIAS.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => enviarTexto(s)} disabled={enviando}>{s}</button>
            ))}
          </div>
        )}

        <form onSubmit={(e) => { e.preventDefault(); enviarTexto(texto) }} className="entrada">
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Escriba su consulta… (no incluya cédula, teléfono ni datos bancarios)"
            disabled={enviando}
            autoFocus
          />
          <button type="submit" disabled={enviando || !texto.trim()}>Enviar</button>
        </form>

        <footer className="pie">
          <span>
            {info
              ? `Agente ${info.agent_name} v${info.agent_version} · sesión ${sessionId ? sessionId.slice(0, 8) : 'nueva'}`
              : 'Backend no disponible: arranque uvicorn en :8000'}
          </span>
          <span className="demo">Demostración del taller · no es un canal oficial</span>
        </footer>
      </section>
    </main>
  )
}
