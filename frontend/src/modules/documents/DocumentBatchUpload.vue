<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
import {computed,nextTick,ref,shallowReactive} from 'vue'
import type {DocumentKind} from '../../api/types'
import type {WorkDocumentResponse} from '../../api/workDocuments'
import DocumentSourceForm from './DocumentSourceForm.vue'
const props=defineProps<{workId:string;expectedVersion:number;departmentId:string;kindOptions:{code:DocumentKind;name:string}[];authorized:boolean;allowCreate:boolean}>()
const emit=defineEmits<{saved:[value:WorkDocumentResponse];changed:[];refresh:[]}>()
type Row={id:number;file:File;status:'waiting'|'done'|'failed';expanded:boolean}
const rows=ref<Row[]>([]),reason=ref(''),error=ref(''),busy=ref(false),started=ref(false),workVersion=ref(props.expectedVersion)
const forms=shallowReactive(new Map<number,InstanceType<typeof DocumentSourceForm>>())
let nextRowId=0
const complete=computed(()=>rows.value.filter(row=>row.status==='done').length),dirty=computed(()=>rows.value.some(row=>row.status!=='done'))
const conflict=computed(()=>rows.value.some(row=>forms.get(row.id)?.workConflict))
function select(event:Event){
  const selected=Array.from((event.target as HTMLInputElement).files??[])
  if(selected.length>100){error.value='За один раз выберите не больше100 файлов.';return}
  if(started.value)return
  forms.clear();rows.value=selected.map(file=>({id:nextRowId++,file,status:'waiting',expanded:false}));error.value='';emit('changed')
}
function bind(id:number,value:unknown){if(value)forms.set(id,value as InstanceType<typeof DocumentSourceForm>);else forms.delete(id)}
function acceptVersion(){
  if(busy.value)return
  workVersion.value=props.expectedVersion
  for(const row of rows.value)if(row.status==='failed')forms.get(row.id)?.acceptVersion(workVersion.value)
}
async function run(){
  if(busy.value||!props.authorized||!props.allowCreate||!rows.value.length||!reason.value.trim())return
  if(!started.value)workVersion.value=props.expectedVersion
  started.value=true;busy.value=true;error.value='';await nextTick()
  try{
    for(const row of rows.value){
      if(row.status==='done')continue
      const value=await forms.get(row.id)!.persist(workVersion.value,reason.value.trim())
      if(!value){row.status='failed';row.expanded=true;error.value='Загрузка остановлена. Подтверждённые строки не повторяются; исправьте ошибку и повторите оставшиеся.';break}
      row.status='done';row.expanded=false;workVersion.value=value.library.context.version
      emit('saved',value);emit('changed');await nextTick()
    }
  }finally{busy.value=false}
}
defineExpose({dirty,busy})
</script>
<template>
  <section class="form-grid" data-document-batch>
    <h3>Выбранные файлы или папка <HelpTip label="Загрузка файлов и папки">До100 файлов, последовательно. Папка доступна только после вашего выбора. Это разовая загрузка, не подключение серверного каталога.</HelpTip></h3>
    <div class="form-columns"><label>Выбрать файлы<input type="file" multiple :disabled="busy||started||!authorized" @change="select"/></label><label>Выбрать папку<input data-folder-files type="file" multiple webkitdirectory :disabled="busy||started||!authorized" @change="select"/></label></div>
    <label>Причина пакетной загрузки<textarea v-model="reason" name="batch_reason" :disabled="busy||started" @input="emit('changed')"/></label>
    <p v-if="rows.length" role="status">Сохранено {{complete}} из {{rows.length}} файлов</p>
    <p v-if="error" class="message message-error" role="alert">{{error}}</p>
    <article v-for="row in rows" :key="row.id" class="archive-batch-row" :data-batch-row="row.id">
      <div class="section-heading"><div><strong>{{row.file.webkitRelativePath||row.file.name}}</strong><p class="muted compact">{{Math.ceil(row.file.size/1024)}}КБ · {{row.status==='done'?'Сохранён':row.status==='failed'?'Требует повтора':'Ожидает загрузки'}}</p></div><button type="button" :disabled="busy" @click="row.expanded=!row.expanded">{{row.expanded?'Скрыть параметры':'Вид и название'}}</button></div>
      <div v-show="row.expanded"><DocumentSourceForm :ref="value=>bind(row.id,value)" :work-id="workId" :expected-version="workVersion" :department-id="departmentId" :kind-options="kindOptions" :authorized="authorized" :allow-create="allowCreate" :initial-file="row.file" embedded @refresh="emit('refresh')" @changed="emit('changed')"/></div>
    </article>
    <section v-if="conflict" class="message"><p>Конфликт версии работы. Обновите архив; затем примите текущую версию для оставшихся файлов.</p><button type="button" @click="emit('refresh')">Обновить архив</button><button data-accept-batch-version type="button" :disabled="busy" @click="acceptVersion">Принять версию {{expectedVersion}} работы</button></section>
    <button v-if="rows.length&&complete<rows.length" data-run-batch class="button-primary" type="button" :disabled="busy||conflict||!authorized||!allowCreate||!reason.trim()" @click="run">{{busy?'Загружается…':started?'Повторить оставшиеся':'Загрузить выбранные файлы'}}</button>
    <p v-if="rows.length&&complete===rows.length" class="message message-success">Все выбранные файлы сохранены и связаны с экспертизой.</p>
  </section>
</template>
