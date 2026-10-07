const LEDS = [
  { key: 'led_red', label: 'LED rouge' },
  { key: 'led_green', label: 'LED verte' },
]

export default function ControlPanel({ actuators, onCommand, disabled }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>Commandes</h2>
      </div>
      <div className="card-body">
        <div className="buttons">
          <button type="button" className="alarm" disabled={disabled} onClick={() => onCommand({ buzzer: true })}>
            Déclencher l'alarme
          </button>
          <button type="button" disabled={disabled} onClick={() => onCommand({ buzzer: false })}>
            Couper l'alarme
          </button>
        </div>
        <div className="buttons">
          {LEDS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              disabled={disabled}
              aria-pressed={Boolean(actuators[key])}
              onClick={() => onCommand({ [key]: !actuators[key] })}
            >
              {label} : {actuators[key] ? 'allumée' : 'éteinte'}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
