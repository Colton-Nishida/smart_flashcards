// TS mirrors of the backend Pydantic schemas (docs/DESIGN.md, "Data model").

export interface User {
  id: string
  username: string
  created_at: string
}

export interface Card {
  id: string
  front: string
  back: string
  tags: string[]
}

export interface Deck {
  id: string
  name: string
  description: string
  created_at: string
  source_filename: string
  cards: Card[]
}

/** What `GET /api/decks` returns per deck: metadata plus a card count, no cards. */
export interface DeckSummary {
  id: string
  name: string
  description: string
  created_at: string
  card_count: number
}

export interface CardInput {
  front: string
  back: string
  tags?: string[]
}

export interface DeckPatch {
  name?: string
  description?: string
}

export interface CardPatch {
  front?: string
  back?: string
  tags?: string[]
}

// ---- Topics & quiz ----

export type Grade = 'good' | 'ok' | 'bad'

export interface QuizDisputeRecord {
  message: string
  verdict: 'upheld' | 'revised'
  reply: string
}

export interface SessionQuestion {
  question: string
  answer: string | null
  grade: Grade | null
  feedback: string | null
  disputes: QuizDisputeRecord[]
}

export interface ActiveSession {
  id: string
  started_at: string
  total_questions: number
  status: 'awaiting_answer' | 'awaiting_next'
  questions: SessionQuestion[]
}

export interface SessionRecord {
  id: string
  started_at: string
  completed_at: string
  total_questions: number
  questions_answered: number
  grades: Record<Grade, number>
  score_before: number
  score_after: number
  summary: string
}

export interface Topic {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  source_filename: string
  notes_md: string
  mastery_score: number
  mastery_notes: string
  sessions: SessionRecord[]
  active_session: ActiveSession | null
}

export interface TopicSummary {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  source_filename: string
  mastery_score: number
  session_count: number
  has_active_session: boolean
}

export interface TopicPatch {
  name?: string
  description?: string
}

export interface QuizQuestionOut {
  session_id: string
  question: string
  question_number: number
  total_questions: number
}

export interface QuizAnswerOut {
  grade: Grade
  feedback: string
  question_number: number
  is_last: boolean
}

export interface QuizDisputeOut {
  verdict: 'upheld' | 'revised'
  grade: Grade
  reply: string
  notes_updated: boolean
}

export interface QuizFinishOut {
  score_before: number
  score_after: number
  mastery_notes: string
  summary: string
  grades: Record<Grade, number>
}
