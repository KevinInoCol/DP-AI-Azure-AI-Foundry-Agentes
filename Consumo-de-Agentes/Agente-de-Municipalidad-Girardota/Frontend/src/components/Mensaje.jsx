export default function Mensaje({ role, text, typing, blocked, error }) {
  const propio = role === 'user'
  return (
    <div className={`msg ${propio ? 'user' : 'bot'}`}>
      {!propio && <div className="avatar" aria-hidden="true">G</div>}
      <div className={`burbuja ${blocked ? 'blocked' : ''} ${error ? 'error' : ''}`}>
        {typing ? (
          <span className="typing" role="status" aria-label="Escribiendo"><i /><i /><i /></span>
        ) : (
          text.split('\n').map((linea, i) => <p key={i}>{linea}</p>)
        )}
      </div>
    </div>
  )
}
