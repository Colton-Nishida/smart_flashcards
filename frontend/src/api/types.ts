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
