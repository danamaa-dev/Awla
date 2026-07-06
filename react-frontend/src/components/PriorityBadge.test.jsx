import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import PriorityBadge from './PriorityBadge'

describe('PriorityBadge', () => {
  it.each([
    [9.5, 'Critical'],
    [9, 'Critical'],
    [7, 'High'],
    [8.9, 'High'],
    [5, 'Medium'],
    [6.9, 'Medium'],
    [1, 'Low'],
    [4.9, 'Low'],
  ])('labels score %s as %s', (score, expected) => {
    render(<PriorityBadge score={score} />)
    expect(screen.getByText(new RegExp(expected))).toBeInTheDocument()
  })
})
