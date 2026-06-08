import React from 'react';

export default function RootCausePanel({ causes }) {
  return (
    <section className="section-card">
      <div className="card-title">
        <h2>Root Cause Insights</h2>
        <span className="badge">Detected issues</span>
      </div>
      <div className="list-block">
        {causes.map((cause) => (
          <div key={cause.title} className="list-item">
            <div className="card-title">
              <strong>{cause.title}</strong>
              <span className={`status-pill ${cause.severity.toLowerCase()}`}>{cause.severity}</span>
            </div>
            <p>{cause.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
