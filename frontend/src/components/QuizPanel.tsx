// The right-hand "chat agent" panel: runs an adaptive Q/A session against one topic.
// Session state lives on the server (topic.active_session); this component mirrors it
// as a chat transcript and drives it via the /quiz endpoints.

import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import {
  abandonQuiz,
  answerQuiz,
  disputeQuiz,
  errorMessage,
  finishQuiz,
  getTopic,
  nextQuizQuestion,
  startQuiz,
} from '../api'
import type { ActiveSession, Grade, Topic } from '../api'
import { formatDate } from '../lib/format'

type Phase = 'setup' | 'answering' | 'graded' | 'done'

interface ChatMsg {
  id: number
  role: 'agent' | 'user'
  text: string
  grade?: Grade
  heading?: string
}

const GRADE_STYLES: Record<Grade, string> = {
  good: 'bg-green-100 text-green-800',
  ok: 'bg-amber-100 text-amber-800',
  bad: 'bg-red-100 text-red-800',
}

const GRADE_LABELS: Record<Grade, string> = { good: 'Good', ok: 'Ok', bad: 'Bad' }

let nextMsgId = 1
function msg(partial: Omit<ChatMsg, 'id'>): ChatMsg {
  return { id: nextMsgId++, ...partial }
}

/** Rebuild the chat transcript from a server-side session (resume after reload). */
function transcriptOf(session: ActiveSession): ChatMsg[] {
  const messages: ChatMsg[] = []
  session.questions.forEach((q, i) => {
    messages.push(
      msg({
        role: 'agent',
        text: q.question,
        heading: `Question ${i + 1} of ${session.total_questions}`,
      }),
    )
    if (q.answer !== null) {
      messages.push(msg({ role: 'user', text: q.answer }))
      if (q.grade !== null) {
        messages.push(msg({ role: 'agent', text: q.feedback ?? '', grade: q.grade }))
      }
    }
    for (const d of q.disputes) {
      messages.push(msg({ role: 'user', text: d.message }))
      messages.push(
        msg({
          role: 'agent',
          text: d.reply,
          heading: d.verdict === 'revised' ? 'Grade revised' : 'Grade upheld',
        }),
      )
    }
  })
  return messages
}

interface QuizPanelProps {
  topicId: string
  /** Fired whenever score / active-session / notes state changed server-side. */
  onTopicMutated: () => void
}

export default function QuizPanel({ topicId, onTopicMutated }: QuizPanelProps) {
  const [topic, setTopic] = useState<Topic | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [tab, setTab] = useState<'quiz' | 'notes'>('quiz')

  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [phase, setPhase] = useState<Phase>('setup')
  const [disputing, setDisputing] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [numQuestions, setNumQuestions] = useState('5')
  const [isLast, setIsLast] = useState(false)
  const [answeredCount, setAnsweredCount] = useState(0)
  // Server-side binding: lets the backend reject writes from a stale tab.
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [questionNumber, setQuestionNumber] = useState(0)

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Load the topic (and resume any in-flight session) whenever the selection changes.
  useEffect(() => {
    let cancelled = false
    setTopic(null)
    setLoadError(null)
    setMessages([])
    setPhase('setup')
    setDisputing(false)
    setBusy(null)
    setError(null)
    setInput('')
    setTab('quiz')
    getTopic(topicId)
      .then((t) => {
        if (cancelled) return
        setTopic(t)
        const session = t.active_session
        if (session && session.questions.length > 0) {
          setMessages(transcriptOf(session))
          setPhase(session.status === 'awaiting_answer' ? 'answering' : 'graded')
          setIsLast(session.questions.length >= session.total_questions)
          setAnsweredCount(session.questions.filter((q) => q.answer !== null).length)
          setSessionId(session.id)
          setQuestionNumber(session.questions.length)
        }
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [topicId])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy])

  useEffect(() => {
    if ((phase === 'answering' || disputing) && !busy) inputRef.current?.focus()
  }, [phase, disputing, busy])

  function push(...newMessages: ChatMsg[]) {
    setMessages((prev) => [...prev, ...newMessages])
  }

  async function refreshTopic() {
    try {
      setTopic(await getTopic(topicId))
    } catch {
      // Non-fatal: the chat still works; notes tab may be stale.
    }
  }

  async function handleStart(event: FormEvent) {
    event.preventDefault()
    const n = Number(numQuestions)
    if (!Number.isInteger(n) || n < 1 || n > 25) {
      setError('Pick between 1 and 25 questions.')
      return
    }
    setError(null)
    setBusy('Preparing your first question…')
    try {
      const q = await startQuiz(topicId, n)
      setMessages([
        msg({
          role: 'agent',
          text: q.question,
          heading: `Question ${q.question_number} of ${q.total_questions}`,
        }),
      ])
      setPhase('answering')
      setIsLast(q.question_number >= q.total_questions)
      setAnsweredCount(0)
      setSessionId(q.session_id)
      setQuestionNumber(q.question_number)
      onTopicMutated()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleAnswer(text: string) {
    if (!sessionId) return
    push(msg({ role: 'user', text }))
    setInput('')
    setBusy('Grading your answer…')
    setError(null)
    try {
      const graded = await answerQuiz(topicId, text, {
        session_id: sessionId,
        question_number: questionNumber,
      })
      push(msg({ role: 'agent', text: graded.feedback, grade: graded.grade }))
      setPhase('graded')
      setIsLast(graded.is_last)
      setAnsweredCount((c) => c + 1)
    } catch (err) {
      setMessages((prev) => prev.slice(0, -1))
      setInput(text)
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleDispute(text: string) {
    if (!sessionId) return
    push(msg({ role: 'user', text }))
    setInput('')
    setDisputing(false)
    setBusy('Reconsidering…')
    setError(null)
    try {
      const ruling = await disputeQuiz(topicId, text, {
        session_id: sessionId,
        question_number: questionNumber,
      })
      const heading =
        ruling.verdict === 'revised'
          ? `Grade revised to ${GRADE_LABELS[ruling.grade]}`
          : 'Grade upheld'
      const suffix = ruling.notes_updated ? '\n\n(I also corrected the study notes.)' : ''
      push(msg({ role: 'agent', text: ruling.reply + suffix, heading }))
      if (ruling.notes_updated) {
        await refreshTopic()
        onTopicMutated()
      }
    } catch (err) {
      setMessages((prev) => prev.slice(0, -1))
      setInput(text)
      setDisputing(true)
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleNext() {
    setBusy('Thinking of the next question…')
    setError(null)
    setDisputing(false)
    try {
      const q = await nextQuizQuestion(topicId)
      push(
        msg({
          role: 'agent',
          text: q.question,
          heading: `Question ${q.question_number} of ${q.total_questions}`,
        }),
      )
      setPhase('answering')
      setIsLast(q.question_number >= q.total_questions)
      setQuestionNumber(q.question_number)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleFinish() {
    setBusy('Scoring the session…')
    setError(null)
    setDisputing(false)
    try {
      const result = await finishQuiz(topicId)
      const delta = result.score_after - result.score_before
      const deltaText = delta >= 0 ? `+${delta}` : `${delta}`
      push(
        msg({
          role: 'agent',
          heading: `Session complete — mastery ${result.score_before} → ${result.score_after} (${deltaText})`,
          text: `${result.summary}\n\nGood: ${result.grades.good} · Ok: ${result.grades.ok} · Bad: ${result.grades.bad}`,
        }),
      )
      setPhase('done')
      await refreshTopic()
      onTopicMutated()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleAbandon() {
    setError(null)
    try {
      await abandonQuiz(topicId)
      setMessages([])
      setPhase('setup')
      setDisputing(false)
      setInput('')
      await refreshTopic()
      onTopicMutated()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    if (disputing) void handleDispute(text)
    else if (phase === 'answering') void handleAnswer(text)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  if (loadError) {
    return (
      <div className="rounded-xl border border-stone-200 bg-card p-6 text-sm text-red-700 shadow-sm">
        {loadError}
      </div>
    )
  }

  if (topic === null) {
    return (
      <div className="rounded-xl border border-stone-200 bg-card p-6 text-sm text-stone-400 shadow-sm">
        Loading topic…
      </div>
    )
  }

  const sessionActive = phase === 'answering' || phase === 'graded'
  const inputEnabled = !busy && (disputing || phase === 'answering')

  return (
    <div className="flex h-[calc(100vh-10.5rem)] min-h-[28rem] flex-col rounded-xl border border-stone-200 bg-card shadow-sm">
      <div className="flex items-center gap-1 border-b border-stone-200 px-4 pt-3">
        <h2 className="mr-auto truncate pb-3 font-display text-lg font-semibold">{topic.name}</h2>
        <PanelTab active={tab === 'quiz'} onClick={() => setTab('quiz')}>
          Quiz
        </PanelTab>
        <PanelTab active={tab === 'notes'} onClick={() => setTab('notes')}>
          Notes & progress
        </PanelTab>
      </div>

      {tab === 'notes' ? (
        <NotesTab topic={topic} />
      ) : (
        <>
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {phase === 'setup' && (
              <SetupCard
                topic={topic}
                numQuestions={numQuestions}
                onNumChange={setNumQuestions}
                onStart={handleStart}
                disabled={Boolean(busy)}
              />
            )}

            {messages.map((m) => (
              <Bubble key={m.id} message={m} />
            ))}

            {busy && (
              <div className="flex items-center gap-2 text-sm text-stone-400">
                <span
                  aria-hidden
                  className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-stone-300 border-t-accent"
                />
                {busy}
              </div>
            )}

            {phase === 'graded' && !busy && !disputing && (
              <div className="flex flex-wrap gap-2">
                {isLast ? (
                  <ActionButton primary onClick={handleFinish}>
                    Finish & get my score
                  </ActionButton>
                ) : (
                  <ActionButton primary onClick={handleNext}>
                    Next question
                  </ActionButton>
                )}
                <ActionButton onClick={() => setDisputing(true)}>Dispute this grade</ActionButton>
                {!isLast && answeredCount > 0 && (
                  <ActionButton onClick={handleFinish}>End early & score</ActionButton>
                )}
              </div>
            )}

            {disputing && !busy && (
              <p className="text-xs text-stone-500">
                Tell the tutor what it got wrong — it can revise the grade and fix the notes.{' '}
                <button
                  onClick={() => setDisputing(false)}
                  className="font-medium text-accent hover:underline"
                >
                  Never mind
                </button>
              </p>
            )}

            {phase === 'done' && !busy && (
              <ActionButton
                primary
                onClick={() => {
                  // Clear the finished transcript so the setup card is actually visible
                  // (it mounts at the top of a container scrolled to the bottom).
                  setMessages([])
                  setPhase('setup')
                }}
              >
                Start another session
              </ActionButton>
            )}
          </div>

          {error && <p className="px-4 pb-2 text-sm text-red-700">{error}</p>}

          <form onSubmit={handleSubmit} className="border-t border-stone-200 p-3">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
                maxLength={5000}
                disabled={!inputEnabled}
                placeholder={
                  disputing
                    ? 'What did the tutor get wrong?'
                    : phase === 'answering'
                      ? 'Type your answer… (Enter to send)'
                      : sessionActive
                        ? 'Choose an action above…'
                        : 'Start a session to begin'
                }
                className="flex-1 resize-none rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:bg-stone-50 disabled:text-stone-400"
              />
              <button
                type="submit"
                disabled={!inputEnabled || !input.trim()}
                className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-50"
              >
                Send
              </button>
            </div>
            {sessionActive && (
              <button
                type="button"
                onClick={answeredCount > 0 ? handleFinish : handleAbandon}
                disabled={Boolean(busy)}
                className="mt-2 text-xs text-stone-400 hover:text-stone-600"
              >
                {answeredCount > 0 ? 'End session now (scores what you answered)' : 'Cancel session'}
              </button>
            )}
          </form>
        </>
      )}
    </div>
  )
}

function PanelTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-t-md border-b-2 px-3 pb-3 pt-1 text-sm font-medium ${
        active
          ? 'border-accent text-accent'
          : 'border-transparent text-stone-500 hover:text-stone-700'
      }`}
    >
      {children}
    </button>
  )
}

function SetupCard({
  topic,
  numQuestions,
  onNumChange,
  onStart,
  disabled,
}: {
  topic: Topic
  numQuestions: string
  onNumChange: (v: string) => void
  onStart: (e: FormEvent) => void
  disabled: boolean
}) {
  return (
    <div className="rounded-lg border border-stone-200 bg-paper/60 p-4">
      <p className="text-sm text-stone-600">
        {topic.sessions.length === 0
          ? "I've read your notes — ready when you are. How many questions this round?"
          : `Welcome back. Current mastery: ${topic.mastery_score}/100. How many questions this round?`}
      </p>
      <form onSubmit={onStart} className="mt-3 flex items-center gap-2">
        <input
          type="number"
          min={1}
          max={25}
          value={numQuestions}
          onChange={(e) => onNumChange(e.target.value)}
          disabled={disabled}
          className="w-20 rounded-md border border-stone-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-50"
        >
          Start quiz
        </button>
      </form>
    </div>
  )
}

function Bubble({ message }: { message: ChatMsg }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 text-sm text-paper">
          {message.text}
        </div>
      </div>
    )
  }
  return (
    <div className="flex">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-sm">
        {message.grade && (
          <span
            className={`mb-1.5 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${GRADE_STYLES[message.grade]}`}
          >
            {GRADE_LABELS[message.grade]}
          </span>
        )}
        {message.heading && (
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-400">
            {message.heading}
          </p>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
      </div>
    </div>
  )
}

function ActionButton({
  primary,
  onClick,
  children,
}: {
  primary?: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      onClick={onClick}
      className={
        primary
          ? 'rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-deep'
          : 'rounded-md border border-stone-300 px-4 py-1.5 text-sm font-medium text-stone-600 hover:bg-stone-100'
      }
    >
      {children}
    </button>
  )
}

function NotesTab({ topic }: { topic: Topic }) {
  return (
    <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
      {topic.instructions && (
        <section className="rounded-lg border border-stone-200 bg-paper/60 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-400">
            Your instructions to the tutor
          </h3>
          <p className="mt-2 whitespace-pre-wrap text-sm text-stone-700">{topic.instructions}</p>
        </section>
      )}

      <section className="rounded-lg border border-stone-200 bg-paper/60 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-400">
          Why this score — the tutor's memory
        </h3>
        <p className="mt-2 whitespace-pre-wrap text-sm text-stone-700">
          {topic.mastery_notes || 'No sessions yet — finish a quiz and the tutor will record what you know.'}
        </p>
      </section>

      {topic.sessions.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-400">
            Past sessions
          </h3>
          <ul className="mt-2 space-y-2">
            {[...topic.sessions].reverse().map((s) => (
              <li key={s.id} className="rounded-lg border border-stone-200 bg-white p-3 text-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">
                    {s.score_before} → {s.score_after}
                  </span>
                  <span className="text-xs text-stone-400">{formatDate(s.completed_at)}</span>
                </div>
                <p className="mt-1 text-xs text-stone-500">
                  {s.questions_answered}/{s.total_questions} answered · Good {s.grades.good} · Ok{' '}
                  {s.grades.ok} · Bad {s.grades.bad}
                </p>
                <p className="mt-1.5 text-stone-600">{s.summary}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-stone-400">
          Study notes (extracted from{' '}
          <a
            href={`/api/topics/${topic.id}/pdf`}
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
            title="Open the original PDF"
          >
            {topic.source_filename}
          </a>
          )
        </h3>
        <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-stone-200 bg-white p-4 font-sans text-sm text-stone-700">
          {topic.notes_md}
        </pre>
      </section>
    </div>
  )
}
