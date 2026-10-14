// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Poster } from './Poster'

afterEach(cleanup)

describe('Poster', () => {
  it('shows the picture taken from the film', () => {
    const { container } = render(<Poster titleId="a/b" fallbackMoon={60} />)
    const img = container.querySelector('img')!
    expect(img.getAttribute('src')).toBe('/api/titles/a%2Fb/media/poster')
    expect(img.getAttribute('alt')).toBe('') // decorative: the title's name sits beside it
    expect(container.querySelector('.harbor')).toBeNull()
  })

  it('falls back to the harbor scene when no picture can be made', () => {
    const { container } = render(<Poster titleId="t" fallbackMoon={60} />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.harbor')).toBeTruthy()
  })
})
