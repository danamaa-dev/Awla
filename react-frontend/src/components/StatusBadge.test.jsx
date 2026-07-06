import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it.each([
    ['open', 'Open'],
    ['in_progress', 'In Progress'],
    ['overdue', 'Overdue'],
    ['completed', 'Completed'],
    ['rejected', 'Rejected'],
  ])('renders %s as %s', (status, label) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('falls back to the open style for an unknown status instead of crashing', () => {
    render(<StatusBadge status="some_future_status" />)
    expect(screen.getByText('Open')).toBeInTheDocument()
  })
})
