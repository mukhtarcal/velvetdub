import { LANGUAGES } from '../lib/titles'

/** Toggle chips for choosing subtitle languages. At least one stays chosen. */
export function LanguagePicker({
  value,
  onChange,
}: {
  value: string[]
  onChange: (languages: string[]) => void
}) {
  function toggle(code: string) {
    const next = value.includes(code) ? value.filter((c) => c !== code) : [...value, code]
    if (next.length > 0) onChange(next)
  }

  return (
    <div className="chips" role="group" aria-label="Subtitle languages">
      {LANGUAGES.map((language) => (
        <button
          key={language.code}
          type="button"
          className="chip"
          aria-pressed={value.includes(language.code)}
          onClick={() => toggle(language.code)}
        >
          {language.label}
        </button>
      ))}
    </div>
  )
}
