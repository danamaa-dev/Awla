import {
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = ['#4F46E5', '#059669', '#D97706', '#DC2626', '#6B7280']

const tooltipStyle = {
  contentStyle: { backgroundColor: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: '8px', color: '#111827' },
  labelStyle: { color: '#111827' },
  itemStyle: { color: '#6B7280' },
}

function Chart({ chartType, data, groupBy, metric }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ textAlign: 'center', color: '#6B7280', padding: '40px 0', fontSize: '14px' }}>
        No chart data available.
      </div>
    )
  }

  if (chartType === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey={metric}
            nameKey={groupBy}
            cx="50%" cy="50%"
            outerRadius={100}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            labelLine={{ stroke: '#9CA3AF' }}
          >
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ color: '#6B7280', fontSize: '12px' }} />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (chartType === 'line') {
    return (
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey={groupBy} tick={{ fill: '#6B7280', fontSize: 12 }} />
          <YAxis tick={{ fill: '#6B7280', fontSize: 12 }} />
          <Tooltip {...tooltipStyle} />
          <Line type="monotone" dataKey={metric} stroke="#4F46E5" strokeWidth={2}
            dot={{ fill: '#4F46E5', r: 4 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
        <XAxis dataKey={groupBy} tick={{ fill: '#6B7280', fontSize: 12 }} />
        <YAxis tick={{ fill: '#6B7280', fontSize: 12 }} />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey={metric} fill="#4F46E5" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function ExecutionModal({ result, onClose }) {
  const columns = result.data && result.data.length > 0 ? Object.keys(result.data[0]) : []

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        backgroundColor: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '24px',
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        backgroundColor: '#FFFFFF',
        border: '1px solid #E5E7EB',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '820px',
        maxHeight: '88vh',
        overflowY: 'auto',
        padding: '28px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h2 style={{ color: '#111827', fontSize: '18px', fontWeight: 700, margin: 0 }}>
              {result.report_title || 'Dashboard'}
            </h2>
            <div style={{ fontSize: '12px', color: '#6B7280', marginTop: '4px' }}>
              {result.data?.length ?? 0} rows · {result.chart_type} chart
            </div>
          </div>
          <button onClick={onClose} className="btn-secondary" style={{ padding: '7px 14px', fontSize: '13px' }}>
            Close
          </button>
        </div>

        <Chart
          chartType={result.chart_type}
          data={result.data}
          groupBy={result.group_by}
          metric={result.metric}
        />

        {result.summary && (
          <div style={{
            marginTop: '20px',
            backgroundColor: '#F9FAFB',
            border: '1px solid #E5E7EB',
            borderRadius: '8px',
            padding: '16px',
          }}>
            <div style={{ color: '#6B7280', fontSize: '12px', fontWeight: 500, marginBottom: '8px' }}>Summary</div>
            <p style={{ color: '#111827', fontSize: '14px', lineHeight: 1.7, margin: 0 }}>
              {result.summary}
            </p>
          </div>
        )}

        {columns.length > 0 && (
          <div style={{ marginTop: '20px', overflowX: 'auto' }}>
            <div style={{ color: '#6B7280', fontSize: '12px', fontWeight: 500, marginBottom: '8px' }}>Data</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#F9FAFB' }}>
                  {columns.map(col => (
                    <th key={col} style={{
                      padding: '8px 14px', textAlign: 'left',
                      color: '#374151', borderBottom: '1px solid #E5E7EB',
                      fontWeight: 600, whiteSpace: 'nowrap',
                    }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.data.map((row, i) => (
                  <tr key={i} style={{ backgroundColor: i % 2 === 0 ? '#FFFFFF' : '#F9FAFB' }}>
                    {columns.map(col => (
                      <td key={col} style={{
                        padding: '8px 14px', color: '#111827',
                        borderBottom: '1px solid #E5E7EB',
                      }}>
                        {row[col] ?? '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
