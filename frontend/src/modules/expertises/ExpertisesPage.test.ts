import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, specialty, testRouter } from '../../test/intakeFixtures'
import ExpertisesPage from './ExpertisesPage.vue'
import { useSessionStore } from '../../stores/session'

describe('expertise registry', () => {
  it('renders the complete lightweight collection including rows beyond the old page boundary',async()=>{
    const records=Array.from({length:41},(_,index)=>({...expertise,id:`record-${index+1}`,registration_number:`${index+1}/4-1-26`}))
    const paths:string[]=[]
    const client=new ApiClient(async input=>{const path=String(input);paths.push(path);if(path.includes('/references/'))return json(page([]));if(path.includes('filter-options'))return json({employees:[]});return json({count:records.length,results:records})})
    const router=await testRouter('/expertises?page=2&page_size=1')
    const wrapper=mount(ExpertisesPage,{global:{plugins:[sessionWith('expertise.view'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(wrapper.findAll('[data-open-expertise]')).toHaveLength(41)
    expect(wrapper.findAll('[data-open-expertise]').at(-1)?.text()).toBe('41/4-1-26')
    expect(wrapper.get('[data-registry-count]').text()).toContain('41')
    expect(wrapper.find('.pagination').exists()).toBe(false)
    expect(paths.some(path=>path.startsWith('/api/v1/expertises/registry/')&&!path.includes('page='))).toBe(true)
    wrapper.unmount()
  })
  it('rejects a truncated collection and offers retry instead of showing it as the complete list',async()=>{
    let complete=false
    const client=new ApiClient(async input=>String(input).includes('/references/')?json(page([])):String(input).includes('filter-options')?json({employees:[]}):json({count:complete?1:2,results:[expertise]}))
    const router=await testRouter('/expertises')
    const wrapper=mount(ExpertisesPage,{global:{plugins:[sessionWith('expertise.view'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(wrapper.find('[data-open-expertise]').exists()).toBe(false)
    expect(wrapper.text()).toContain('неполный список')
    complete=true;await wrapper.get('[data-retry-registry]').trigger('click');await flushPromises()
    expect(wrapper.findAll('[data-open-expertise]')).toHaveLength(1)
    wrapper.unmount()
  })
  it('cycles server sorting without page parameters and preserves filters and return links',async()=>{
    const paths:string[]=[]
    const client=new ApiClient(async input=>{const path=String(input);paths.push(path);if(path.includes('filter-options'))return json({employees:[]});return json(page(path.includes('/references/')?[]:[expertise]))})
    const router=await testRouter('/expertises?page=2&state=in_progress')
    const wrapper=mount(ExpertisesPage,{global:{plugins:[sessionWith('expertise.view'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    for(const expected of ['registration_number','-registration_number','']){
      await wrapper.get('[data-sort-column="registration_number"]').trigger('click');await flushPromises()
      expect(router.currentRoute.value.query.page).toBeUndefined()
      expect(router.currentRoute.value.query.ordering??'').toBe(expected)
      const query=new URL(paths.filter(path=>path.startsWith('/api/v1/expertises/registry/?')).at(-1)!,'http://localhost').searchParams
      expect(query.has('page')).toBe(false)
      expect(query.get('state')).toBe('in_progress');expect(query.get('ordering')??'').toBe(expected)
      expect(new URL(wrapper.get('[data-open-expertise]').attributes('href')!,'http://localhost').searchParams.get('return')).toBe(router.currentRoute.value.fullPath)
    }
    wrapper.unmount()
  })
  it('downloads all applied URL filters without pagination only after a click', async () => {
    const downloads: string[] = [], saved: string[] = []
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:expertises')
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { saved.push(this.download) })
    const client = new ApiClient(async input => {
      const path = String(input)
      if (path.includes('/export.xlsx')) {
        downloads.push(path)
        return new Response('xlsx', { headers: {
          'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition':'attachment; filename="expertises-2026-10-29.xlsx"',
        } })
      }
      if (path.includes('filter-options')) return json({ employees: [] })
      return json(page([]))
    })
    const router = await testRouter('/expertises?search=151&state=suspended&calendar_days_min=0&calendar_days_max=12&department_id=d-4&specialty_id=s-1&employee_id=e-1&received_from=2026-01-01&received_to=2026-12-31&ordering=-registration_number&page=2&page_size=1')
    const wrapper = mount(ExpertisesPage, { global: { plugins: [sessionWith('expertise.view','expertise.export'),router], provide: { [apiKey as symbol]:client } } })
    try {
      await flushPromises(); expect(downloads).toEqual([])
      await wrapper.get('[name="search"]').setValue('not-yet-applied')
      await wrapper.get('[data-export-expertises]').trigger('click'); await flushPromises()
      expect(downloads).toHaveLength(1)
      const query = new URL(downloads[0]!, 'http://localhost').searchParams
      expect(Object.fromEntries(query)).toEqual({ search:'151', state:'suspended', calendar_days_min:'0', calendar_days_max:'12', department_id:'d-4', specialty_id:'s-1', employee_id:'e-1', received_from:'2026-01-01', received_to:'2026-12-31',ordering:'-registration_number' })
      expect(saved).toEqual(['expertises-2026-10-29.xlsx'])
      expect(createUrl).toHaveBeenCalledOnce()
    } finally { wrapper.unmount(); vi.restoreAllMocks() }
  })
  it('hides Excel download without export access', async () => {
    const client = new ApiClient(async input => String(input).includes('filter-options') ? json({employees:[]}) : json(page([])))
    const router = await testRouter('/expertises')
    const wrapper = mount(ExpertisesPage,{global:{plugins:[sessionWith('expertise.view'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(wrapper.find('[data-export-expertises]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('shows a denied export without starting a browser download', async () => {
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:unexpected')
    const client = new ApiClient(async input => String(input).includes('/export.xlsx')
      ? json({code:'permission_denied',message:'Нет права выгружать эту выборку.'},403)
      : String(input).includes('filter-options') ? json({employees:[]}) : json(page([])))
    const router = await testRouter('/expertises')
    const wrapper = mount(ExpertisesPage,{global:{plugins:[sessionWith('expertise.view','expertise.export'),router],provide:{[apiKey as symbol]:client}}})
    try {
      await flushPromises(); await wrapper.get('[data-export-expertises]').trigger('click'); await flushPromises()
      expect(wrapper.get('[role="alert"]').text()).toContain('Нет права выгружать эту выборку.')
      expect(createUrl).not.toHaveBeenCalled()
      expect(wrapper.get('[data-export-expertises]').attributes('disabled')).toBeUndefined()
    } finally { wrapper.unmount(); vi.restoreAllMocks() }
  })
  it('offers Google and file sync directly and opens review without applying expertise changes', async () => {
    const writes: { path:string; body:unknown }[] = []
    const client = new ApiClient(async (input, init) => {
      const path=String(input)
      if(path.includes('/csrf/'))return json({csrf_token:'t'})
      if(path.includes('/google-source/'))return json({configured:true,spreadsheet_id:'source-123456789',gid:'0',sheet_name:'Лист1',label:'Журнал',url:'https://docs.google.com/spreadsheets/d/source-123456789/edit'})
      if(init?.method==='POST'){writes.push({path,body:JSON.parse(String(init.body))});return json({batch:{id:'fresh-batch'}},201)}
      return path.includes('filter-options')?json({employees:[]}):json(page([]))
    })
    const router=await testRouter('/expertises?state=in_progress&page=2')
    router.addRoute({path:'/imports/:id/review',component:{template:'<p>Перечень изменений</p>'}})
    router.addRoute({path:'/imports',component:{template:'<p>Источники</p>'}})
    const pinia=sessionWith('expertise.view','imports.results.view','imports.preview','imports.reconcile','imports.apply')
    useSessionStore(pinia).user!.supported_modules=['journal_import_preview','journal_application','journal_google_preview']
    const wrapper=mount(ExpertisesPage,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    expect(wrapper.find('[data-read-journal-source]').exists()).toBe(true)
    expect(wrapper.find('[data-upload-journal-file]').exists()).toBe(true)
    await wrapper.get('[data-read-journal-source]').trigger('click');await flushPromises()
    expect(writes).toHaveLength(1)
    expect(writes[0]!.path).toBe('/api/v1/imports/google-preview/')
    expect(router.currentRoute.value.path).toBe('/imports/fresh-batch/review')
    expect(router.currentRoute.value.query.return).toBe('/expertises?state=in_progress&page=2')
    wrapper.unmount()
  })
  it('labels an explicitly training material without inferring from the title',async()=>{
    const client=new ApiClient(async input=>String(input).includes('/references/')?json(page([])):String(input).includes('filter-options')?json({employees:[]}):json(page([{...expertise,material:{...expertise.material,is_demo:true}}])))
    const router=await testRouter('/expertises')
    const wrapper=mount(ExpertisesPage,{global:{plugins:[sessionWith('expertise.view'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises();expect(wrapper.text()).toContain('Учебная запись');wrapper.unmount()
  })
  it('restores state and calendar day range from the URL, forwards zero and retains filters in the work return link', async () => {
    const paths: string[] = []
    const client = new ApiClient(async input => {
      const path = String(input); paths.push(path)
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
      if (path.includes('filter-options')) return json({ employees: [] })
      return json(page([expertise]))
    })
    const router = await testRouter('/expertises?state=suspended&calendar_days_min=0&calendar_days_max=12&page=1')
    const wrapper = mount(ExpertisesPage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.get('[name="state"]').element).toHaveProperty('value', 'suspended')
    expect(wrapper.get('[name="calendar_days_min"]').element).toHaveProperty('value', '0')
    expect(wrapper.get('[name="calendar_days_max"]').element).toHaveProperty('value', '12')
    expect(paths.some(path => path.includes('state=suspended') && path.includes('calendar_days_min=0') && path.includes('calendar_days_max=12'))).toBe(true)
    const link = new URL(wrapper.get('[data-open-expertise]').attributes('href')!, 'http://localhost')
    expect(link.searchParams.get('return')).toBe('/expertises?state=suspended&calendar_days_min=0&calendar_days_max=12&page=1')
    await wrapper.get('[name="calendar_days_min"]').setValue('3')
    await wrapper.get('form.toolbar').trigger('submit'); await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ state: 'suspended', calendar_days_min: '3', calendar_days_max: '12' })
    wrapper.unmount()
  })
  it('uses URL filters and keeps them in the detail return link', async () => {
    const paths: string[] = []
    const client = new ApiClient(async input => {
      const path = String(input); paths.push(path)
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
      return json(page([expertise]))
    })
    const router = await testRouter('/expertises?search=151&department_id=d-4&page=2')
    const wrapper = mount(ExpertisesPage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(paths.some(path => path.includes('/expertises/registry/?') && path.includes('search=151') && path.includes('department_id=d-4') && !path.includes('page='))).toBe(true)
    expect(wrapper.find('.pagination').exists()).toBe(false)
    expect(wrapper.get('[data-registry-count]').text()).toContain('1')
    const detail = new URL(wrapper.get('[data-open-expertise]').attributes('href')!, 'http://localhost')
    expect(detail.pathname).toBe('/expertises/work-1')
    expect(detail.searchParams.get('return')).toBe('/expertises?search=151&department_id=d-4&page=2')
    await wrapper.get('[name="search"]').setValue('152')
    await wrapper.get('form.toolbar').trigger('submit'); await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ search: '152', department_id: 'd-4' })
    wrapper.unmount()
  })
})
