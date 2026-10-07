const LEDS = [
  { key: 'led_red', label: 'LED rouge', color: '#ef4444' },
  { key: 'led_green', label: 'LED verte', color: '#2ecc71' },
]

export default function ControlPanel({ actuators, onCommand, disabled }) {
  return (
    <section className="card">
      <header className="card-header">
        <h2>Contrôle réactif</h2>
      </header>
      <div className="controls">
        <div className="alarm-buttons">
          <button type="button" className="btn btn-danger" disabled={disabled} onClick={() => onCommand({ buzzer: true })}>
            Déclencher l'alarme
          </button>
          <button type="button" className="btn" disabled={disabled} onClick={() => onCommand({ buzzer: false })}>
            Couper l'alarme
          </button>
        </div>
        <p className="buzzer-state">Buzzer : {actuators.buzzer ? 'en marche' : 'arrêté'}</p>
        <div className="leds">
          {LEDS.map(({ key, label, color }) => (
            <button
              key={key}
              type="button"
              className={`led-toggle ${actuators[key] ? 'on' : ''}`}
              style={{ '--led': color }}
              disabled={disabled}
              aria-pressed={Boolean(actuators[key])}
              onClick={() => onCommand({ [key]: !actuators[key] })}
            >
              <span className="led-dot" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
