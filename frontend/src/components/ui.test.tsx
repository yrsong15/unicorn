// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Segmented } from './ui'

afterEach(cleanup)

describe('Segmented', () => {
  const options = [{ key: 'a', label: 'Alpha' }, { key: 'b', label: 'Beta' }]

  it('marks the selected option as checked', () => {
    render(<Segmented label="Pick" value="b" onChange={() => {}} options={options} />)
    expect(screen.getByRole('radiogroup', { name: 'Pick' })).toBeTruthy()
    expect(screen.getByRole('radio', { name: 'Beta' }).getAttribute('aria-checked')).toBe('true')
    expect(screen.getByRole('radio', { name: 'Alpha' }).getAttribute('aria-checked')).toBe('false')
  })

  it('reports the clicked option', () => {
    const onChange = vi.fn()
    render(<Segmented label="Pick" value="a" onChange={onChange} options={options} />)
    fireEvent.click(screen.getByRole('radio', { name: 'Beta' }))
    expect(onChange).toHaveBeenCalledWith('b')
  })
})
