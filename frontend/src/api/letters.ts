import type { DocumentLink, Reference } from './types'

export type Direction = 'incoming' | 'outgoing'
export type ReplyCompleteness = 'partial' | 'additional' | 'final'
export type LetterState = 'draft' | 'registered' | 'partially_sent' | 'sent'
export interface Person { id: string; full_name: string }
export interface Recorded { id: string; actor: Person; created_at: string; reason: string }
export interface Recipient { id: string; name: string; address: string; email: string }
export interface WorkOption { id: string; registration_number: string; material: { id: string; title: string } }
export interface MaterialOption { id: string; title: string }
export interface LetterContent extends Recorded {
  number: number; kind: Reference | null; subject: string; body: string; sender_name: string; external_number: string
  external_on: string | null; document_on: string | null; received_on: string | null; note: string
  material: MaterialOption | null; expertises: { id: string; registration_number: string }[]
  parent: { id: string; subject: string; direction: Direction; registration_number: string | null } | { id: string; restricted: true } | null
  reply_completeness: ReplyCompleteness | null; recipients: Recipient[]
}
export interface LetterSummary { id: string; direction: Direction; subject: string; registration_number: string | null; reply_completeness: ReplyCompleteness | null; state: LetterState }
export interface LetterRegistration extends Recorded { journal: Reference; registration_number: string; registered_on: string; year: number; revision_id: string; files: DocumentLink[] }
export interface Dispatch extends Recorded { sent_on: string; channel: Reference; recipient_ids: string[]; tracking: string; comment: string; evidence: DocumentLink; files: DocumentLink[] }
export interface Delivery extends Recorded { dispatch_id: string; recipient_id: string; delivered_on: string; evidence: DocumentLink }
export interface ControlEvent extends Recorded { kind: 'opened' | 'deadline_changed' | 'closed' | 'reopened'; actual_on: string; due_on: string | null; due_basis: string; closure_reason: Reference | null; reply: { id: string; subject: string } | { id: string; restricted: true } | null; comment: string }
export interface LetterControl { id: string; opened_on: string; due_on: string | null; due_basis: string; status: 'open' | 'closed'; response_progress: 'none' | 'registered' | 'partial' | 'final'; overdue: boolean; events: ControlEvent[] }
export interface Letter {
  id: string; direction: Direction; department: Reference | null; responsible: Person | null; version: number; created_at: string
  state: LetterState; received_on: string | null; content: LetterContent; content_history: LetterContent[]
  attachments: (Recorded & { document: DocumentLink })[]; registration: LetterRegistration | null; dispatches: Dispatch[]; deliveries: Delivery[]
  receipts: (Recorded & { received_on: string; evidence: DocumentLink })[]
  assignment_history: (Recorded & { previous: Person | null; responsible: Person })[]; replies: LetterSummary[]
  control: LetterControl | null; allowed_actions: string[]
}
export interface LetterOptions { kinds: Reference[]; journals: (Reference & { direction: Direction; department_id: string | null })[]; channels: Reference[]; closure_reasons: (Reference & { rule: 'reply_sent' | 'reply_received' | 'withdrawn' | 'not_required' | 'other' })[]; departments: Reference[]; employees: Person[] }
export interface LetterCommandResponse { event: { id: string }; letter: Letter }
export const emptyLetterOptions = (): LetterOptions => ({ kinds: [], journals: [], channels: [], closure_reasons: [], departments: [], employees: [] })
export const letterStateLabels: Record<LetterState, string> = { draft: 'Черновик', registered: 'Зарегистрировано', partially_sent: 'Отправлено части адресатов', sent: 'Отправлено всем адресатам' }
export const replyLabels = { partial: 'Частичный', additional: 'Дополнительный', final: 'Завершающий' }
export const institutionToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Krasnoyarsk', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
