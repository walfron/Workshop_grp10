import { useState } from 'react'

const WEBCAM_URL = import.meta.env.VITE_WEBCAM_URL

export default function WebcamPanel() {
  const [failed, setFailed] = useState(false)
  const live = Boolean(WEBCAM_URL) && !failed

  return (
    <section className="card">
      <div className="card-header">
        <h2>Webcam</h2>
      </div>
      <div className="card-body">
        <div className="webcam">
          {live ? (
            <img src={WEBCAM_URL} alt="Flux webcam analysé par l'IA" onError={() => setFailed(true)} />
          ) : (
            <p className="muted">{WEBCAM_URL ? 'Flux webcam injoignable' : 'Flux webcam non configuré'}</p>
          )}
        </div>
      </div>
    </section>
  )
}
