/** Placeholder shaped like RequestCard, shown while the request list is
 * loading instead of a generic spinner -- previews the content that's
 * about to arrive rather than just signaling "something is happening"
 * (audit finding L-UX1). */
export default function RequestCardSkeleton() {
  return (
    <div className="card" style={{ marginBottom: '12px' }} aria-hidden="true">
      <div className="row row-gap-3" style={{ justifyContent: 'space-between', marginBottom: '14px' }}>
        <div className="skeleton" style={{ width: '45%', height: '16px' }} />
        <div className="skeleton" style={{ width: '70px', height: '20px', borderRadius: '10px' }} />
      </div>
      <div className="skeleton" style={{ width: '85%', height: '13px', marginBottom: '8px' }} />
      <div className="skeleton" style={{ width: '60%', height: '13px' }} />
    </div>
  )
}
