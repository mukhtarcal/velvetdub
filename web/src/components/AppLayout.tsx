import { Link, NavLink, Outlet } from 'react-router-dom'

// Only pages that exist are listed. Settings arrives in a later step (1.5).
const NAV = [
  { to: '/', label: 'Add a title', end: true },
  { to: '/library', label: 'Library', end: false },
]

/** A slim velvet bar across the top, with the page below it. */
export function AppLayout() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="wordmark">
            Velvet Dub
          </Link>
          <nav aria-label="Main">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </div>
  )
}
