export type SortValue = string | number | boolean | Date | null | undefined | readonly SortValue[]
export interface SortColumn<T = unknown> { key: string; label: string; value?: (row: T) => SortValue; sortable?: boolean }
const collator = new Intl.Collator('ru', {numeric:true, sensitivity:'base'})
const blank = (value: SortValue) => value === null || value === undefined || value === ''
function compare(a: SortValue, b: SortValue, direction=1): number {
  if (Array.isArray(a) || Array.isArray(b)) {
    const left=Array.isArray(a)?a:[a], right=Array.isArray(b)?b:[b]
    for(let i=0;i<Math.max(left.length,right.length);i++){const result=compare(left[i],right[i],direction);if(result)return result}
    return 0
  }
  if(blank(a)||blank(b))return blank(a)?blank(b)?0:1:-1
  if(a instanceof Date || b instanceof Date)return direction*(Number(a)-Number(b))
  if(typeof a==='number'&&typeof b==='number')return direction*(a-b)
  return direction*collator.compare(String(a),String(b))
}
export function nextOrdering(current: string, key: string) { return current===key?'-'+key:current==='-'+key?'':key }
export function orderingParams(ordering: string): Record<string,string> { return ordering ? {ordering} : {} }
export function sortRows<T>(rows: readonly T[], columns: readonly SortColumn<T>[], ordering: string, pinFirst?: (row:T)=>boolean): T[] {
  const column=columns.find(item=>item.key===ordering.replace(/^-/,''))
  if(!ordering||!column||column.sortable===false)return [...rows]
  const value=column.value??((row:T)=>(row as Record<string,SortValue>)[column.key])
  const direction=ordering.startsWith('-')?-1:1
  return rows.map((row,index)=>({row,index})).sort((a,b)=>{
    if(pinFirst&&pinFirst(a.row)!==pinFirst(b.row))return pinFirst(a.row)?-1:1
    const av=value(a.row),bv=value(b.row)
    const result=compare(av,bv,direction)
    return result||a.index-b.index
  }).map(item=>item.row)
}
