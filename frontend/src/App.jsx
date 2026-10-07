import { useState } from 'react'
import NavBar from './components/NavBar.jsx'
import { useSentinel } from './hooks/useSentinel.js'
import DashboardPage from './pages/DashboardPage.jsx'
import ServerPage from './pages/ServerPage.jsx'

const PAGES = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'server', label: 'Serveur' },
]

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const sentinel = useSentinel()

  return (
    <div className="layout">
      <NavBar pages={PAGES} currentPage={currentPage} onNavigate={setCurrentPage} />
      <main>{currentPage === 'dashboard' ? <DashboardPage {...sentinel} /> : <ServerPage {...sentinel} />}</main>
    </div>
  )
}
