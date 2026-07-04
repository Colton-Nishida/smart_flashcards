import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api'
import type { Card, CardPatch } from '../api'

interface CardRowProps {
  card: Card
  onSave: (patch: CardPatch) => Promise<void>
  onDelete: () => Promise<void>
}

function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
}

export default function CardRow({ card, onSave, onDelete }: CardRowProps) {
  const [editing, setEditing] = useState(false)
  const [front, setFront] = useState(card.front)
  const [back, setBack] = useState(card.back)
  const [tags, setTags] = useState(card.tags.join(', '))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function startEditing() {
    setFront(card.front)
    setBack(card.back)
    setTags(card.tags.join(', '))
    setError(null)
    setEditing(true)
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSave({ front: front.trim(), back: back.trim(), tags: parseTags(tags) })
      setEditing(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm('Delete this card?')) return
    setBusy(true)
    setError(null)
    try {
      await onDelete()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  if (editing) {
    return (
      <li className="rounded-lg border border-accent/40 bg-card p-4">
        <form onSubmit={handleSave} className="space-y-3">
          <label className="block text-xs font-medium uppercase tracking-wide text-stone-500">
            Front
            <textarea
              value={front}
              onChange={(e) => setFront(e.target.value)}
              required
              rows={2}
              disabled={busy}
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm normal-case tracking-normal outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </label>
          <label className="block text-xs font-medium uppercase tracking-wide text-stone-500">
            Back
            <textarea
              value={back}
              onChange={(e) => setBack(e.target.value)}
              required
              rows={3}
              disabled={busy}
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm normal-case tracking-normal outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </label>
          <label className="block text-xs font-medium uppercase tracking-wide text-stone-500">
            Tags (comma-separated)
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              disabled={busy}
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm normal-case tracking-normal outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
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
      </li>
    )
  }

  return (
    <li className="group rounded-lg border border-stone-200 bg-card p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Front</p>
          <p className="mt-1 whitespace-pre-wrap text-sm">{card.front}</p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Back</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-stone-700">{card.back}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2">
        {card.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-500"
          >
            {tag}
          </span>
        ))}
        <span className="ml-auto flex gap-2 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
          <button
            onClick={startEditing}
            disabled={busy}
            className="text-xs font-medium text-stone-500 hover:text-accent"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            disabled={busy}
            className="text-xs font-medium text-stone-500 hover:text-red-700"
          >
            Delete
          </button>
        </span>
      </div>
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
    </li>
  )
}
