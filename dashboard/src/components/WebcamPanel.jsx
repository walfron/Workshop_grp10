import { useState } from 'react'

const WEBCAM_URL = import.meta.env.VITE_WEBCAM_URL

export default function WebcamPanel() {
  const [failed, setFailed] = useState(false)
  const live = Boolean(WEBCAM_URL) && !failed

  return (
    <section className="card">
      <header className="card-header">
        <h2>Webcam (vision IA)</h2>
        {live && <span className="live-badge">LIVE</span>}
      </header>
      <div className="webcam">
        {live ? (
          <img src={WEBCAM_URL} alt="Flux webcam analysé par l'IA" onError={() => setFailed(true)} />
        ) : (
          <p className="placeholder">{WEBCAM_URL ? 'Flux webcam injoignable' : 'Flux webcam non configuré'}</p>
        )}
      </div>
    </section>
  )
}
