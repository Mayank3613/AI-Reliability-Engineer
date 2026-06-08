import React from 'react';

export default function CostInsights({ items }) {
  return (
    <section className="section-card">
      <div className="card-title">
        <h2>Cost Insights</h2>
        <span className="badge">Forecast</span>
      </div>
      <div className="list-block">
        {items.map((item) => (
          <div key={item.label} className="list-item">
            <strong>{item.label}</strong>
            <p className="small-text">{item.value}</p>
            <div className="track">
              <div className="progress" style={{ width: `${item.progress}%`, background: item.color }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
