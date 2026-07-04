import { useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api'
import type { CardInput } from '../api'

interface AddCardFormProps {
  onAdd: (card: CardInput) => Promise<void>
}

export default function AddCardForm({ onAdd }: AddCardFormProps) {
  const [open, setOpen] = useState(false)
  const [front, setFront] = useState('')
  const [back, setBack] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onAdd({ front: front.trim(), back: back.trim() })
      setFront('')
      setBack('')
      setOpen(false)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="mt-4 w-full rounded-lg border border-dashed border-stone-300 py-3 text-sm font-medium text-stone-500 hover:border-accent/50 hover:text-accent"
      >
        + Add a card
      </button>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-4 space-y-3 rounded-lg border border-accent/40 bg-card p-4"
    >
      <label className="block text-xs font-medium uppercase tracking-wide text-stone-500">
        Front
        <textarea
          value={front}
          onChange={(e) => setFront(e.target.value)}
          required
          rows={2}
          autoFocus
          disabled={busy}
          placeholder="Question or prompt"
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
          placeholder="Answer"
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
          Add card
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          disabled={busy}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
