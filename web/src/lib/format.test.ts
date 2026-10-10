import { describe, expect, it } from 'vitest'
import { categoryLabel, formatTime, joinLabels } from './format'

describe('formatTime', () => {
  it.each([
    [0, '0:00'],
    [9.9, '0:09'],
    [2478, '41:18'],
    [3723, '1:02:03'],
    [-5, '0:00'],
  ])('%s -> %s', (seconds, expected) => {
    expect(formatTime(seconds)).toBe(expected)
  })
})

describe('labels', () => {
  it('uses plain category names', () => {
    expect(categoryLabel('drugs_and_drinking')).toBe('drugs and drinking')
    expect(categoryLabel('something_new')).toBe('something new')
  })
  it('joins lists in plain English without duplicates', () => {
    expect(joinLabels([])).toBe('')
    expect(joinLabels(['violence', 'violence'])).toBe('violence')
    expect(joinLabels(['violence', 'nudity'])).toBe('violence and nudity')
    expect(joinLabels(['a', 'b', 'c'])).toBe('a, b and c')
  })
})
