import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {afterEach,expect,it} from 'vitest'
import {createMemoryHistory,createRouter} from 'vue-router'
import {sessionWith} from '../../test/fixtures'
import {useSessionStore} from '../../stores/session'
import App from '../../App.vue'
import HomePage from '../HomePage.vue'
enableAutoUnmount(afterEach)
async function open(department=false){
 const pinia=sessionWith(department?'reports.form151.run':'reports.plans.manage')
 if(department)useSessionStore(pinia).user!.access['reports.form151.run']![0]!.scope='departments'
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/workspace',component:HomePage},{path:'/report-plans',component:{template:'<p>Планы</p>'}}]});await router.push('/workspace');await router.isReady()
 const wrapper=mount(App,{global:{plugins:[pinia,router]}});await flushPromises();return wrapper
}
it('offers institutional plan navigation on the home and sidebar without implying report or document rights',async()=>{
 const wrapper=await open();expect(wrapper.find('nav a[href="/report-plans"]').exists()).toBe(true);expect(wrapper.find('main a[href="/report-plans"]').exists()).toBe(true);expect(wrapper.text()).not.toContain('пока не назначены рабочие разделы')
})
it('does not advertise institutional plan access from a department-only reporting role',async()=>{
 const wrapper=await open(true);expect(wrapper.find('a[href="/report-plans"]').exists()).toBe(false)
})
