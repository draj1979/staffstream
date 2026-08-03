import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'StaffStream',
  description: 'An AI assistant for every employee.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
