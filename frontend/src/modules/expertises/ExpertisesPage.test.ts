import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, specialty, testRouter } from '../../test/intakeFixtures'
import ExpertisesPage from './ExpertisesPage.vue'

describe('expertise registry', () => {
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
