import { LANGUAGES } from '../lib/titles'

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
    <div className="chips" role="group" aria-label="Subtitle languages">
      {LANGUAGES.map((language) => (
        <button
          key={language.code}
          type="button"
          className="chip"
          aria-pressed={value.includes(language.code)}
          disabled={disabled}
          onClick={() => toggle(language.code)}
        >
          {language.label}
        </button>
      ))}
    </div>
  )
}
