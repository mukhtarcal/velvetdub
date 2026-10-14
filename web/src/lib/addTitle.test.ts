import { describe, expect, it } from 'vitest'
import {
  needsLanguage,
  processChoices,
  skipSummary,
  submitState,
  subtitleSummary,
  type AddTitleForm,
} from './addTitle'

const form: AddTitleForm = { hasFile: true, name: 'Harbor Lights 1947', filters: [], subtitlesOn: false, languages: [] }

describe('submit rules', () => {
  it('is allowed with nothing chosen: filters and subtitles are both optional', () => {
    expect(submitState(form)).toEqual({
      canSubmit: true,
      hint: 'Next, we upload the film and start the scan.',
    })
  })

  it('needs a file, and says so first', () => {
    expect(submitState({ ...form, hasFile: false, name: '' })).toEqual({
      canSubmit: false,
      hint: 'Choose a file first.',
    })
  })

  it('needs a name', () => {
    expect(submitState({ ...form, name: '   ' }).canSubmit).toBe(false)
  })

  it('is held back when subtitles are on but no language is chosen', () => {
    const on = { ...form, subtitlesOn: true }
    expect(needsLanguage(on)).toBe(true)
    expect(submitState(on)).toEqual({ canSubmit: false, hint: 'Choose a subtitle language first.' })
    expect(submitState({ ...on, languages: ['en'] }).canSubmit).toBe(true)
  })

  it('ignores ticked languages while subtitles are off', () => {
    const off = { ...form, languages: [] as string[] }
    expect(needsLanguage(off)).toBe(false)
  })
})

describe('summary', () => {
  it('says the film plays as is when nothing is skipped', () => {
    expect(skipSummary([])).toBe('Nothing. The film plays as is.')
  })

  it('lists the chosen filters in plain words, in the order they are offered', () => {
    expect(skipSummary(['sexual_content'])).toBe('Sex scenes')
    expect(skipSummary(['violence', 'nudity'])).toBe('Nudity and violence')
    expect(skipSummary(['violence', 'scary_scenes', 'nudity'])).toBe('Nudity, scary scenes and violence')
  })

  it('lists subtitle languages, or None', () => {
    expect(subtitleSummary({ subtitlesOn: false, languages: ['en'] })).toBe('None')
    expect(subtitleSummary({ subtitlesOn: true, languages: [] })).toBe('None')
    expect(subtitleSummary({ subtitlesOn: true, languages: ['en', 'es'] })).toBe('English and Spanish')
  })
})

describe('what is sent', () => {
  it('sends no languages when subtitles are off, and filters in a fixed order', () => {
    expect(
      processChoices({ filters: ['violence', 'nudity'], subtitlesOn: false, languages: ['en'] }),
    ).toEqual({ filter_categories: ['nudity', 'violence'], subtitle_languages: [] })
  })

  it('sends the chosen languages when subtitles are on', () => {
    expect(processChoices({ filters: [], subtitlesOn: true, languages: ['ur'] })).toEqual({
      filter_categories: [],
      subtitle_languages: ['ur'],
    })
  })
})
