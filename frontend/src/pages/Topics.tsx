// Topics + dynamic quiz: topic list with mastery bars on the left,
// the quiz chat agent for the selected topic on the right.

import { useCallback, useEffect, useState } from 'react'
import { deleteTopic, errorMessage, listTopics } from '../api'
import type { Topic, TopicSummary } from '../api'
import MasteryBar from '../components/MasteryBar'
import NewTopicForm from '../components/NewTopicForm'
import QuizPanel from '../components/QuizPanel'

export default function Topics() {
  const [topics, setTopics] = useState<TopicSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showNewForm, setShowNewForm] = useState(false)

  const refresh = useCallback(() => {
    listTopics()
      .then((result) => {
        setTopics(result)
        setError(null)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  function handleCreated(topic: Topic) {
    setShowNewForm(false)
    setSelectedId(topic.id)
    refresh()
  }

  async function handleDelete(topicId: string, name: string) {
    if (!window.confirm(`Delete the topic “${name}” and all its progress?`)) return
    try {
      await deleteTopic(topicId)
      if (selectedId === topicId) setSelectedId(null)
      refresh()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside>
        <div className="flex items-center justify-between">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Topics</h1>
          <button
            onClick={() => setShowNewForm((v) => !v)}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-deep"
          >
            {showNewForm ? 'Close' : 'New topic'}
          </button>
        </div>

        {showNewForm && (
          <div className="mt-4">
            <NewTopicForm onCreated={handleCreated} onCancel={() => setShowNewForm(false)} />
          </div>
        )}

        {error && <p className="mt-4 text-sm text-red-700">{error}</p>}

        {!error && topics === null && (
          <p className="mt-4 text-sm text-stone-400">Loading topics…</p>
        )}

        {topics !== null && topics.length === 0 && !showNewForm && (
          <div className="mt-6 rounded-xl border border-dashed border-stone-300 p-6 text-center">
            <p className="font-display">No topics yet</p>
            <p className="mt-1 text-sm text-stone-500">
              Upload a PDF and a tutor will quiz you on it, tracking how well you know it.
            </p>
          </div>
        )}

        {topics !== null && topics.length > 0 && (
          <ul className="mt-4 space-y-2">
            {topics.map((topic) => (
              <li key={topic.id} className="group relative">
                <button
                  onClick={() => setSelectedId(topic.id)}
                  className={`w-full rounded-xl border p-4 text-left transition-colors ${
                    selectedId === topic.id
                      ? 'border-accent bg-card shadow-sm'
                      : 'border-stone-200 bg-card hover:border-accent/50'
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2 pr-5">
                    <span className="truncate font-display text-base font-medium">
                      {topic.name}
                    </span>
                    {topic.has_active_session && (
                      <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                        in progress
                      </span>
                    )}
                  </div>
                  <div className="mt-2.5">
                    <MasteryBar score={topic.mastery_score} />
                  </div>
                  <p className="mt-1.5 text-xs text-stone-400">
                    {topic.session_count === 0
                      ? 'Never quizzed'
                      : `${topic.session_count} session${topic.session_count === 1 ? '' : 's'}`}
                  </p>
                </button>
                <button
                  onClick={() => void handleDelete(topic.id, topic.name)}
                  aria-label={`Delete ${topic.name}`}
                  title="Delete topic"
                  className="absolute right-3 top-3 hidden text-stone-300 hover:text-red-600 group-hover:block"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section>
        {selectedId ? (
          <QuizPanel topicId={selectedId} onTopicMutated={refresh} />
        ) : (
          <div className="flex h-[calc(100vh-10.5rem)] min-h-[28rem] items-center justify-center rounded-xl border border-dashed border-stone-300 text-center">
            <div>
              <p className="font-display text-lg">Pick a topic to get quizzed</p>
              <p className="mt-1 text-sm text-stone-500">
                The tutor asks questions from your notes, grades your answers, and tracks your
                mastery over time.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
