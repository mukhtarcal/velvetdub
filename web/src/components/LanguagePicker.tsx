import { LANGUAGES } from '@/lib/titles'
import { cn } from '@/lib/utils'

/** Toggle chips for choosing languages (subtitles or a dub). Choosing none is allowed while
 * editing; the page explains it and holds back the submit button. `only` limits the choices to
 * the languages on offer. */
export function LanguagePicker({
  value,
  onChange,
  disabled,
  label = 'Subtitle languages',
  only,
}: {
  value: string[]
  onChange: (languages: string[]) => void
  disabled?: boolean
  label?: string
  only?: string[]
}) {
  function toggle(code: string) {
    onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code])
  }

  const offered = only ? LANGUAGES.filter((l) => only.includes(l.code)) : LANGUAGES

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
      {offered.map((language) => {
        const on = value.includes(language.code)
        return (
          <button
            key={language.code}
            type="button"
            aria-pressed={on}
            disabled={disabled}
            onClick={() => toggle(language.code)}
            className={cn(
              'min-h-11 cursor-pointer rounded-sm border px-4 text-[15px] transition-colors duration-200 disabled:opacity-45',
              on
                ? 'border-velvet bg-velvet text-ink'
                : 'border-border-control bg-panel text-ink-soft hover:border-border-strong hover:text-ink',
            )}
          >
            {language.label}
          </button>
        )
      })}
    </div>
  )
}
