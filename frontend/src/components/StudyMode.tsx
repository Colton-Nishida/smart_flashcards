import { useEffect, useState } from 'react'
import type { Card } from '../api'

interface StudyModeProps {
  deckName: string
  cards: Card[]
  onExit: () => void
}

function shuffle(cards: Card[]): Card[] {
  const result = [...cards]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

export default function StudyMode({ deckName, cards, onExit }: StudyModeProps) {
  const [queue, setQueue] = useState<Card[]>(() => shuffle(cards))
  const [revealed, setRevealed] = useState(false)
  const [doneCount, setDoneCount] = useState(0)
  const [againCount, setAgainCount] = useState(0)

  const current: Card | undefined = queue[0]

  function reveal() {
    if (current && !revealed) setRevealed(true)
  }

  function again() {
    if (!current || !revealed) return
    setQueue((q) => [...q.slice(1), q[0]])
    setAgainCount((n) => n + 1)
    setRevealed(false)
  }

  function gotIt() {
    if (!current || !revealed) return
    setQueue((q) => q.slice(1))
    setDoneCount((n) => n + 1)
    setRevealed(false)
  }

  function restart() {
    setQueue(shuffle(cards))
    setRevealed(false)
    setDoneCount(0)
    setAgainCount(0)
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === ' ') {
        event.preventDefault() // no page scroll / stray button re-clicks
        reveal()
      } else if (event.key === 'Enter') {
        event.preventDefault()
        reveal()
      } else if (revealed && (event.key === '1' || event.key.toLowerCase() === 'a')) {
        again()
      } else if (revealed && (event.key === '2' || event.key.toLowerCase() === 'g')) {
        gotIt()
      } else if (event.key === 'Escape') {
        onExit()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Studying</p>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{deckName}</h1>
        </div>
        <button
          onClick={onExit}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-600 hover:bg-stone-100"
        >
          End session
        </button>
      </div>

      {current ? (
        <>
          <p className="mt-6 text-sm text-stone-500">
            {doneCount} done · {queue.length} to go
          </p>

          <button
            type="button"
            onClick={reveal}
            className="mt-3 block w-full cursor-pointer rounded-2xl border border-stone-200 bg-card p-8 text-left shadow-sm sm:p-12"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Front</p>
            <p className="mt-3 font-display text-2xl leading-snug whitespace-pre-wrap">
              {current.front}
            </p>

            {revealed ? (
              <>
                <hr className="my-6 border-stone-200" />
                <p className="text-xs font-medium uppercase tracking-wide text-stone-400">Back</p>
                <p className="mt-3 text-lg leading-relaxed whitespace-pre-wrap text-stone-800">
                  {current.back}
                </p>
              </>
            ) : (
              <p className="mt-8 text-sm text-stone-400">Click or press Space to reveal</p>
            )}
          </button>

          {revealed && (
            <div className="mt-5 flex justify-center gap-3">
              <button
                onClick={again}
                className="rounded-md border border-stone-300 bg-card px-6 py-2.5 text-sm font-semibold text-stone-700 hover:bg-stone-100"
              >
                Again
              </button>
              <button
                onClick={gotIt}
                className="rounded-md bg-accent px-6 py-2.5 text-sm font-semibold text-white hover:bg-accent-deep"
              >
                Got it
              </button>
            </div>
          )}

          <p className="mt-6 text-center text-xs text-stone-400">
            Space to flip · 1 = again · 2 = got it · Esc to end
          </p>
        </>
      ) : (
        <div className="mt-10 rounded-2xl border border-stone-200 bg-card p-10 text-center shadow-sm">
          <p className="font-display text-2xl font-semibold">Session complete</p>
          <p className="mt-2 text-sm text-stone-500">
            {doneCount} {doneCount === 1 ? 'card' : 'cards'} studied
            {againCount > 0 && <> · {againCount} {againCount === 1 ? 'retry' : 'retries'}</>}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              onClick={restart}
              className="rounded-md bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-deep"
            >
              Study again
            </button>
            <button
              onClick={onExit}
              className="rounded-md border border-stone-300 px-5 py-2 text-sm font-medium text-stone-600 hover:bg-stone-100"
            >
              Back to deck
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
