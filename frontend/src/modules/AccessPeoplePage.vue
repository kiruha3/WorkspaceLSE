<script setup lang="ts">
import SortableTable from '../shared/ui/SortableTable.vue'
import {orderingParams} from '../shared/ui/tableSorting'

import {computed,inject,onBeforeUnmount,onMounted,ref} from 'vue'
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
const ordering=ref('')
function sortTable(value:string){ordering.value=value;void load(1)}
const api=useApi(),session=useSessionStore(),requests=new LatestRequest()
const list=ref<Page<Person>>({count:0,next:null,previous:null,results:[]})
const selected=ref<Person|null>(null),search=ref(''),page=ref(1),loading=ref(false),error=ref<unknown>(null)
const creating=ref(false),fullName=ref(''),saving=ref(false),createError=ref<unknown>(null),success=ref('')
const account=ref<InstanceType<typeof EmployeeAccount>|null>(null),access=ref<InstanceType<typeof EmployeeAccess>|null>(null)
const busy=computed(()=>saving.value||Boolean(account.value?.busy||access.value?.busy))
const confirmLeave=useDirtyGuard(()=>Boolean((creating.value&&fullName.value)||account.value?.dirty||access.value?.dirty),inject(routerKey,undefined),()=>busy.value)
async function load(nextPage=page.value){
  page.value=nextPage;loading.value=true;error.value=null
  try{await requests.run(signal=>api.request<Page<Person>>(`/access/employees/?${new URLSearchParams({...orderingParams(ordering.value),search:search.value,page:String(page.value)})}`,{signal}),result=>{list.value=result;loading.value=false})}
  catch(cause){error.value=cause;loading.value=false}
}
function back(){
  if(busy.value||!confirmLeave())return
  selected.value=null;creating.value=false;fullName.value='';createError.value=null;success.value=''
}
function startCreate(){
  if(busy.value||!session.can('employees.create')||!confirmLeave())return
  selected.value=null;creating.value=true;fullName.value='';createError.value=null;success.value=''
}
async function createEmployee(){
  if(saving.value||!session.can('employees.create')||!fullName.value.trim())return
  saving.value=true;createError.value=null
  try{
    selected.value=await api.request<Person>('/employees/',{method:'POST',body:{full_name:fullName.value.trim()}})
    fullName.value='';creating.value=false;success.value='Карточка сотрудника создана. Теперь задайте логин и первоначальный пароль, затем назначьте роли.'
    void load()
  }catch(cause){createError.value=cause}finally{saving.value=false}
}
onMounted(()=>load())
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Администрирование доступа</p><h1>{{creating?'Новый сотрудник':selected?.full_name??'Учётные записи и назначения'}}</h1><p class="muted">Выберите сотрудника, чтобы создать персональный вход, сбросить пароль или назначить роли.</p></div><div class="button-row"><button v-if="selected||creating" data-back-access :disabled="busy" @click="back">← Назад к списку</button><button v-if="!creating&&session.can('employees.create')" data-add-access-employee class="button-primary" :disabled="busy" @click="startCreate">+ Добавить сотрудника</button></div></div>
  <section v-if="creating" class="card narrow-card">
    <h2>Новый сотрудник</h2><p class="muted">Сначала создайте карточку человека. Затем здесь можно выдать логин, задать пароль и назначить роли. Если сотрудник уже есть, вернитесь к списку и выберите его.</p><ApiMessage :error="createError"/>
    <form data-create-access-employee class="form-grid" @submit.prevent="createEmployee"><fieldset class="form-grid" :disabled="saving">
      <label>ФИО<input v-model="fullName" name="full_name" required maxlength="220" autocomplete="name"/></label>
      <div class="button-row"><button class="button-primary" :disabled="saving||!fullName.trim()">{{saving?'Создание…':'Создать сотрудника'}}</button><button type="button" :disabled="saving" @click="back">Отмена</button></div>
    </fieldset></form>
  </section>
  <section v-else-if="!selected" class="card">
    <form class="toolbar" @submit.prevent="load(1)"><label class="search-field">Поиск сотрудника<input v-model="search" type="search" /></label><button :disabled="loading">Найти</button></form>
    <ApiMessage :error="error"/><p v-if="loading" class="state">Загрузка каталога…</p>
    <div v-else class="table-scroll"><SortableTable :rows="list.results" :columns='[{"key": "full_name", "label": "Сотрудник"}, {"key": "is_active", "label": "Активность"}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}"><tr v-for="person in tableRows" :key="person.id"><td><button class="text-button" :data-open-access="person.id" @click="selected=person">{{person.full_name}}</button></td><td>{{person.is_active?'Активен':'Неактивен'}}</td></tr><tr v-if="!list.results.length"><td colspan="2" class="state">Нет сотрудников по этой выборке.</td></tr></SortableTable></div>
    <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="load"/>
  </section>
  <section v-else :key="selected.id" class="card">
    <p v-if="success" class="message message-success" role="status">{{success}}</p>
    <EmployeeAccount v-if="session.canAny('users.view','users.create','users.reset_password','users.deactivate')" ref="account" :employee-id="selected.id"/>
    <EmployeeAccess v-if="session.canAny('access.roles.assign','access.effective.view')" ref="access" :employee-id="selected.id"/>
  </section>
</template>
