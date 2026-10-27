import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { basis } from '../test/intakeFixtures'
import type { FileVersion } from '../api/types'
import BasisPreview from './BasisPreview.vue'
const first: FileVersion = { id: 'f-1', number: 1, original_name: 'basis.pdf', content_type: 'application/pdf', size: 2048, sha256: 'sha-first', created_at: '2026-10-28T08:00:00Z', download_url: '/api/v1/file-versions/f-1/download/', preview_url: '/api/v1/file-versions/f-1/preview/' }
describe('authorized basis preview', () => {
  it('opens the accepted file rather than a later ordinary upload and labels other versions unconfirmed', async () => {
    const second = { ...first, id: 'f-2', number: 2, preview_url: '/api/v1/file-versions/f-2/preview/' }
    const document = { ...basis, accepted_version_id: 'f-1', versions: [first, second] }
    const wrapper = mount(BasisPreview, { props: { document } })
    expect(wrapper.get('iframe').attributes('src')).toBe(first.preview_url)
    await wrapper.get('select').setValue('f-2')
    expect(wrapper.get('iframe').attributes('src')).toBe(second.preview_url)
    expect(wrapper.get('[data-unconfirmed-file]').text()).toContain('не подтверждена')
    await wrapper.setProps({ document: { ...document, accepted_version_id: 'f-2' } })
    expect(wrapper.find('[data-unconfirmed-file]').exists()).toBe(false)
    expect(wrapper.get('iframe').attributes('src')).toBe(second.preview_url)
    wrapper.unmount()
  })
  it('selects the newest persisted version and can preview an older PDF without changing its original', async () => {
    const second = { ...first, id: 'f-2', number: 2, original_name: 'new-basis.pdf', download_url: '/api/v1/file-versions/f-2/download/', preview_url: '/api/v1/file-versions/f-2/preview/' }
    const wrapper = mount(BasisPreview, { props: { document: { ...basis, versions: [first, second] } } })
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('f-2')
    expect(wrapper.get('iframe').attributes('src')).toBe('/api/v1/file-versions/f-2/preview/')
    await wrapper.get('select').setValue('f-1')
    expect(wrapper.get('iframe').attributes('src')).toBe('/api/v1/file-versions/f-1/preview/')
    expect(wrapper.get('a').attributes('href')).toBe('/api/v1/file-versions/f-1/download/')
    await wrapper.setProps({ document: { ...basis, versions: [first, { ...second }] } })
    expect(wrapper.get('iframe').attributes('src')).toBe('/api/v1/file-versions/f-1/preview/')
    wrapper.unmount()
  })
  it('renders supported images inside the card and explains download-only formats', async () => {
    const wrapper = mount(BasisPreview, { props: { document: { ...basis, versions: [{ ...first, content_type: 'image/jpeg', original_name: 'photo.jpg' }] } } })
    expect(wrapper.get('img').attributes('src')).toBe('/api/v1/file-versions/f-1/preview/')
    await wrapper.setProps({ document: { ...basis, versions: [{ ...first, content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', preview_url: null }] } })
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('Предпросмотр недоступен')
    expect(wrapper.get('a').attributes('href')).toBe('/api/v1/file-versions/f-1/download/')
    wrapper.unmount()
  })
})
