import React, { useState, useEffect } from 'react';
import ReliabilityScore from './ReliabilityScore';
import RootCausePanel from './RootCausePanel';
import CostInsights from './CostInsights';
import AgentComparison from './AgentComparison';
import Recommendations from './Recommendations';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      const response = await fetch('http://localhost:8080/api/v1/dashboard/data');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const json = await response.json();
      setData(json);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError('Connection to AIRE backend failed. Retrying...');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000); // poll every 8 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="loading-container">
        <div className="loader"></div>
        <p>Connecting to AIRE telemetry backend...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="error-container">
        <div className="loader" style={{ animation: 'none', borderTopColor: 'var(--danger)' }}></div>
        <h2>Connection Failed</h2>
        <p>{error}</p>
        <button onClick={() => { setLoading(true); fetchData(); }} className="action-btn" style={{ marginTop: '16px' }}>
          Retry Connection
        </button>
      </div>
    );
  }

  // Use state variables from backend response
  const { overviewCards, reliability, recommendations, causes, costMetrics, agents } = data;

  return (
    <div className="dashboard-layout">
      {/* Premium Gemini-style Navigation */}
      <header className="navbar" style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 0 24px 0',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        marginBottom: '40px'
      }}>
        <div className="nav-brand" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div className="brand-logo" style={{
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            background: 'var(--gemini-gradient)',
            boxShadow: '0 0 15px rgba(139, 92, 246, 0.4)'
          }}></div>
          <span style={{
            fontFamily: 'Outfit, sans-serif',
            fontWeight: 800,
            fontSize: '1.35rem',
            letterSpacing: '-0.03em',
            background: 'linear-gradient(90deg, #fff, #c084fc)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>AIRE</span>
        </div>
        <div className="nav-status" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '0.8rem',
          color: '#34d399',
          background: 'rgba(16, 185, 129, 0.06)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          padding: '6px 14px',
          borderRadius: '100px',
          fontWeight: 600
        }}>
          <span className="pulse-dot" style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: '#10b981',
            boxShadow: '0 0 8px #10b981'
          }}></span>
          Telemetry Live
        </div>
      </header>

      {error && (
        <div style={{
          background: 'rgba(255, 107, 107, 0.15)',
          border: '1px solid var(--danger)',
          padding: '12px 24px',
          borderRadius: '12px',
          marginBottom: '24px',
          color: '#fb7185',
          fontSize: '0.9rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>⚠️ {error}</span>
          <button onClick={fetchData} className="action-btn secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>Reconnect</button>
        </div>
      )}
      <div className="dashboard-header">
        <div className="hero">
          <p className="badge">AIRE Control Center</p>
          <h1>AI agent reliability made visible.</h1>
          <p>
            Review live telemetry, root cause insights, cost forecasts, and recommendation actions across your
            deployed AI agents.
          </p>
        </div>
        <div className="metric-grid">
          {overviewCards.map((card) => (
            <div key={card.label} className="metric-card interactive-card" onClick={fetchData}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <p>{card.detail}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="dashboard-grid">
        <ReliabilityScore {...reliability} />
        <div className="section-card">
          <div className="card-title">
            <h2>Top recommendations</h2>
            <span className="badge">Action items</span>
          </div>
          <Recommendations items={recommendations} />
        </div>
      </div>

      <div className="section-row">
        <RootCausePanel causes={causes} />
        <CostInsights items={costMetrics} />
      </div>

      <div className="section-row">
        <AgentComparison agents={agents} />
      </div>
    </div>
  );
}
