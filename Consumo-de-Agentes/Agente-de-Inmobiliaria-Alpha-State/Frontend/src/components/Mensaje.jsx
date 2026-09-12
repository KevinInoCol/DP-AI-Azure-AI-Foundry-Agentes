export default function Mensaje({ role, text, typing, blocked, error }) {
  const propio = role === 'user'
  return (
    <div className={`msg ${propio ? 'user' : 'bot'}`}>
      {!propio && <div className="avatar">A</div>}
      <div className={`burbuja ${blocked ? 'blocked' : ''} ${error ? 'error' : ''}`}>
        {typing ? (
          <span className="typing"><i /><i /><i /></span>
        ) : (
          text.split('\n').map((linea, i) => <p key={i}>{linea}</p>)
        )}
      </div>
    </div>
  )
}
