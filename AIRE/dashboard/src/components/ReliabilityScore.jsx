import React from 'react';

export default function ReliabilityScore({ score, grade, trend, risk, summary }) {
  const ringColor = score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--accent)' : score >= 40 ? 'var(--warning)' : 'var(--danger)';
  const ringFill = Math.min(Math.max(score, 0), 100) * 3.6;

  return (
    <section className="card reliability-panel">
      <div className="card-title">
        <h2>Reliability</h2>
        <span className="badge">Health score</span>
      </div>
      <div
        className="score-ring"
        style={{
          background: `conic-gradient(${ringColor} ${ringFill}deg, rgba(255,255,255,0.08) 0deg)`,
        }}
      >
        <div className="score-inner">
          <div className="score-value">
            <strong>{score}</strong>
            <span>out of 100</span>
          </div>
          <span className={`status-pill ${risk.toLowerCase()}`}>{risk} risk</span>
        </div>
      </div>
      <p>{summary}</p>
      <div className="band">
        <div>
          <strong>Grade</strong>
          <span>{grade}</span>
        </div>
        <div>
          <strong>Trend</strong>
          <span>{trend}</span>
        </div>
      </div>
    </section>
  );
}
