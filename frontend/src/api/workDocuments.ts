import type {BasisDocument,DocumentKind,DocumentLink,Page} from './types'
export interface WorkDocumentContext {id:string;registration_number:string;version:number;state:string;material:{id:string};department:{id:string;code:string;name:string}}
export interface DocumentOrigin {kind:string;id:string;label:string;accepted_version_id?:string|null;note?:string;letter_id?:string}
export interface WorkDocumentEntry {document:BasisDocument;origins:DocumentOrigin[];extra_links:{id:string;note:string}[]}
export interface WorkDocumentLibrary extends Page<WorkDocumentEntry> {
  context:WorkDocumentContext;can_link:boolean;can_unlink:boolean;can_create:boolean
  document_kinds:{code:DocumentKind;name:string}[]
  detached_links:{id:string;document:DocumentLink;note:string;created_at:string;detached_at:string;detach_reason:string}[]
}
export interface WorkDocumentResponse {event:{id:string};library:WorkDocumentLibrary}
export const documentPath=(id:string)=>`/expertises/${encodeURIComponent(id)}/documents/`
export const originKey=(origin:DocumentOrigin)=>`${origin.kind}:${origin.id}`
