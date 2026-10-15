import { LANGUAGES } from '@/lib/titles'
import { cn } from '@/lib/utils'

/** Toggle chips for choosing subtitle languages. Choosing none is allowed while editing; the
 * page explains it and holds back the submit button. */
export function LanguagePicker({
  value,
  onChange,
  disabled,
}: {
  value: string[]
  onChange: (languages: string[]) => void
  disabled?: boolean
}) {
  function toggle(code: string) {
    onChange(value.includes(code) ? value.filter((c) => c !== code) : [...value, code])
  }

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Subtitle languages">
      {LANGUAGES.map((language) => {
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
