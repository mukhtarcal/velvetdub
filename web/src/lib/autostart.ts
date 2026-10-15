import type { ProcessChoices } from '../api/types'

// "Add a title" hands its choices to the processing page, which starts the job on arrival.
// The router carried this as navigation state before; it now rides in sessionStorage for one hop.
const key = (titleId: string) => `velvetdub:autostart:${titleId}`

export function saveAutostart(titleId: string, choices: ProcessChoices): void {
  try {
    sessionStorage.setItem(key(titleId), JSON.stringify(choices))
  } catch {
    // storage blocked: the processing page then offers "Try again" with the saved choices
  }
}

/** Read and forget, so a reload does not start the job twice. */
export function takeAutostart(titleId: string): ProcessChoices | undefined {
  try {
    const raw = sessionStorage.getItem(key(titleId))
    sessionStorage.removeItem(key(titleId))
    return raw ? (JSON.parse(raw) as ProcessChoices) : undefined
  } catch {
    return undefined
  }
}
