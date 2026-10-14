import { describe, expect, it } from 'vitest'
import { categoryLabel, formatBytes, formatDuration, formatTime, joinLabels } from './format'

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

describe('sizes and durations', () => {
  it('writes sizes in plain units', () => {
    expect(formatBytes(2_400_000_000)).toBe('2.4 GB')
    expect(formatBytes(640_000_000)).toBe('640 MB')
    expect(formatBytes(1)).toBe('1 KB')
  })

  it('writes durations for sentences', () => {
    expect(formatDuration(192)).toBe('3 min 12 s')
    expect(formatDuration(45)).toBe('45 s')
    expect(formatDuration(180)).toBe('3 min')
    expect(formatDuration(3720)).toBe('1 h 2 min')
  })
})
