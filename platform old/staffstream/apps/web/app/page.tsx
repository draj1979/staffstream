// Landing / redirect page
// Unauthenticated users → /auth/login
// Admin users → /dashboard
// Employee users → /portal
import { redirect } from 'next/navigation'

export default function Home() {
  redirect('/api/auth/login')
}
