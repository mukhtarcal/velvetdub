// Few icons; words first. 2px stroke, ivory (currentColor), decorative (the button carries the label).

import type { ReactNode } from 'react'

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

export const PlayIcon = () => (
  <Icon>
    <path d="M7 4v16l13-8z" />
  </Icon>
)
export const PauseIcon = () => (
  <Icon>
    <path d="M8 4v16M16 4v16" />
  </Icon>
)
export const RewindIcon = () => (
  <Icon>
    <path d="M12 5a8 8 0 1 1-8 8M4 5v5h5" />
  </Icon>
)
export const FullScreenIcon = () => (
  <Icon>
    <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
  </Icon>
)
export const BackIcon = () => (
  <Icon>
    <path d="M15 5l-7 7 7 7" />
  </Icon>
)
export const VolumeIcon = ({ muted }: { muted: boolean }) => (
  <Icon>
    <path d="M4 9v6h4l5 4V5L8 9z" />
    {muted ? <path d="M17 9l4 6M21 9l-4 6" /> : <path d="M17 8a5 5 0 0 1 0 8" />}
  </Icon>
)
