export default function PriorityBadge({ score }) {
  let color, bg, border, label

  if (score >= 9) {
    color = 'var(--danger)'; bg = 'var(--danger-bg)'; border = 'var(--danger-border)'; label = `${score} — Critical`
  } else if (score >= 7) {
    color = 'var(--warning)'; bg = 'var(--warning-bg)'; border = 'var(--warning-border)'; label = `${score} — High`
  } else if (score >= 5) {
    color = 'var(--accent-indigo)'; bg = 'var(--indigo-bg)'; border = 'var(--indigo-border)'; label = `${score} — Medium`
  } else {
    color = 'var(--success)'; bg = 'var(--success-bg)'; border = 'var(--success-border)'; label = `${score} — Low`
  }

  return (
    <span style={{
      backgroundColor: bg,
      color,
      border: `1px solid ${border}`,
      padding: '3px 10px',
      borderRadius: '6px',
      fontSize: '12px',
      fontWeight: 600,
      whiteSpace: 'nowrap',
      display: 'inline-block',
    }}>
      {label}
    </span>
  )
}
