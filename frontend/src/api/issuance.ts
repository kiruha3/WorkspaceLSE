import type { DocumentKind, DocumentLink, Reference } from './types'
export type IssueState = 'draft' | 'checked' | 'needs_recheck' | 'issued'
export type IssueItemKind = 'expert_subscription' | 'cover_letter' | 'notification' | 'invoice' | 'other'
export interface IssuePerson { id: string; full_name: string }
export interface IssueRecorded { id: string; actor: IssuePerson | null; created_at: string; reason: string }
export interface PackageItem { id: string; kind: IssueItemKind; expertise_id: string; document: DocumentLink; note: string }
export interface PackageRevision extends IssueRecorded { number: number; materials_description: string; note: string; items: PackageItem[] }
export interface IssueWork { id: string; registration_number: string; category_code: string; state: string; department: { id: string; code: string; name: string }; is_commission: boolean; closure: { id: string; kind: string; ended_on: string | null; result_kind: string | null; document: DocumentLink } | null; required_items: string[] }
export interface PackageReadiness { blockers: { code: string; field: string; message: string; expertise_id?: string }[]; can_check: boolean; can_issue: boolean; check_current: boolean }
export interface PackageCheck extends IssueRecorded { revision_id: string; works: { expertise_id: string; closure_id: string }[]; files: { item_id: string | null; closure_id: string | null; document: DocumentLink }[] }
export interface MaterialIssue extends IssueRecorded { check_id: string; issued_on: string; method: Reference; recipient_name: string; recipient_basis: string; tracking: string; comment: string; evidence: DocumentLink }
export interface IssuePackage { id: string; material: { id: string; title: string }; version: number; state: IssueState; content: PackageRevision; content_history: PackageRevision[]; works: IssueWork[]; readiness: PackageReadiness; checks: PackageCheck[]; issuance: MaterialIssue | null; allowed_actions: string[] }
export interface IssueOptions { methods: Reference[]; item_kinds: { code: IssueItemKind; name: string; document_kinds: DocumentKind[] }[] }
export interface MaterialPackage { material: { id: string; title: string }; package: IssuePackage | null; can_prepare: boolean }
export interface IssueCommandResponse { event: { id: string }; package: IssuePackage }
export interface WorkIssueStatus { status: 'unavailable' | 'not_issued' | 'issued'; issued_on: string | null; package: { id: string; restricted?: true } | null }
export const emptyIssueOptions = (): IssueOptions => ({ methods: [], item_kinds: [] })
export const issueStateLabels: Record<IssueState, string> = { draft: 'Черновик', checked: 'Проверен', needs_recheck: 'Требуется повторная проверка', issued: 'Выдано' }
export const issueItemLabels: Record<IssueItemKind, string> = { expert_subscription: 'Подписка эксперта', cover_letter: 'Сопроводительное', notification: 'Уведомление', invoice: 'Счёт', other: 'Прочее приложение' }
export const issueToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Krasnoyarsk', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
