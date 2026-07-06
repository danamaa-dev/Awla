const STATUS = {
  open:        { color: 'var(--accent-indigo)', bg: 'var(--indigo-bg)', border: 'var(--indigo-border)', label: 'Open' },
  in_progress: { color: 'var(--warning)', bg: 'var(--warning-bg)', border: 'var(--warning-border)', label: 'In Progress' },
  overdue:     { color: 'var(--danger)', bg: 'var(--danger-bg)', border: 'var(--danger-border)', label: 'Overdue' },
  completed:   { color: 'var(--success)', bg: 'var(--success-bg)', border: 'var(--success-border)', label: 'Completed' },
  rejected:    { color: 'var(--text-dim)', bg: 'var(--surface-2)', border: 'var(--border)', label: 'Rejected' },
}

export default function StatusBadge({ status }) {
  const { color, bg, border, label } = STATUS[status] || STATUS.open

  return (
    <span style={{
      backgroundColor: bg,
      color,
      border: `1px solid ${border}`,
      padding: '2px 8px',
      borderRadius: '5px',
      fontSize: '12px',
      fontWeight: 500,
      display: 'inline-block',
    }}>
      {label}
    </span>
  )
}
