<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {RouterLink,useRoute,useRouter} from 'vue-router'
import {useSessionStore} from '../../stores/session'
import {canReadReportPlans,institutionPermission} from '../../api/reportPlans'
import ReportPlanEditor from './ReportPlanEditor.vue'
const route=useRoute(),router=useRouter(),session=useSessionStore()
const todayYear=()=>Number(new Intl.DateTimeFormat('en',{timeZone:'Asia/Krasnoyarsk',year:'numeric'}).format(new Date()))
const year=computed(()=>{
 const value=route.query.year
 if(value===undefined)return todayYear()
 if(typeof value!=='string'||!/^\d{4}$/.test(value))return null
 const number=Number(value);return number>=1900&&number<=2200?number:null
})
const requestedYear=ref<number|string>(year.value??todayYear()),enabled=computed(()=>canReadReportPlans(session.user))
watch(year,value=>{if(value!==null)requestedYear.value=value})
async function chooseYear(){
 const value=Number(requestedYear.value)
 if(!Number.isInteger(value)||value<1900||value>2200)return
 await router.push({path:'/report-plans',query:{...route.query,year:String(value)}})
 requestedYear.value=year.value??todayYear()
}
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Госзадание · раздел 6 формы15.1</p><h1>Годовые планы</h1><p class="muted">Общий объём и явное распределение по специальностям. Фактическое выполнение считается из экспертиз отдельно.</p></div><RouterLink v-if="institutionPermission(session.user,'reports.form151.run')" class="button" to="/reports">К отчёту 15.1</RouterLink></div>
 <p v-if="!enabled" class="state">Для просмотра плана нужны права справочников, расчёта15.1 или ведения планов по учреждению.</p>
 <template v-else><form class="card year-picker" @submit.prevent="chooseYear"><label>Год плана<input v-model="requestedYear" name="plan_year" type="number" min="1900" max="2200" step="1" required/></label><button>Открыть год</button></form>
 <p v-if="year===null" class="message message-error">В ссылке должен быть один год от1900до2200.</p><ReportPlanEditor v-else :key="year" :year="year"/></template>
</template>
<style scoped>.year-picker{display:flex;align-items:end;gap:16px;margin-bottom:20px}.year-picker label{display:flex;flex-direction:column;gap:8px;max-width:180px}@media(max-width:600px){.year-picker{align-items:stretch;flex-direction:column}}</style>
