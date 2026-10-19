import { motion } from 'motion/react'

/** A two-way choice for an optional section ("No subtitles" | "Add subtitles"), styled as the
 * brand's segmented control. A radio group: `layoutId` must differ between toggles on one page. */
export function OptionToggle({
  label,
  layoutId,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string
  layoutId: string
  value: boolean
  options: [off: string, on: string]
  onChange: (on: boolean) => void
  disabled?: boolean
}) {
  const choices = [
    { on: false, label: options[0] },
    { on: true, label: options[1] },
  ]
  return (
    <div className="flex w-fit gap-0 border border-border-control bg-panel p-1" role="radiogroup" aria-label={label}>
      {choices.map((option) => (
        <button
          key={option.label}
          type="button"
          role="radio"
          aria-checked={value === option.on}
          disabled={disabled}
          onClick={() => onChange(option.on)}
          className="relative min-h-11 cursor-pointer px-5 text-[15px] text-ink-soft transition-colors aria-checked:text-ink disabled:cursor-not-allowed disabled:opacity-45"
        >
          {value === option.on && (
            <motion.span
              layoutId={layoutId}
              className="absolute inset-0 bg-velvet"
              transition={{ type: 'spring', stiffness: 500, damping: 40 }}
            />
          )}
          <span className="relative">{option.label}</span>
        </button>
      ))}
    </div>
  )
}
