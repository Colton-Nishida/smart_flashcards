import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage, isUnauthorized, login, register } from '../api'
import type { User } from '../api'

type Mode = 'login' | 'register'

interface LoginProps {
  onLogin: (user: User) => void
}

export default function Login({ onLogin }: LoginProps) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function switchMode(next: Mode) {
    setMode(next)
    setError(null)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      if (mode === 'register') {
        await register(username, password, inviteCode.trim())
      }
      // Register doesn't necessarily set the session cookie — log in either way.
      onLogin(await login(username, password))
    } catch (err) {
      if (mode === 'login' && isUnauthorized(err)) {
        setError('Wrong username or password.')
      } else {
        setError(errorMessage(err))
      }
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <h1 className="font-display text-4xl font-semibold tracking-tight">Smart Flashcards</h1>
      <p className="mt-2 text-sm text-stone-500">Turn any PDF into a deck worth studying.</p>

      <form
        onSubmit={handleSubmit}
        className="mt-10 w-full max-w-sm rounded-xl border border-stone-200 bg-card p-6 shadow-sm"
      >
        <h2 className="font-display text-xl font-medium">
          {mode === 'login' ? 'Sign in' : 'Create an account'}
        </h2>

        <label className="mt-5 block text-sm font-medium text-stone-700">
          Username
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
            autoComplete="username"
            disabled={busy}
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
          />
        </label>

        <label className="mt-4 block text-sm font-medium text-stone-700">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            disabled={busy}
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
          />
        </label>

        {mode === 'register' && (
          <label className="mt-4 block text-sm font-medium text-stone-700">
            Invite code <span className="font-normal text-stone-400">(if you were given one)</span>
            <input
              type="text"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              autoComplete="off"
              disabled={busy}
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
            />
          </label>
        )}

        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 w-full rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-60"
        >
          {busy ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>

      <p className="mt-5 text-sm text-stone-500">
        {mode === 'login' ? (
          <>
            New here?{' '}
            <button
              type="button"
              onClick={() => switchMode('register')}
              className="font-medium text-accent hover:underline"
            >
              Create an account
            </button>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <button
              type="button"
              onClick={() => switchMode('login')}
              className="font-medium text-accent hover:underline"
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  )
}
