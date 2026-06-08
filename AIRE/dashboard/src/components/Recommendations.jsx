import React, { useState } from 'react';

export default function Recommendations({ items }) {
  const [expanded, setExpanded] = useState(null);
  const [applied, setApplied] = useState({});

  const handleApply = (e, title) => {
    e.stopPropagation();
    setApplied(prev => ({ ...prev, [title]: true }));
    setTimeout(() => {
      alert(`Fix applied! Background deployment started for: ${title}`);
    }, 500);
  };

  return (
    <div className="list-block">
      {items.map((item) => {
        const isExpanded = expanded === item.title;
        const isApplied = applied[item.title];
        
        return (
          <div 
            key={item.title} 
            className={`list-item interactive-item ${isExpanded ? 'expanded' : ''}`}
            onClick={() => setExpanded(isExpanded ? null : item.title)}
          >
            <div className="card-title" style={{ marginBottom: isExpanded ? '0' : '18px' }}>
              <strong>{item.title}</strong>
              <span className="recommendation-tag">{item.tag}</span>
            </div>
            
            {isExpanded && (
              <div className="expanded-content">
                <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '16px', marginTop: '0' }}>
                  Simulated Impact: <strong style={{ color: 'var(--success)' }}>+24 reliability</strong>, <strong style={{ color: 'var(--success)' }}>-12% tokens</strong>.<br/>
                  Grounded in: <em>reliability-playbooks-v3.md</em>
                </p>
                <button 
                  className={`action-btn ${isApplied ? 'secondary' : ''}`}
                  onClick={(e) => handleApply(e, item.title)}
                  disabled={isApplied}
                >
                  {isApplied ? '✓ Fix Applied' : '⚡ Apply Fix'}
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
