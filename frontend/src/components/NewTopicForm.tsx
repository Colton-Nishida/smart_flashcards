import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { createTopic, errorMessage } from '../api'
import type { Topic } from '../api'

const MAX_PDF_BYTES = 20 * 1024 * 1024 // 20 MB, mirrors the backend cap

function validateFile(file: File): string | null {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) return 'Only PDF files are supported.'
  if (file.size > MAX_PDF_BYTES) {
    return `That file is ${(file.size / (1024 * 1024)).toFixed(1)} MB — the limit is 20 MB.`
  }
  return null
}

interface NewTopicFormProps {
  onCreated: (topic: Topic) => void
  onCancel: () => void
}

export default function NewTopicForm({ onCreated, onCancel }: NewTopicFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [instructions, setInstructions] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0] ?? null
    setError(picked ? validateFile(picked) : null)
    setFile(picked)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (extracting || !file) return
    const problem = validateFile(file)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setExtracting(true)
    try {
      onCreated(await createTopic(file, name.trim(), description.trim(), instructions.trim()))
    } catch (err) {
      setError(errorMessage(err))
      setExtracting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-stone-200 bg-card p-4 shadow-sm"
    >
      <fieldset disabled={extracting} className="space-y-3">
        <label className="block text-sm font-medium text-stone-700">
          PDF document
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={handleFileChange}
            required
            className="mt-1 w-full text-sm text-stone-600 file:mr-3 file:rounded-md file:border-0 file:bg-stone-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-stone-700 hover:file:bg-stone-200"
          />
        </label>
        <label className="block text-sm font-medium text-stone-700">
          Topic name
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
            placeholder="Photosynthesis"
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </label>
        <label className="block text-sm font-medium text-stone-700">
          Description <span className="font-normal text-stone-400">(optional)</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="What is this topic about?"
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
        </label>
        <label className="block text-sm font-medium text-stone-700">
          Instructions for the tutor{' '}
          <span className="font-normal text-stone-400">(optional)</span>
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
            maxLength={4000}
            placeholder="e.g. “Only cover section 3 of the PDF” · “Ask definition-style questions only” · “Make the questions hard”"
            className="mt-1 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          />
          <span className="mt-1 block text-xs font-normal text-stone-400">
            The tutor follows these when writing notes, picking questions, and scoring.
          </span>
        </label>
      </fieldset>

      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}

      {extracting ? (
        <div className="mt-4 flex items-center gap-2 rounded-md bg-stone-100 px-3 py-2 text-sm">
          <span
            aria-hidden
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-stone-300 border-t-accent"
          />
          <span className="text-stone-600">Claude is reading the PDF and writing study notes…</span>
        </div>
      ) : (
        <div className="mt-4 flex gap-2">
          <button
            type="submit"
            disabled={!file || Boolean(file && validateFile(file))}
            className="rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-50"
          >
            Create topic
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-stone-300 px-4 py-1.5 text-sm font-medium text-stone-600 hover:bg-stone-100"
          >
            Cancel
          </button>
        </div>
      )}
    </form>
  )
}
