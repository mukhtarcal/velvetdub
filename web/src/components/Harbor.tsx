/** Flat harbor scene shown until real frames from the film exist (docs/BRAND.md, imagery). */
export function Harbor({ moon = 60, beam = false }: { moon?: number; beam?: boolean }) {
  return (
    <svg className="harbor" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="320" height="180" fill="var(--night-sky)" />
      {beam && <path d="M0 70 L250 98 L250 104 L0 120 Z" fill="#262c35" />}
      <circle cx={moon} cy="38" r="9" fill="var(--muted)" />
      <rect y="118" width="320" height="62" fill="var(--night-sea)" />
      <path d="M180 124 C 210 108, 260 106, 320 112 L 320 126 L 180 126 Z" fill="var(--silhouette)" />
      <rect x="244" y="78" width="8" height="34" fill="var(--silhouette)" />
      <rect x="245" y="82" width="6" height="6" fill="var(--lamp)" />
    </svg>
  )
}
