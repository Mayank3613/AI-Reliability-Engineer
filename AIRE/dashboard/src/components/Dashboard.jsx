import React from 'react';
import ReliabilityScore from './ReliabilityScore';
import RootCausePanel from './RootCausePanel';
import CostInsights from './CostInsights';
import AgentComparison from './AgentComparison';
import Recommendations from './Recommendations';

const overviewCards = [
  { label: 'Active agents', value: '4', detail: 'Telemetry live' },
  { label: 'Average reliability', value: '87%', detail: 'Up 6% from last hour' },
  { label: 'Cost forecast', value: '$18.6k', detail: 'Projected monthly spend' },
  { label: 'Open incidents', value: '2', detail: 'Critical root causes' },
];

const reliability = {
  score: 88,
  grade: 'B+',
  trend: '+6%',
  risk: 'LOW',
  summary:
    'All agents remain stable with strong success rates. A few latency spikes from upstream tool calls are being monitored.',
};

const causes = [
  {
    title: 'Tool call latency spikes',
    detail: 'Search and ticket lookup API calls are introducing variability under peak load.',
    severity: 'Medium',
  },
  {
    title: 'Inconsistent model prompts',
    detail: 'Some agent contexts lack structured tool instructions, causing response drift.',
    severity: 'Low',
  },
  {
    title: 'Retry storm from timeout handling',
    detail: 'Agents are issuing repeated retries for transient failures instead of backoff.',
    severity: 'High',
  },
];

const costMetrics = [
  { label: 'Current spend', value: '$6,780', progress: 72, color: '#5ba4f7' },
  { label: 'Model optimization', value: '$4,120', progress: 46, color: '#36d6b3' },
  { label: 'Potential savings', value: '$3,100', progress: 28, color: '#ffb020' },
];

const agents = [
  { name: 'customer-support-agent', score: 92, health: 'Excellent', spend: '$3,120' },
  { name: 'coding-agent', score: 86, health: 'Good', spend: '$2,280' },
  { name: 'research-agent', score: 81, health: 'Fair', spend: '$4,180' },
  { name: 'enterprise-agent', score: 81, health: 'Fair', spend: '$3,110' },
];

const recommendations = [
  {
    title: 'Shift next-gen requests to flash model tier',
    tag: 'Cost',
  },
  {
    title: 'Add adaptive backoff for retry loops',
    tag: 'Reliability',
  },
  {
    title: 'Standardize tool prompt templates',
    tag: 'Quality',
  },
];

export default function Dashboard() {
  return (
    <div className="dashboard-layout">
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
            <div key={card.label} className="metric-card">
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
