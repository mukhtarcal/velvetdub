import { NavLink, Outlet } from 'react-router-dom'

// Only pages that exist are listed. Profiles and Settings arrive in later steps (1.4, 1.5).
const NAV = [
  { to: '/', label: 'Library', end: true },
  { to: '/add', label: 'Add a title', end: false },
]

export function AppLayout() {
  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <div className="wordmark">Velvet Dub</div>
        <div className="gilt-rule" aria-hidden="true" />
        <ul>
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.end}>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
