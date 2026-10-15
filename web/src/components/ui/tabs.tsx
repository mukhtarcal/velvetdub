'use client'

import * as React from 'react'
import { Tabs as TabsPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

// Two looks (docs/BRAND.md): `page` tabs sit on a hairline with a velvet rule under the chosen
// one; `inner` tabs are smaller segmented controls inside a panel, the chosen one in velvet.
type Level = 'page' | 'inner'

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root data-slot="tabs" className={cn('flex flex-col', className)} {...props} />
}

function TabsList({
  className,
  level = 'page',
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> & { level?: Level }) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-level={level}
      className={cn(
        'group/tabs-list flex max-w-full overflow-x-auto [scrollbar-width:none]',
        level === 'page' ? 'gap-1 border-b border-line' : 'w-fit flex-wrap gap-1.5',
        className,
      )}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        'relative inline-flex min-h-11 cursor-pointer items-center whitespace-nowrap text-muted-foreground transition-colors duration-200 hover:text-ink data-[state=active]:text-ink',
        // page level: a velvet rule grows in under the chosen tab
        'group-data-[level=page]/tabs-list:px-4 group-data-[level=page]/tabs-list:text-[16px]',
        'group-data-[level=page]/tabs-list:after:absolute group-data-[level=page]/tabs-list:after:inset-x-3 group-data-[level=page]/tabs-list:after:-bottom-px group-data-[level=page]/tabs-list:after:h-[3px] group-data-[level=page]/tabs-list:after:origin-left group-data-[level=page]/tabs-list:after:scale-x-0 group-data-[level=page]/tabs-list:after:bg-velvet group-data-[level=page]/tabs-list:after:transition-transform group-data-[level=page]/tabs-list:after:duration-300 group-data-[level=page]/tabs-list:data-[state=active]:after:scale-x-100',
        // inner level: segmented control
        'group-data-[level=inner]/tabs-list:rounded-sm group-data-[level=inner]/tabs-list:border group-data-[level=inner]/tabs-list:border-border-control group-data-[level=inner]/tabs-list:bg-panel group-data-[level=inner]/tabs-list:px-3.5 group-data-[level=inner]/tabs-list:text-[14.5px] group-data-[level=inner]/tabs-list:data-[state=active]:border-velvet group-data-[level=inner]/tabs-list:data-[state=active]:bg-velvet',
        className,
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn('pt-6 outline-none data-[state=active]:animate-in data-[state=active]:fade-in-0 data-[state=active]:duration-300', className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
