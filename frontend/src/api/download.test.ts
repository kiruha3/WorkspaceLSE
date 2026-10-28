import { expect,it } from 'vitest'
import { ApiClient } from './client'

it('downloads only a successful Excel response with same-origin credentials',async()=>{
  let options:RequestInit|undefined
  const client=new ApiClient(async(_,init)=>{options=init;return new Response(new Uint8Array([80,75,3,4]),{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Content-Disposition':'attachment; filename="15-1.xlsx"'}})})
  expect(typeof client.download).toBe('function')
  const file=await client.download('/reports/form151/xlsx/')
  expect(new Headers(options?.headers).get('Accept')).toBe('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/json')
  expect(options?.credentials).toBe('same-origin');expect(file.filename).toBe('15-1.xlsx');expect(file.blob.size).toBe(4)
})
it('propagates a stale report error instead of returning a JSON blob',async()=>{
  const client=new ApiClient(async()=>new Response(JSON.stringify({code:'command_conflict',message:'Пересчитайте отчёт'}),{status:409,headers:{'Content-Type':'application/json'}}))
  expect(typeof client.download).toBe('function')
  await expect(client.download('/reports/form151/xlsx/')).rejects.toMatchObject({status:409,code:'command_conflict',message:'Пересчитайте отчёт'})
})
