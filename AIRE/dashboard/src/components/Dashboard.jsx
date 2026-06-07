import React from 'react';
import ReliabilityScore from './ReliabilityScore';
import RootCausePanel from './RootCausePanel';
import CostInsights from './CostInsights';
import AgentComparison from './AgentComparison';

export default function Dashboard() {
  return (
    <div className="dashboard">
      <ReliabilityScore />
      <RootCausePanel />
      <CostInsights />
      <AgentComparison />
    </div>
  );
}
