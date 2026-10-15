import type { Metadata, Viewport } from 'next'
import { Archivo, Limelight } from 'next/font/google'
import { MotionProvider } from '@/components/brand/MotionProvider'
import './globals.css'

const limelight = Limelight({ weight: '400', subsets: ['latin'], variable: '--font-limelight' })
const archivo = Archivo({ subsets: ['latin'], axes: ['wdth'], variable: '--font-archivo' })

export const metadata: Metadata = {
  title: 'Velvet Dub',
  description: 'A movie palace in your living room.',
  icons: { icon: '/favicon.svg' },
}

export const viewport: Viewport = { colorScheme: 'dark', themeColor: '#0f0b0b' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${limelight.variable} ${archivo.variable}`}>
      <body className="min-h-svh">
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  )
}
