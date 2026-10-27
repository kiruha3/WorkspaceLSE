import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, specialty, testRouter } from '../../test/intakeFixtures'
import ExpertisesPage from './ExpertisesPage.vue'

describe('expertise registry', () => {
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
