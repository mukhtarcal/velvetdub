/** The logo mark: "VD" in Limelight, in a velvet square ringed by brass marquee bulbs
 * (docs/BRAND.md, logo). On a velvet background the square drops to velvet-deep. */
const BULBS = (() => {
  // Evenly spaced around the square's edge, clockwise from the top-left corner.
  const perSide = 4
  const points: { x: number; y: number }[] = []
  for (let i = 0; i < perSide; i++) points.push({ x: (i / perSide) * 100, y: 0 })
  for (let i = 0; i < perSide; i++) points.push({ x: 100, y: (i / perSide) * 100 })
  for (let i = 0; i < perSide; i++) points.push({ x: 100 - (i / perSide) * 100, y: 100 })
  for (let i = 0; i < perSide; i++) points.push({ x: 0, y: 100 - (i / perSide) * 100 })
  return points
})()

export function Mark() {
  return (
    <span className="mark" aria-hidden="true">
      {BULBS.map((p, i) => (
        <span
          key={i}
          className="bulb"
          style={{ left: `calc(${p.x}% - 2px)`, top: `calc(${p.y}% - 2px)`, ['--i' as string]: i }}
        />
      ))}
      VD
    </span>
  )
}
