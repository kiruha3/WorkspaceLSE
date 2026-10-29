<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
import {computed,ref} from 'vue'
import {ApiError,useApi} from '../../api/client'
import {newCommandKey} from '../../api/commandKey'
import type {BasisDocument,FileVersion} from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
const props=defineProps<{document:BasisDocument;authorized:boolean}>()
const emit=defineEmits<{saved:[];changed:[]}>()
const api=useApi(),file=ref<File|null>(null),fileInput=ref<HTMLInputElement|null>(null),busy=ref(false),error=ref<unknown>(null),conflict=ref(false),current=ref<BasisDocument|null>(null),uncertain=ref(false)
const attempt=ref<{key:string;version:number;file:File}|null>(null),dirty=computed(()=>Boolean(file.value))
function choose(event:Event){file.value=(event.target as HTMLInputElement).files?.[0]??null;attempt.value=null;error.value=null;conflict.value=false;current.value=null;emit('changed')}
async function refresh(){busy.value=true;error.value=null;try{current.value=await api.request<BasisDocument>(`/documents/${props.document.id}/`)}catch(cause){error.value=cause}finally{busy.value=false}}
function accept(){if(!current.value||!file.value)return;attempt.value={key:newCommandKey(),version:current.value.version,file:file.value};conflict.value=false;current.value=null;error.value=null}
function reset(){if(busy.value||uncertain.value)return;file.value=null;attempt.value=null;error.value=null;conflict.value=false;current.value=null;if(fileInput.value)fileInput.value.value='';emit('changed')}
async function save(){
  if(busy.value||!props.authorized||!file.value||conflict.value)return
  if(!attempt.value)attempt.value={key:newCommandKey(),version:props.document.version,file:file.value}
  busy.value=true;error.value=null
  try{
    const body=new FormData();body.append('expected_version',String(attempt.value.version));body.append('file',attempt.value.file)
    if(attempt.value.file.webkitRelativePath)body.append('relative_path',attempt.value.file.webkitRelativePath)
    await api.request<FileVersion>(`/documents/${props.document.id}/versions/`,{method:'POST',body,headers:{'Idempotency-Key':attempt.value.key}})
    file.value=null;attempt.value=null;if(fileInput.value)fileInput.value.value='';emit('saved');emit('changed')
  }catch(cause){error.value=cause;conflict.value=cause instanceof ApiError&&cause.status===409;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'}finally{busy.value=false}
}
defineExpose({dirty,busy})
</script>
<template>
  <form data-version-upload class="inset-form form-grid" @submit.prevent="save">
    <h4>Добавить сохранённую версию <HelpTip label="Версии документа">Новая версия не заменяет файл, принятый при окончании, регистрации письма или выдаче. Право загрузки проверяется отдельно от права просмотра.</HelpTip></h4>
    <label>Новый файл<input ref="fileInput" data-version-file type="file" :disabled="busy||!authorized||Boolean(attempt)" @change="choose"/></label><p v-if="file" class="muted">Выбран: {{file.name}}</p>
    <ApiMessage :error="error"/>
    <section v-if="conflict" class="message"><p>Документ изменён. Выбранный файл сохранён; требуется сверка версии.</p><button data-refresh-file-version type="button" :disabled="busy" @click="refresh">Загрузить текущую версию документа</button><template v-if="current"><p>Текущая версия документа {{current.version}} · {{current.title}}</p><button data-accept-file-version type="button" :disabled="busy" @click="accept">Принять версию {{current.version}} документа</button></template></section>
    <button type="submit" :disabled="busy||!file||conflict||!authorized">{{busy?'Загрузка…':'Сохранить новую версию'}}</button>
    <button v-if="attempt&&!busy&&!uncertain" data-reset-version-file type="button" @click="reset">Отменить эту попытку и выбрать другой файл</button>
  </form>
</template>
