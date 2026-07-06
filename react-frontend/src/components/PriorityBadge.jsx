export default function PriorityBadge({ score }) {
  let color, bg, border, label

  if (score >= 9) {
    color = '#DC2626'; bg = '#FEF2F2'; border = '#FECACA'; label = `${score} — Critical`
  } else if (score >= 7) {
    color = '#D97706'; bg = '#FFFBEB'; border = '#FDE68A'; label = `${score} — High`
  } else if (score >= 5) {
    color = '#4F46E5'; bg = '#EEF2FF'; border = '#C7D2FE'; label = `${score} — Medium`
  } else {
    color = '#059669'; bg = '#ECFDF5'; border = '#A7F3D0'; label = `${score} — Low`
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
