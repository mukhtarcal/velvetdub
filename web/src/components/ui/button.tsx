import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import { cn } from '@/lib/utils'

// docs/BRAND.md: primary = velvet fill with ivory text, one per screen. Secondary = border-strong
// outline. Text actions = underlined ivory.
const buttonVariants = cva(
  "relative inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-sm text-[15px] font-medium whitespace-nowrap select-none outline-none transition-[background-color,border-color,color,transform] duration-200 active:translate-y-px disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5",
  {
    variants: {
      variant: {
        primary:
          'min-h-12 border border-velvet bg-velvet px-7 text-ink hover:border-velvet-sheen hover:bg-[#a8202a]',
        secondary:
          'min-h-11 border border-border-strong bg-transparent px-5 text-ink hover:border-brass/70 hover:bg-raised/60',
        text: 'min-h-11 px-0 font-normal text-action',
        icon: 'size-11 border border-transparent text-ink hover:border-border-control',
      },
    },
    defaultVariants: { variant: 'secondary' },
  },
)

function Button({
  className,
  variant,
  asChild = false,
  type,
  ...props
}: React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : 'button'
  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      type={asChild ? undefined : (type ?? 'button')}
      className={cn(buttonVariants({ variant, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
