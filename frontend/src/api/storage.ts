import type {CurrentUser} from './types'
import {institutionPermission} from './reportPlans'

export const storagePermission='documents.storage.manage'
export const settingsActions=[storagePermission,'imports.source.manage','access.roles.view','access.roles.manage','users.view','users.create','users.reset_password','users.deactivate','access.roles.assign','access.effective.view','references.view','references.manage','employees.view']
export const canManageStorage=(user:CurrentUser|null)=>institutionPermission(user,storagePermission)&&Boolean(user?.supported_modules?.includes('document_storage_settings'))
export interface StorageRoot {year:number;path:string;version:number;read_only:true}
export interface SavedStorageRoot extends StorageRoot {event:{id:string}}
export type StorageCheckStatus='available'|'unavailable'|'timeout'
export function validStorageRoot(value:StorageRoot):boolean {
 return Boolean(value)&&Number.isInteger(value.year)&&value.year>=1900&&value.year<=9999&&typeof value.path==='string'&&Number.isInteger(value.version)&&value.version>=0&&value.read_only===true
}
