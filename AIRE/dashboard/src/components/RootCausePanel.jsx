import React, { useState } from 'react';

export default function RootCausePanel({ causes }) {
  const [expanded, setExpanded] = useState(null);

  const handleTraceClick = (e, title) => {
    e.stopPropagation();
    alert(`Opening Dynatrace for root cause: ${title}`);
  };

  return (
    <section className="section-card">
      <div className="card-title">
        <h2>Root Cause Insights</h2>
        <span className="badge">Detected issues</span>
      </div>
      <div className="list-block">
        {causes.map((cause) => {
          const isExpanded = expanded === cause.title;
          
          return (
            <div 
              key={cause.title} 
              className={`list-item interactive-item ${isExpanded ? 'expanded' : ''}`}
              onClick={() => setExpanded(isExpanded ? null : cause.title)}
            >
              <div className="card-title" style={{ marginBottom: '6px' }}>
                <strong>{cause.title}</strong>
                <span className={`status-pill ${cause.severity.toLowerCase()}`}>{cause.severity}</span>
              </div>
              <p style={{ marginTop: '0', marginBottom: isExpanded ? '0' : '0' }}>{cause.detail}</p>
              
              {isExpanded && (
                <div className="expanded-content">
                  <p style={{ color: 'var(--muted)', fontSize: '0.85rem', marginBottom: '12px', marginTop: '0' }}>
                    Trace ID: <code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px' }}>dt.trace.abc123xyz</code>
                  </p>
                  <button 
                    className="action-btn secondary"
                    onClick={(e) => handleTraceClick(e, cause.title)}
                  >
                    🔍 View Trace in Dynatrace
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
