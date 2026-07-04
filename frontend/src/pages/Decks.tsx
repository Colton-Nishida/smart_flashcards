import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, listDecks } from '../api'
import type { DeckSummary } from '../api'
import { formatDate } from '../lib/format'

export default function Decks() {
  const [decks, setDecks] = useState<DeckSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listDecks()
      .then((result) => {
        if (!cancelled) setDecks(result)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold tracking-tight">Your decks</h1>

      {error && <p className="mt-6 text-sm text-red-700">{error}</p>}

      {!error && decks === null && <p className="mt-6 text-sm text-stone-400">Loading decks…</p>}

      {decks !== null && decks.length === 0 && (
        <div className="mt-10 rounded-xl border border-dashed border-stone-300 p-10 text-center">
          <p className="font-display text-lg">No decks yet</p>
          <p className="mt-1 text-sm text-stone-500">
            Upload a PDF and Claude will write your first deck.
          </p>
          <Link
            to="/upload"
            className="mt-5 inline-block rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-deep"
          >
            Upload a PDF
          </Link>
        </div>
      )}

      {decks !== null && decks.length > 0 && (
        <ul className="mt-6 space-y-3">
          {decks.map((deck) => (
            <li key={deck.id}>
              <Link
                to={`/decks/${deck.id}`}
                className="block rounded-xl border border-stone-200 bg-card p-5 shadow-sm transition-colors hover:border-accent/50"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <h2 className="font-display text-xl font-medium">{deck.name}</h2>
                  <span className="shrink-0 text-sm text-stone-500">
                    {deck.card_count} {deck.card_count === 1 ? 'card' : 'cards'}
                  </span>
                </div>
                {deck.description && (
                  <p className="mt-1 line-clamp-2 text-sm text-stone-600">{deck.description}</p>
                )}
                <p className="mt-2 text-xs text-stone-400">Created {formatDate(deck.created_at)}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
