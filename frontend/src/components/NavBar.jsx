export default function NavBar({ pages, currentPage, onNavigate }) {
  return (
    <nav>
      <strong className="brand">Sentinel-X</strong>
      <ul>
        {pages.map(({ id, label }) => (
          <li key={id}>
            <button
              type="button"
              className={id === currentPage ? 'active' : undefined}
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
