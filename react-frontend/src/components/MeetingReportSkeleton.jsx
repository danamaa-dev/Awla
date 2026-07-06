/** Placeholder shown while the request list backing the report is loading,
 * matching the loading-state treatment used on Dashboard (RequestCardSkeleton). */
export default function MeetingReportSkeleton() {
  return (
    <div aria-hidden="true">
      <div className="card" style={{ marginBottom: '14px' }}>
        <div className="skeleton" style={{ width: '30%', height: '13px', marginBottom: '18px' }} />
        <div className="skeleton" style={{ width: '90%', height: '13px', marginBottom: '10px' }} />
        <div className="skeleton" style={{ width: '75%', height: '13px' }} />
      </div>
      <div className="card">
        <div className="skeleton" style={{ width: '40%', height: '13px', marginBottom: '18px' }} />
        <div className="skeleton" style={{ width: '85%', height: '13px', marginBottom: '10px' }} />
        <div className="skeleton" style={{ width: '60%', height: '13px' }} />
      </div>
    </div>
  )
}
