<script setup lang="ts">
import {inject,onBeforeUnmount,onMounted,ref} from 'vue'
import {routerKey} from 'vue-router'
import {LatestRequest,useApi} from '../api/client'
import type {Page} from '../api/types'
import {useSessionStore} from '../stores/session'
import {useDirtyGuard} from '../shared/ui/useDirtyGuard'
import ApiMessage from '../shared/ui/ApiMessage.vue'
import PaginationBar from '../shared/ui/PaginationBar.vue'
import EmployeeAccount from './people/EmployeeAccount.vue'
import EmployeeAccess from './people/EmployeeAccess.vue'

interface Person {id:string;full_name:string;is_active:boolean}
const api=useApi(),session=useSessionStore(),requests=new LatestRequest()
const list=ref<Page<Person>>({count:0,next:null,previous:null,results:[]})
const selected=ref<Person|null>(null),search=ref(''),page=ref(1),loading=ref(false),error=ref<unknown>(null)
const account=ref<InstanceType<typeof EmployeeAccount>|null>(null),access=ref<InstanceType<typeof EmployeeAccess>|null>(null)
const confirmLeave=useDirtyGuard(()=>Boolean(account.value?.dirty||access.value?.dirty),inject(routerKey,undefined))
async function load(nextPage=page.value){
  page.value=nextPage;loading.value=true;error.value=null
  try{await requests.run(signal=>api.request<Page<Person>>(`/access/employees/?${new URLSearchParams({search:search.value,page:String(page.value)})}`,{signal}),result=>{list.value=result;loading.value=false})}
  catch(cause){error.value=cause;loading.value=false}
}
function back(){if(confirmLeave()) selected.value=null}
onMounted(()=>load())
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Администрирование доступа</p><h1>{{selected?.full_name??'Учётные записи и назначения'}}</h1><p class="muted">Минимальный каталог для управления входом и ролями. Кадровые сведения здесь не раскрываются.</p></div><button v-if="selected" @click="back">← Назад к списку</button></div>
  <section v-if="!selected" class="card">
    <form class="toolbar" @submit.prevent="load(1)"><label class="search-field">Поиск сотрудника<input v-model="search" type="search" /></label><button :disabled="loading">Найти</button></form>
    <ApiMessage :error="error"/><p v-if="loading" class="state">Загрузка каталога…</p>
    <div v-else class="table-scroll"><table><thead><tr><th>Сотрудник</th><th>Активность</th></tr></thead><tbody><tr v-for="person in list.results" :key="person.id"><td><button class="text-button" :data-open-access="person.id" @click="selected=person">{{person.full_name}}</button></td><td>{{person.is_active?'Активен':'Неактивен'}}</td></tr><tr v-if="!list.results.length"><td colspan="2" class="state">Нет сотрудников по этой выборке.</td></tr></tbody></table></div>
    <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="load"/>
  </section>
  <section v-else :key="selected.id" class="card">
    <EmployeeAccount v-if="session.canAny('users.view','users.create','users.deactivate')" ref="account" :employee-id="selected.id"/>
    <EmployeeAccess v-if="session.canAny('access.roles.assign','access.effective.view')" ref="access" :employee-id="selected.id"/>
  </section>
</template>
