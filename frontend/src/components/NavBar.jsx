export default function NavBar({ pages, currentPage, onNavigate }) {
  return (
    <nav className="navbar">
      <div className="brand">
        <h1>SENTINEL-X</h1>
      </div>
      <ul className="nav-links">
        {pages.map(({ id, label }) => (
          <li key={id}>
            <button
              type="button"
              className={`nav-link ${id === currentPage ? 'active' : ''}`}
              aria-current={id === currentPage ? 'page' : undefined}
              onClick={() => onNavigate(id)}
            >
              {label}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
