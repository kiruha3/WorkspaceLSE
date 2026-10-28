import { computed,onBeforeUnmount,ref } from 'vue'
import { ApiError,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
export interface CommandPacket { path: string; method: 'POST' | 'PATCH'; body: unknown }
/** Retain the exact request after an ambiguous reply; fresh requests require an explicit reset. */
export function useCommandAttempt<T>(prepare:()=>Promise<CommandPacket>|CommandPacket,saved:(value:T)=>void) {
 const api=useApi(),busy=ref(false),uncertain=ref(false),error=ref<unknown>(null)
 let active=true,attempt:(CommandPacket&{key:string})|null=null
 const conflict=computed(()=>error.value instanceof ApiError&&error.value.status===409)
 function reset(){if(!busy.value&&!uncertain.value){attempt=null;error.value=null}}
 async function submit(){
  if(busy.value)return
  busy.value=true;error.value=null
  try{
   if(!attempt){const packet=await prepare();if(!active)return;attempt={...packet,body:JSON.parse(JSON.stringify(packet.body)),key:newCommandKey()}}
   const value=await api.request<T>(attempt.path,{method:attempt.method,body:attempt.body,headers:{'Idempotency-Key':attempt.key}})
   if(active){attempt=null;uncertain.value=false;saved(value)}
  }catch(cause){if(active){error.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'}}
  finally{if(active)busy.value=false}
 }
 onBeforeUnmount(()=>{active=false})
 return {busy,uncertain,error,conflict,reset,submit}
}
