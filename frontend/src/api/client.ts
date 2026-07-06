// Typed fetch client — the ONLY module that talks to the backend.
// All requests go through `request()`, which sends the session cookie and
// broadcasts UNAUTHORIZED_EVENT on any 401 so the app can route back to login.

import type {
  Card,
  CardInput,
  CardPatch,
  Deck,
  DeckPatch,
  DeckSummary,
  QuizAnswerOut,
  QuizDisputeOut,
  QuizFinishOut,
  QuizQuestionOut,
  Topic,
  TopicPatch,
  TopicSummary,
  User,
} from './types'

/** Fired on `window` whenever any API call comes back 401. */
export const UNAUTHORIZED_EVENT = 'smart-flashcards:unauthorized'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

/** Human-readable message for any error thrown by this module. */
export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Something went wrong.'
}

async function extractDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string' && detail) return detail
    }
  } catch {
    // Non-JSON error body; fall through to a generic message.
  }
  return `Request failed (${response.status}${response.statusText ? ` ${response.statusText}` : ''})`
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { credentials: 'include', ...init })
  } catch {
    throw new ApiError(0, 'Could not reach the server.')
  }
  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    throw new ApiError(response.status, await extractDetail(response))
  }
  if (response.status === 204) return undefined as T
  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

// ---- Auth ----

/** inviteCode is only enforced when the server has INVITE_CODE configured. */
export function register(
  username: string,
  password: string,
  inviteCode = '',
): Promise<User> {
  return request<User>(
    '/auth/register',
    json('POST', { username, password, invite_code: inviteCode }),
  )
}

export function login(username: string, password: string): Promise<User> {
  return request<User>('/auth/login', json('POST', { username, password }))
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' })
}

export function getMe(): Promise<User> {
  return request<User>('/auth/me')
}

// ---- Decks ----

/** Synchronous generation: this call takes 15–60s while Claude writes the cards. */
export function createDeck(file: File, name: string, description: string): Promise<Deck> {
  const form = new FormData()
  form.append('file', file)
  form.append('name', name)
  form.append('description', description)
  return request<Deck>('/decks', { method: 'POST', body: form })
}

export function listDecks(): Promise<DeckSummary[]> {
  return request<DeckSummary[]>('/decks')
}

export function getDeck(deckId: string): Promise<Deck> {
  return request<Deck>(`/decks/${deckId}`)
}

export function updateDeck(deckId: string, patch: DeckPatch): Promise<Deck> {
  return request<Deck>(`/decks/${deckId}`, json('PATCH', patch))
}

export function deleteDeck(deckId: string): Promise<void> {
  return request<void>(`/decks/${deckId}`, { method: 'DELETE' })
}

// ---- Cards ----

export function createCard(deckId: string, card: CardInput): Promise<Card> {
  return request<Card>(`/decks/${deckId}/cards`, json('POST', card))
}

export function updateCard(deckId: string, cardId: string, patch: CardPatch): Promise<Card> {
  return request<Card>(`/decks/${deckId}/cards/${cardId}`, json('PATCH', patch))
}

export function deleteCard(deckId: string, cardId: string): Promise<void> {
  return request<void>(`/decks/${deckId}/cards/${cardId}`, { method: 'DELETE' })
}

// ---- Topics ----

/** Synchronous extraction: takes 15–60s while Claude distills the PDF into notes. */
export function createTopic(
  file: File,
  name: string,
  description: string,
  instructions = '',
): Promise<Topic> {
  const form = new FormData()
  form.append('file', file)
  form.append('name', name)
  form.append('description', description)
  form.append('instructions', instructions)
  return request<Topic>('/topics', { method: 'POST', body: form })
}

export function listTopics(): Promise<TopicSummary[]> {
  return request<TopicSummary[]>('/topics')
}

export function getTopic(topicId: string): Promise<Topic> {
  return request<Topic>(`/topics/${topicId}`)
}

export function updateTopic(topicId: string, patch: TopicPatch): Promise<Topic> {
  return request<Topic>(`/topics/${topicId}`, json('PATCH', patch))
}

export function deleteTopic(topicId: string): Promise<void> {
  return request<void>(`/topics/${topicId}`, { method: 'DELETE' })
}

// ---- Quiz sessions (each call is one Claude turn: expect a few seconds) ----

export function startQuiz(
  topicId: string,
  numQuestions: number,
  replace = false,
): Promise<QuizQuestionOut> {
  return request<QuizQuestionOut>(
    `/topics/${topicId}/quiz/start`,
    json('POST', { num_questions: numQuestions, replace }),
  )
}

/** session/question binding lets the server reject writes from a stale tab. */
export interface QuizBinding {
  session_id: string
  question_number: number
}

export function answerQuiz(
  topicId: string,
  answer: string,
  binding: QuizBinding,
): Promise<QuizAnswerOut> {
  return request<QuizAnswerOut>(
    `/topics/${topicId}/quiz/answer`,
    json('POST', { answer, ...binding }),
  )
}

export function nextQuizQuestion(topicId: string): Promise<QuizQuestionOut> {
  return request<QuizQuestionOut>(`/topics/${topicId}/quiz/next`, { method: 'POST' })
}

export function disputeQuiz(
  topicId: string,
  message: string,
  binding: QuizBinding,
): Promise<QuizDisputeOut> {
  return request<QuizDisputeOut>(
    `/topics/${topicId}/quiz/dispute`,
    json('POST', { message, ...binding }),
  )
}

export function finishQuiz(topicId: string): Promise<QuizFinishOut> {
  return request<QuizFinishOut>(`/topics/${topicId}/quiz/finish`, { method: 'POST' })
}

export function abandonQuiz(topicId: string): Promise<void> {
  return request<void>(`/topics/${topicId}/quiz`, { method: 'DELETE' })
}
