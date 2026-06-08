import React from 'react';

export default function AgentComparison({ agents }) {
  return (
    <section className="section-card agent-comparison">
      <div className="card-title">
        <h2>Agent Comparison</h2>
        <span className="badge">Performance</span>
      </div>
      <table className="agent-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Reliability</th>
            <th>Current spend</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr key={agent.name}>
              <td>
                <strong>{agent.name}</strong>
                <span className="small-text">{agent.health}</span>
              </td>
              <td>
                <span className="score-dot" style={{ background: agent.score >= 85 ? 'var(--success)' : agent.score >= 70 ? 'var(--accent)' : 'var(--warning)' }} />
                {agent.score}%
              </td>
              <td>{agent.spend}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
