import React from 'react';

export default function Recommendations({ items }) {
  return (
    <div className="list-block">
      {items.map((item) => (
        <div key={item.title} className="list-item">
          <div className="card-title">
            <strong>{item.title}</strong>
            <span className="recommendation-tag">{item.tag}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
