import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, createDeck, errorMessage } from '../api'

const MAX_PDF_BYTES = 20 * 1024 * 1024 // 20 MB, mirrors the backend cap

function validateFile(file: File): string | null {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) return 'Only PDF files are supported.'
  if (file.size > MAX_PDF_BYTES) {
    return `That file is ${(file.size / (1024 * 1024)).toFixed(1)} MB — the limit is 20 MB.`
  }
  return null
}

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    // 413 covers both an oversized file and too-many-cards-to-fit; the backend's
    // `detail` explains which, so surface it rather than guessing here.
    if (err.status === 0) return 'Could not reach the server — check that the backend is running, then try again.'
  }
  return errorMessage(err)
}

export default function Upload() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [additionalInstructions, setAdditionalInstructions] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0] ?? null
    setError(picked ? validateFile(picked) : null)
    setFile(picked)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (generating || !file) return
    const problem = validateFile(file)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setGenerating(true)
    try {
      const deck = await createDeck(
        file,
        name.trim(),
        description.trim(),
        additionalInstructions.trim(),
      )
      navigate(`/decks/${deck.id}`)
    } catch (err) {
      setError(friendlyError(err))
      setGenerating(false)
    }
  }

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold tracking-tight">New deck</h1>
      <p className="mt-2 text-sm text-stone-500">
        Upload a PDF and Claude will turn it into a flashcard deck.
      </p>

      <form
        onSubmit={handleSubmit}
        className="mt-8 rounded-xl border border-stone-200 bg-card p-6 shadow-sm"
      >
        <fieldset disabled={generating} className="space-y-5">
          <label className="block text-sm font-medium text-stone-700">
            PDF document
            <div className="mt-1 rounded-md border border-dashed border-stone-300 bg-white px-3 py-4">
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                required
                className="w-full text-sm text-stone-600 file:mr-4 file:rounded-md file:border-0 file:bg-stone-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-stone-700 hover:file:bg-stone-200"
              />
              <p className="mt-2 text-xs text-stone-400">One PDF becomes one deck · 20 MB max</p>
            </div>
          </label>

          <label className="block text-sm font-medium text-stone-700">
            Deck name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="Bio 101 – Chapter 4"
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </label>

          <label className="block text-sm font-medium text-stone-700">
            Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="What's this deck about? e.g. “Cell respiration, Bio 101 chapter 4”."
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </label>

          <label className="block text-sm font-medium text-stone-700">
            Additional instructions <span className="font-normal text-stone-400">(optional)</span>
            <textarea
              value={additionalInstructions}
              onChange={(e) => setAdditionalInstructions(e.target.value)}
              rows={3}
              placeholder="Tell Claude how to build the deck — e.g. “Only make cards about the water cycle”, “Focus on the first page”, or “Skip the summary section”."
              className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-base outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
            <p className="mt-1 text-xs text-stone-400">
              Cards are always drawn only from the PDF; this just guides what to focus on.
            </p>
          </label>
        </fieldset>

        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}

        {generating ? (
          <div className="mt-6 flex items-center gap-3 rounded-md bg-stone-100 px-4 py-3">
            <span
              aria-hidden
              className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-stone-300 border-t-accent"
            />
            <div className="text-sm">
              <p className="font-medium">Generating your deck…</p>
              <p className="text-stone-500">
                Claude is reading the PDF and writing cards. This usually takes 15–60 seconds —
                keep this tab open.
              </p>
            </div>
          </div>
        ) : (
          <button
            type="submit"
            disabled={!file || Boolean(file && validateFile(file))}
            className="mt-6 rounded-md bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-50"
          >
            Generate deck
          </button>
        )}
      </form>
    </div>
  )
}
