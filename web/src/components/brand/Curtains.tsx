/** Decorative curtains and valance (docs/BRAND.md, motifs). Everything here is hidden from
 * screen readers; the heading and status text carry the meaning. */

/** Two curtain panels. Shut, they meet in the middle; open, they are drawn back to the sides.
 * `animate` turns the movement on, so a page that loads already open does not play it. */
export function Curtains({ open, animate }: { open: boolean; animate: boolean }) {
  return (
    <div className="curtains" data-open={open} data-animate={animate} aria-hidden="true">
      <div className="drape left" />
      <div className="drape right" />
      <div className="tie cord left" />
      <div className="tie tassel left" />
      <div className="tie cord right" />
      <div className="tie tassel right" />
    </div>
  )
}

/** The pelmet and four festoon swags across the top of the stage. */
export function Valance() {
  return (
    <div className="valance" aria-hidden="true">
      <div className="pelmet" />
      <svg viewBox="0 0 1000 60" preserveAspectRatio="none">
        <path
          d="M0 0 Q125 64 250 0 Z M250 0 Q375 64 500 0 Z M500 0 Q625 64 750 0 Z M750 0 Q875 64 1000 0 Z"
          style={{ fill: 'var(--velvet-mid)' }}
        />
        <path
          d="M40 0 Q125 40 210 0 M290 0 Q375 40 460 0 M540 0 Q625 40 710 0 M790 0 Q875 40 960 0"
          fill="none"
          style={{ stroke: 'var(--velvet-deep)' }}
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d="M70 0 Q125 22 180 0 M320 0 Q375 22 430 0 M570 0 Q625 22 680 0 M820 0 Q875 22 930 0"
          fill="none"
          style={{ stroke: 'var(--velvet-sheen)' }}
          strokeOpacity="0.35"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d="M0 0 Q125 64 250 0 Q375 64 500 0 Q625 64 750 0 Q875 64 1000 0"
          fill="none"
          style={{ stroke: 'var(--gilt)' }}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d="M0 3 Q125 67 250 3 Q375 67 500 3 Q625 67 750 3 Q875 67 1000 3"
          fill="none"
          style={{ stroke: 'var(--fringe)' }}
          strokeWidth="4"
          strokeDasharray="1 3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}

/** Shut curtains and a small valance over a library poster, with no movement. */
export function PosterCurtains() {
  return (
    <div className="poster-curtains" aria-hidden="true">
      <Curtains open={false} animate={false} />
      <div className="valance-strip" />
    </div>
  )
}
