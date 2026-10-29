import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, specialty, testRouter } from '../../test/intakeFixtures'
import ExpertisesPage from './ExpertisesPage.vue'
import { useSessionStore } from '../../stores/session'

describe('expertise registry', () => {
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
    expect(router.currentRoute.value.query).toEqual({ state: 'suspended', calendar_days_min: '3', calendar_days_max: '12', page: '1' })
    wrapper.unmount()
  })
  it('uses URL filters and keeps them in the detail return link', async () => {
    const paths: string[] = []
    const client = new ApiClient(async input => {
      const path = String(input); paths.push(path)
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
      return json({ ...page([expertise]), count: 30, previous: '?page=1' })
    })
    const router = await testRouter('/expertises?search=151&department_id=d-4&page=2')
    const wrapper = mount(ExpertisesPage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(paths.some(path => path.includes('search=151') && path.includes('department_id=d-4') && path.includes('page=2'))).toBe(true)
    expect(wrapper.get('.pagination').text()).toContain('Страница 2')
    const detail = new URL(wrapper.get('[data-open-expertise]').attributes('href')!, 'http://localhost')
    expect(detail.pathname).toBe('/expertises/work-1')
    expect(detail.searchParams.get('return')).toBe('/expertises?search=151&department_id=d-4&page=2')
    await wrapper.get('[name="search"]').setValue('152')
    await wrapper.get('form.toolbar').trigger('submit'); await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ search: '152', department_id: 'd-4', page: '1' })
    wrapper.unmount()
  })
})
