import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {apiKey,ApiClient} from '../api/client'
import {json,page,sessionWith} from '../test/fixtures'
import {router} from '../router'
import App from '../App.vue'
import AccessPeoplePage from './AccessPeoplePage.vue'
import {useSessionStore} from '../stores/session'

enableAutoUnmount(afterEach)
afterEach(()=>vi.restoreAllMocks())

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
  it('creates a person first and retries login creation on the same person without a duplicate',async()=>{
    const writes:{path:string;body:unknown}[]=[]
    const client=new ApiClient(async(input,init)=>{
      const path=String(input)
      if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
      if(init?.method==='POST'){
        writes.push({path,body:JSON.parse(String(init.body))})
        if(path==='/api/v1/employees/')return json({id:'new-person',full_name:'Новый сотрудник',is_active:true,version:1,org_assignments:[],specialties:[]},201)
        return writes.length===2?json({message:'Такой логин уже используется'},400):json({id:'new-user',username:'new-login',is_active:true},201)
      }
      if(path.endsWith('/account/'))return json(null)
      return json(page([]))
    })
    const wrapper=mount(AccessPeoplePage,{global:{plugins:[sessionWith('users.create','employees.create')],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    await wrapper.get('[data-add-access-employee]').trigger('click')
    await wrapper.get('[name="full_name"]').setValue('Новый сотрудник')
    await wrapper.get('[data-create-access-employee]').trigger('submit');await flushPromises()
    expect(writes).toEqual([{path:'/api/v1/employees/',body:{full_name:'Новый сотрудник'}}])
    expect(wrapper.get('h1').text()).toBe('Новый сотрудник')
    await wrapper.get('[name="new_username"]').setValue('new-login')
    await wrapper.get('[name="new_password"]').setValue('New-person-test-password9!')
    await wrapper.get('[data-create-account]').trigger('submit');await flushPromises()
    expect(wrapper.text()).toContain('Такой логин уже используется')
    expect((wrapper.get('[name="new_username"]').element as HTMLInputElement).value).toBe('new-login')
    await wrapper.get('[data-create-account]').trigger('submit');await flushPromises()
    expect(writes.map(write=>write.path)).toEqual(['/api/v1/employees/','/api/v1/employees/new-person/account/','/api/v1/employees/new-person/account/'])
    expect(wrapper.find('[data-create-account]').exists()).toBe(false)
    expect(wrapper.text()).toContain('new-login')
  })
  it('does not offer new personnel creation to a login-only administrator',async()=>{
    const client=new ApiClient(async()=>json(page([])))
    const wrapper=mount(AccessPeoplePage,{global:{plugins:[sessionWith('users.create')],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(wrapper.find('[data-add-access-employee]').exists()).toBe(false)
  })
  it('guards the new employee draft and keeps its name when creation fails',async()=>{
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
    const client=new ApiClient(async(input,init)=>String(input).endsWith('/csrf/')?json({csrf_token:'token'}):init?.method==='POST'?json({message:'Не удалось создать сотрудника'},503):json(page([])))
    const wrapper=mount(AccessPeoplePage,{global:{plugins:[sessionWith('users.create','employees.create')],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    await wrapper.get('[data-add-access-employee]').trigger('click')
    await wrapper.get('[name="full_name"]').setValue('Черновик сотрудника')
    await wrapper.get('[data-back-access]').trigger('click')
    expect(wrapper.find('[data-create-access-employee]').exists()).toBe(true)
    await wrapper.get('[data-create-access-employee]').trigger('submit');await flushPromises()
    expect(wrapper.text()).toContain('Не удалось создать сотрудника')
    expect((wrapper.get('[name="full_name"]').element as HTMLInputElement).value).toBe('Черновик сотрудника')
    confirm.mockReturnValue(true)
    await wrapper.get('[data-back-access]').trigger('click')
    expect(wrapper.find('[data-create-access-employee]').exists()).toBe(false)
  })
  it('opens the account and reset action for a reset-only administrator',async()=>{
    const pinia=sessionWith('users.reset_password')
    const client=new ApiClient(async input=>String(input).endsWith('/account/')?json({id:'u-2',username:'existing-user',is_active:true}):json(page([{id:'employee-2',full_name:'Сотрудник',is_active:true}])))
    await router.push('/access')
    const wrapper=mount(App,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/access')
    await wrapper.get('[data-open-access="employee-2"]').trigger('click');await flushPromises()
    expect(wrapper.find('[data-reset-account]').exists()).toBe(true)
  })
  it.each(['reset','employee','account'])('blocks route navigation until a pending %s command settles',async mode=>{
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(true)
    let finish!:(response:Response)=>void
    const pending=new Promise<Response>(resolve=>{finish=resolve})
    const pinia=sessionWith('users.create','users.reset_password','employees.create')
    const logout=vi.spyOn(useSessionStore(),'logout').mockResolvedValue()
    const client=new ApiClient(async(input,init)=>{
      const path=String(input)
      if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
      if(init?.method==='POST')return pending
      if(path.endsWith('/account/'))return json(mode==='reset'?{id:'u-2',username:'existing-user',is_active:true}:null)
      return json(page([{id:'employee-2',full_name:'Сотрудник',is_active:true}]))
    })
    await router.push('/access')
    const wrapper=mount(App,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    if(mode==='employee'){
      await wrapper.get('[data-add-access-employee]').trigger('click')
      await wrapper.get('[name="full_name"]').setValue('Новый сотрудник')
      await wrapper.get('[data-create-access-employee]').trigger('submit')
    }else{
      await wrapper.get('[data-open-access="employee-2"]').trigger('click');await flushPromises()
      if(mode==='reset'){
        await wrapper.get('[data-reset-account]').trigger('click')
        await wrapper.get('[name="reset_password"]').setValue('Pending-test-password9!')
        await wrapper.get('[name="reset_password_confirm"]').setValue('Pending-test-password9!')
        await wrapper.get('[data-reset-account-form]').trigger('submit')
      }else{
        await wrapper.get('[name="new_username"]').setValue('new-user')
        await wrapper.get('[name="new_password"]').setValue('Pending-test-password9!')
        await wrapper.get('[data-create-account]').trigger('submit')
      }
    }
    await flushPromises()
    await wrapper.get('button[aria-label="Выйти из системы"]').trigger('click');await flushPromises()
    const logoutCalls=logout.mock.calls.length
    await router.push('/workspace')
    const pendingRoute=router.currentRoute.value.path
    finish(json(mode==='employee'?{id:'new-person',full_name:'Новый сотрудник',is_active:true}:{id:'u-2',username:'existing-user',is_active:true}))
    await flushPromises()
    expect(logoutCalls).toBe(0)
    expect(pendingRoute).toBe('/access')
    expect(confirm).not.toHaveBeenCalled()
    await router.push('/workspace')
    expect(router.currentRoute.value.path).toBe('/workspace')
  })
})
