import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import HelpTip from './HelpTip.vue'

enableAutoUnmount(afterEach)
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); document.body.innerHTML = '' })
const open = () => mount(HelpTip, { attachTo: document.body, props: { label: 'Сроки' }, slots: { default: 'Паузы учитываются отдельно.' } })
const tip = () => document.querySelector<HTMLElement>('[role="tooltip"]')

it('keeps help hidden initially and provides a named non-submitting question button', () => {
 const wrapper = open(), button = wrapper.get('button')
 expect(button.text()).toBe('?')
 expect(button.attributes('type')).toBe('button')
 expect(button.attributes('aria-label')).toBe('Пояснение: Сроки')
 expect(button.attributes('aria-describedby')).toBeUndefined()
 expect(tip()).toBeNull()
 expect(wrapper.text()).not.toContain('Паузы учитываются отдельно.')
})

it('opens on hover and stays readable while the pointer moves onto the explanation', async () => {
 vi.useFakeTimers()
 const wrapper = open(), button = wrapper.get('button')
 await button.trigger('mouseenter'); await flushPromises()
 expect(tip()?.textContent).toBe('Паузы учитываются отдельно.')
 expect(button.attributes('aria-describedby')).toBe(tip()?.id)
 await button.trigger('mouseleave')
 tip()!.dispatchEvent(new MouseEvent('mouseenter'))
 await vi.advanceTimersByTimeAsync(200)
 expect(tip()).not.toBeNull()
 tip()!.dispatchEvent(new MouseEvent('mouseleave'))
 await vi.advanceTimersByTimeAsync(200)
 expect(tip()).toBeNull()
})

it('supports keyboard focus and Escape without immediately reopening', async () => {
 const wrapper = open(), button = wrapper.get('button')
 await button.trigger('focus'); await flushPromises()
 expect(tip()).not.toBeNull()
 document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
 await flushPromises()
 expect(tip()).toBeNull()
 expect(button.attributes('aria-describedby')).toBeUndefined()
 await button.trigger('blur'); await button.trigger('focus'); await flushPromises()
 expect(tip()).not.toBeNull()
})

it('pins on a tap, closes on a second tap or an outside press', async () => {
 vi.useFakeTimers()
 const wrapper = open(), button = wrapper.get('button')
 await button.trigger('click'); await button.trigger('mouseleave'); await vi.advanceTimersByTimeAsync(200)
 expect(tip()).not.toBeNull()
 await button.trigger('click'); await flushPromises()
 expect(tip()).toBeNull()
 await button.trigger('click'); await flushPromises()
 document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
 await flushPromises()
 expect(tip()).toBeNull()
})

it('keeps the popup within a narrow viewport when the button is near its bottom-right corner', async () => {
 vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(360)
 vi.spyOn(window, 'innerHeight', 'get').mockReturnValue(240)
 vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
  return (this.tagName === 'BUTTON' ? { left: 330, right: 350, top: 210, bottom: 230, width: 20, height: 20 } : { left: 0, right: 320, top: 0, bottom: 120, width: 320, height: 120 }) as DOMRect
 })
 const wrapper = open()
 await wrapper.get('button').trigger('mouseenter'); await flushPromises()
 const popup = tip()!
 expect(parseFloat(popup.style.left)).toBeGreaterThanOrEqual(12)
 expect(parseFloat(popup.style.left) + 320).toBeLessThanOrEqual(348)
 expect(parseFloat(popup.style.top)).toBeGreaterThanOrEqual(12)
 expect(parseFloat(popup.style.top) + 120).toBeLessThanOrEqual(228)
})

it('closes pinned help when keyboard focus or an assistive click moves to another control', async () => {
 const wrapper = open(), button = wrapper.get('button'), other = document.createElement('button')
 document.body.append(other)
 await button.trigger('click'); await flushPromises()
 other.dispatchEvent(new FocusEvent('focusin', { bubbles: true })); await flushPromises()
 expect(tip()).toBeNull()
 await button.trigger('click'); await flushPromises()
 other.click(); await flushPromises()
 expect(tip()).toBeNull()
})

it('uses distinct descriptions and removes its popup on unmount', async () => {
 const wrapper = mount({ components: { HelpTip }, template: '<div><HelpTip label="Сроки">О сроках</HelpTip><HelpTip label="Документы">О файлах</HelpTip></div>' }, { attachTo: document.body })
 await wrapper.findAll('button')[0]!.trigger('focus'); await wrapper.findAll('button')[1]!.trigger('focus'); await flushPromises()
 const ids = [...document.querySelectorAll('[role="tooltip"]')].map(item => item.id)
 expect(new Set(ids).size).toBe(2)
 wrapper.unmount()
 expect(tip()).toBeNull()
 window.dispatchEvent(new Event('resize'))
 document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
 expect(tip()).toBeNull()
})
