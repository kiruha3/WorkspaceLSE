import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { basis } from '../test/intakeFixtures'
import type { FileVersion } from '../api/types'
import BasisPreview from './BasisPreview.vue'
import { compactPresentationKey } from './ui/compactPresentation'
const first: FileVersion = { id: 'f-1', number: 1, original_name: 'basis.pdf', content_type: 'application/pdf', size: 2048, sha256: 'sha-first', created_at: '2026-10-28T08:00:00Z', download_url: '/api/v1/file-versions/f-1/download/', preview_url: '/api/v1/file-versions/f-1/preview/' }
describe('authorized basis preview', () => {
  it('inherits compact presentation from its card while allowing an explicit expanded preview', () => {
    const document = { ...basis, versions: [first] }
    const global = { provide: { [compactPresentationKey as symbol]: true } }
    const compact = mount(BasisPreview, { props: { document }, global })
    const expanded = mount(BasisPreview, { props: { document, compact: false }, global })
    expect(compact.find('iframe').exists()).toBe(false)
    expect(compact.get('[data-document-details-toggle]').attributes('aria-expanded')).toBe('false')
    expect(expanded.get('iframe').attributes('src')).toBe('/api/v1/file-versions/f-1/preview/')
    expect(expanded.find('[data-document-details-toggle]').exists()).toBe(false)
    compact.unmount(); expanded.unmount()
  })
  it.each([
    { contentType: 'application/pdf', media: 'iframe', fileName: 'basis.pdf' },
    { contentType: 'image/jpeg', media: 'img', fileName: 'basis.jpg' },
  ])('loads a compact $media only after disclosure while keeping its download available', async ({ contentType, media, fileName }) => {
    const wrapper = mount(BasisPreview, { attachTo: window.document.body, props: { compact: true, document: { ...basis, versions: [{ ...first, content_type: contentType, original_name: fileName, preview_url: 'about:blank' }] } } })
    expect(wrapper.find(media).exists()).toBe(false)
    expect(wrapper.text()).toContain('Постановление суда')
    expect(wrapper.text()).toContain(`${fileName} · 2 КБ · версия 1`)
    expect(wrapper.get('a[download]').attributes('href')).toBe('/api/v1/file-versions/f-1/download/')
    const toggle = wrapper.get('[data-document-details-toggle]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    await toggle.trigger('click')
    const viewer = wrapper.get(media)
    expect(viewer.attributes('src')).toBe('about:blank')
    expect(viewer.isVisible()).toBe(true)
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.get(media).isVisible()).toBe(false)
    await toggle.trigger('click')
    expect(wrapper.get(media).element).toBe(viewer.element)
    wrapper.unmount()
  })
  it('keeps the selected compact version and its preview error through disclosure and same-document refresh', async () => {
    const second = { ...first, id: 'f-2', number: 2, original_name: 'later.pdf', preview_url: '/api/v1/file-versions/f-2/preview/' }
    const document = { ...basis, accepted_version_id: 'f-1', versions: [first, second] }
    const wrapper = mount(BasisPreview, { props: { compact: true, document } })
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.get('a[download]').attributes('href')).toBe('/api/v1/file-versions/f-1/download/')
    expect(wrapper.text()).toContain('подтверждена версия 1')
    await wrapper.get('[data-document-details-toggle]').trigger('click')
    await wrapper.get('select').setValue('f-2')
    await wrapper.get('iframe').trigger('error')
    expect(wrapper.text()).toContain('Не удалось загрузить предпросмотр')
    await wrapper.get('[data-document-details-toggle]').trigger('click')
    await wrapper.setProps({ document: { ...document, versions: [{ ...first }, { ...second }] } })
    await wrapper.get('[data-document-details-toggle]').trigger('click')
    expect(wrapper.get('select').element).toHaveProperty('value', 'f-2')
    expect(wrapper.get('[data-unconfirmed-file]').isVisible()).toBe(true)
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain('Не удалось загрузить предпросмотр')
    wrapper.unmount()
  })
  it('requires the separate external-source action after expanding compact details', async () => {
    const wrapper = mount(BasisPreview, { props: { compact: true, document: { ...basis, source_kind: 'external_link', source_url: 'https://example.org/doc.pdf', versions: [] } } })
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.find('[data-open-external-preview]').exists()).toBe(false)
    await wrapper.get('[data-document-details-toggle]').trigger('click')
    expect(wrapper.find('iframe').exists()).toBe(false)
    await wrapper.get('[data-open-external-preview]').trigger('click')
    expect(wrapper.get('iframe').attributes('src')).toBe('https://example.org/doc.pdf')
    expect(wrapper.get('iframe').attributes('sandbox')).toBe('')
    expect(wrapper.get('iframe').attributes('referrerpolicy')).toBe('no-referrer')
    wrapper.unmount()
  })
  it('keeps an opened compact viewer on refresh but closes it for another document identity', async () => {
    const document = { ...basis, versions: [first] }
    const wrapper = mount(BasisPreview, { props: { compact: true, document } })
    expect(wrapper.find('iframe').exists()).toBe(false)
    await wrapper.get('[data-document-details-toggle]').trigger('click')
    const viewer = wrapper.get('iframe').element
    await wrapper.setProps({ document: { ...document, versions: [{ ...first }] } })
    expect(wrapper.get('[data-document-details-toggle]').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('iframe').isVisible()).toBe(true)
    expect(wrapper.get('iframe').element).toBe(viewer)
    await wrapper.setProps({ document: { ...document, id: 'document-2' } })
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.get('[data-document-details-toggle]').attributes('aria-expanded')).toBe('false')
    wrapper.unmount()
  })
  it('keeps restrictions, missing paper scans, and unknown accepted versions explicit when compact', () => {
    const restricted = mount(BasisPreview, { props: { compact: true, document: { id: 'secret', restricted: true } } })
    expect(restricted.text()).toContain('Доступ к документу ограничен')
    expect(restricted.find('iframe').exists()).toBe(false)
    expect(restricted.find('[data-document-details-toggle]').exists()).toBe(false)
    const paper = mount(BasisPreview, { props: { compact: true, document: basis } })
    expect(paper.text()).toContain('Бумажный оригинал')
    expect(paper.text()).toContain('Электронный скан пока не добавлен')
    expect(paper.find('[data-document-details-toggle]').exists()).toBe(false)
    const unknown = mount(BasisPreview, { props: { compact: true, document: { ...basis, accepted_version_id: null, versions: [first] } } })
    expect(unknown.text()).toContain('Подтверждённая версия файла не установлена')
    expect(unknown.find('a[download]').exists()).toBe(false)
    expect(unknown.find('iframe').exists()).toBe(false)
    restricted.unmount(); paper.unmount(); unknown.unmount()
  })
  it('does not load a URL until explicitly requested and never calls it an archived scan',async()=>{
    const wrapper=mount(BasisPreview,{props:{document:{...basis,source_kind:'external_link',source_url:'https://example.org/doc.pdf',versions:[]}}})
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain('Внешняя ссылка')
    await wrapper.get('[data-open-external-preview]').trigger('click')
    expect(wrapper.get('iframe').attributes('src')).toBe('https://example.org/doc.pdf')
    expect(wrapper.get('iframe').attributes('sandbox')).toBe('')
    expect(wrapper.get('iframe').attributes('referrerpolicy')).toBe('no-referrer')
    expect(wrapper.get('[data-external-source]').attributes('rel')).toContain('noreferrer')
    wrapper.unmount()
  })
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
