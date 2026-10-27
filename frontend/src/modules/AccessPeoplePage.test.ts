import {flushPromises,mount} from '@vue/test-utils'
import {describe,expect,it} from 'vitest'
import {apiKey,ApiClient} from '../api/client'
import {json,page,sessionWith} from '../test/fixtures'
import {router} from '../router'
import App from '../App.vue'

describe('access administrator navigation',()=>{
  it('opens a minimal access directory without personnel access',async()=>{
    const requests:string[]=[]
    const client=new ApiClient(async(input)=>{
      const path=String(input);requests.push(path)
      if(path.includes('/access/employees/')) return json(page([{id:'employee-2',full_name:'Другой сотрудник',is_active:true}]))
      if(path.endsWith('/account/')) return json(null)
      throw new Error('Unexpected personnel request: '+path)
    })
    const pinia=sessionWith('users.create')
    await router.push('/access')
    const wrapper=mount(App,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/access')
    expect(wrapper.find('a[href="/access"]').exists()).toBe(true)
    expect(wrapper.find('a[href="/people"]').exists()).toBe(false)
    await wrapper.get('[data-open-access="employee-2"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-create-account]').exists()).toBe(true)
    expect(requests.some(path=>/^\/api\/v1\/employees\/[^/]+\/$/.test(path))).toBe(false)
    wrapper.unmount()
  })
  it('lets a role manager reach roles without a separate view permission',async()=>{
    const pinia=sessionWith('access.roles.manage')
    const client=new ApiClient(async input=>String(input).endsWith('/permissions/')?json([]):json(page([])))
    const wrapper=mount(App,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}})
    await router.push('/roles')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/roles')
    expect(wrapper.find('a[href="/roles"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Создать роль')
    wrapper.unmount()
  })
})
