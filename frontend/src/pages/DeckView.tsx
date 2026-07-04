import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  createCard,
  deleteCard,
  deleteDeck,
  errorMessage,
  getDeck,
  updateCard,
  updateDeck,
} from '../api'
import type { Card, CardInput, CardPatch, Deck } from '../api'
import AddCardForm from '../components/AddCardForm'
import CardRow from '../components/CardRow'
import StudyMode from '../components/StudyMode'
import { formatDate } from '../lib/format'

export default function DeckView() {
  const { deckId } = useParams<{ deckId: string }>()
  const navigate = useNavigate()
  const [deck, setDeck] = useState<Deck | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [studying, setStudying] = useState(false)

  useEffect(() => {
    if (!deckId) return
    let cancelled = false
    getDeck(deckId)
      .then((result) => {
        if (!cancelled) setDeck(result)
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [deckId])

  if (!deckId) return null

  if (error) {
    return (
      <div>
        <p className="text-sm text-red-700">{error}</p>
        <Link to="/decks" className="mt-4 inline-block text-sm font-medium text-accent hover:underline">
          ← Back to decks
        </Link>
      </div>
    )
  }

  if (!deck) {
    return <p className="text-sm text-stone-400">Loading deck…</p>
  }

  if (studying) {
    return <StudyMode deckName={deck.name} cards={deck.cards} onExit={() => setStudying(false)} />
  }

  async function handleSaveMeta(name: string, description: string) {
    const updated = await updateDeck(deckId!, { name, description })
    setDeck((d) => (d ? { ...d, name: updated.name, description: updated.description } : d))
  }

  async function handleDeleteDeck() {
    if (!window.confirm(`Delete the deck “${deck!.name}” and all its cards?`)) return
    try {
      await deleteDeck(deckId!)
      navigate('/decks')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function handleAddCard(input: CardInput) {
    const card = await createCard(deckId!, input)
    setDeck((d) => (d ? { ...d, cards: [...d.cards, card] } : d))
  }

  async function handleSaveCard(cardId: string, patch: CardPatch) {
    const updated = await updateCard(deckId!, cardId, patch)
    setDeck((d) =>
      d ? { ...d, cards: d.cards.map((c) => (c.id === cardId ? updated : c)) } : d,
    )
  }

  async function handleDeleteCard(cardId: string) {
    await deleteCard(deckId!, cardId)
    setDeck((d) => (d ? { ...d, cards: d.cards.filter((c) => c.id !== cardId) } : d))
  }

  return (
    <div>
      <Link to="/decks" className="text-sm font-medium text-accent hover:underline">
        ← All decks
      </Link>

      <DeckHeader
        deck={deck}
        onSave={handleSaveMeta}
        onDelete={handleDeleteDeck}
        onStudy={() => setStudying(true)}
      />

      <section className="mt-8">
        <h2 className="text-xs font-medium uppercase tracking-wide text-stone-400">
          Cards ({deck.cards.length})
        </h2>
        {deck.cards.length === 0 && (
          <p className="mt-3 text-sm text-stone-500">
            This deck has no cards yet — add one below.
          </p>
        )}
        <ul className="mt-3 space-y-3">
          {deck.cards.map((card: Card) => (
            <CardRow
              key={card.id}
              card={card}
              onSave={(patch) => handleSaveCard(card.id, patch)}
              onDelete={() => handleDeleteCard(card.id)}
            />
          ))}
        </ul>
        <AddCardForm onAdd={handleAddCard} />
      </section>
    </div>
  )
}

interface DeckHeaderProps {
  deck: Deck
  onSave: (name: string, description: string) => Promise<void>
  onDelete: () => void
  onStudy: () => void
}

function DeckHeader({ deck, onSave, onDelete, onStudy }: DeckHeaderProps) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(deck.name)
  const [description, setDescription] = useState(deck.description)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function startEditing() {
    setName(deck.name)
    setDescription(deck.description)
    setError(null)
    setEditing(true)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSave(name.trim(), description.trim())
      setEditing(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (editing) {
    return (
      <form onSubmit={handleSubmit} className="mt-4 space-y-3 rounded-xl border border-accent/40 bg-card p-5">
        <label className="block text-sm font-medium text-stone-700">
          Deck name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={busy}
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </label>
        <label className="block text-sm font-medium text-stone-700">
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            disabled={busy}
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-60"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => setEditing(false)}
            disabled={busy}
            className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-60"
          >
            Cancel
          </button>
        </div>
      </form>
    )
  }

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">{deck.name}</h1>
          {deck.description && <p className="mt-2 text-sm text-stone-600">{deck.description}</p>}
          <p className="mt-2 text-xs text-stone-400">
            Created {formatDate(deck.created_at)} · from {deck.source_filename}
          </p>
        </div>
        <button
          onClick={onStudy}
          disabled={deck.cards.length === 0}
          className="rounded-md bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-50"
        >
          Study
        </button>
      </div>
      <div className="mt-3 flex gap-3">
        <button onClick={startEditing} className="text-xs font-medium text-stone-500 hover:text-accent">
          Edit deck
        </button>
        <button onClick={onDelete} className="text-xs font-medium text-stone-500 hover:text-red-700">
          Delete deck
        </button>
      </div>
    </div>
  )
}
