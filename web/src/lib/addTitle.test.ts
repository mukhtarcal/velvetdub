import { describe, expect, it } from 'vitest'
import {
  choseAnything,
  dubbingSummary,
  needsDubLanguage,
  needsLanguage,
  processChoices,
  skipSummary,
  submitState,
  subtitleSummary,
  type AddTitleForm,
} from './addTitle'

const form: AddTitleForm = {
  hasFile: true,
  name: 'Harbor Lights 1947',
  filters: [],
  subtitlesOn: false,
  languages: [],
  dubbingOn: false,
  dubLanguages: [],
}

describe('submit rules', () => {
  it('is allowed with nothing chosen: everything is optional, and nothing is processed', () => {
    expect(submitState(form)).toEqual({
      canSubmit: true,
      hint: 'Next, we upload the film. Nothing else is processed.',
    })
  })

  it('says processing starts once anything is chosen', () => {
    expect(submitState({ ...form, filters: ['swearing'] }).hint).toBe('Next, we upload the film and start processing.')
    expect(submitState({ ...form, subtitlesOn: true, languages: ['en'] }).hint).toBe(
      'Next, we upload the film and start processing.',
    )
  })

  it('does not count a switch that is on with nothing ticked as a choice', () => {
    expect(choseAnything({ ...form, subtitlesOn: true })).toBe(false)
    expect(choseAnything({ ...form, dubbingOn: true })).toBe(false)
    expect(choseAnything({ ...form, filters: ['violence'] })).toBe(true)
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

  it('is held back when dubbing is on but no language is chosen', () => {
    const on = { ...form, dubbingOn: true }
    expect(needsDubLanguage(on)).toBe(true)
    expect(submitState(on)).toEqual({ canSubmit: false, hint: 'Choose a dubbing language first.' })
    expect(submitState({ ...on, dubLanguages: ['ar'] }).canSubmit).toBe(true)
  })

  it('warns that a dub is the slowest part once one is chosen', () => {
    const state = submitState({ ...form, dubbingOn: true, dubLanguages: ['ar'] })
    expect(state.hint).toBe('Next, we upload the film and start processing. The dub is the slowest part.')
  })

  it('checks subtitles before dubbing, so one reason is given at a time', () => {
    const both = { ...form, subtitlesOn: true, dubbingOn: true }
    expect(submitState(both).hint).toBe('Choose a subtitle language first.')
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
    expect(skipSummary(['swearing', 'nudity'])).toBe('Nudity and swearing') // swearing is offered last
  })

  it('lists subtitle languages, or None', () => {
    expect(subtitleSummary({ subtitlesOn: false, languages: ['en'] })).toBe('None')
    expect(subtitleSummary({ subtitlesOn: true, languages: [] })).toBe('None')
    expect(subtitleSummary({ subtitlesOn: true, languages: ['en', 'es'] })).toBe('English and Spanish')
  })

  it('lists dubbing languages, or None', () => {
    expect(dubbingSummary({ dubbingOn: false, dubLanguages: ['ar'] })).toBe('None')
    expect(dubbingSummary({ dubbingOn: true, dubLanguages: [] })).toBe('None')
    expect(dubbingSummary({ dubbingOn: true, dubLanguages: ['ar', 'es'] })).toBe('Arabic and Spanish')
  })
})

describe('what is sent', () => {
  it('sends no languages when subtitles are off, and filters in a fixed order', () => {
    expect(
      processChoices({
        filters: ['violence', 'nudity'],
        subtitlesOn: false,
        languages: ['en'],
        dubbingOn: false,
        dubLanguages: ['ar'],
      }),
    ).toEqual({ filter_categories: ['nudity', 'violence'], subtitle_languages: [], dub_languages: [] })
  })

  it('sends swearing as a filter, after the picture ones', () => {
    expect(
      processChoices({
        filters: ['swearing', 'violence'],
        subtitlesOn: false,
        languages: [],
        dubbingOn: false,
        dubLanguages: [],
      }).filter_categories,
    ).toEqual(['violence', 'swearing'])
  })

  it('sends the chosen languages when subtitles are on', () => {
    expect(
      processChoices({ filters: [], subtitlesOn: true, languages: ['ur'], dubbingOn: false, dubLanguages: [] }),
    ).toEqual({ filter_categories: [], subtitle_languages: ['ur'], dub_languages: [] })
  })

  it('sends the chosen dub languages when dubbing is on, alongside subtitles', () => {
    expect(
      processChoices({ filters: [], subtitlesOn: true, languages: ['en'], dubbingOn: true, dubLanguages: ['ar'] }),
    ).toEqual({ filter_categories: [], subtitle_languages: ['en'], dub_languages: ['ar'] })
  })
})
