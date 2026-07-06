const STATUS = {
  open:        { color: '#4F46E5', bg: '#EEF2FF', border: '#C7D2FE', label: 'Open' },
  in_progress: { color: '#D97706', bg: '#FFFBEB', border: '#FDE68A', label: 'In Progress' },
  overdue:     { color: '#DC2626', bg: '#FEF2F2', border: '#FECACA', label: 'Overdue' },
  completed:   { color: '#059669', bg: '#ECFDF5', border: '#A7F3D0', label: 'Completed' },
  rejected:    { color: '#6B7280', bg: '#F9FAFB', border: '#E5E7EB', label: 'Rejected' },
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
