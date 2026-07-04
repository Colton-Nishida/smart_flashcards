import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { getMe, logout, UNAUTHORIZED_EVENT } from './api'
import type { User } from './api'
import Login from './pages/Login'
import Upload from './pages/Upload'
import Decks from './pages/Decks'
import DeckView from './pages/DeckView'

export default function App() {
  // undefined = still checking the session, null = signed out.
  const [user, setUser] = useState<User | null | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) setUser(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Any API call that comes back 401 kicks the user to the login screen.
  useEffect(() => {
    const onUnauthorized = () => setUser(null)
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  if (user === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-stone-400">
        Loading…
      </div>
    )
  }

  if (user === null) {
    return <Login onLogin={setUser} />
  }

  return <Shell user={user} onSignedOut={() => setUser(null)} />
}

interface ShellProps {
  user: User
  onSignedOut: () => void
}

function Shell({ user, onSignedOut }: ShellProps) {
  const [loggingOut, setLoggingOut] = useState(false)

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } catch {
      // Clear the client session regardless — worst case the cookie lingers.
    } finally {
      onSignedOut()
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-stone-200 bg-card">
        <div className="mx-auto flex max-w-3xl items-center gap-6 px-4 py-3">
          <span className="font-display text-lg font-semibold tracking-tight">
            Smart Flashcards
          </span>
          <nav className="flex gap-1">
            <Tab to="/upload">Upload</Tab>
            <Tab to="/decks">Decks</Tab>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-sm text-stone-500 sm:inline">{user.username}</span>
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-60"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Navigate to="/decks" replace />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/decks" element={<Decks />} />
          <Route path="/decks/:deckId" element={<DeckView />} />
          <Route path="*" element={<Navigate to="/decks" replace />} />
        </Routes>
      </main>
    </div>
  )
}

function Tab({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-sm font-medium ${
          isActive ? 'bg-ink text-paper' : 'text-stone-600 hover:bg-stone-100'
        }`
      }
    >
      {children}
    </NavLink>
  )
}
