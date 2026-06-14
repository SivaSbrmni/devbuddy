/**
 * AEP Router — Phase 5.
 *
 * Provides the React Router configuration for the AEP module.
 * Mount this inside the main app router under /aep/* when the
 * `autonomous_ui_enabled` flag is active.
 */
import { Route, Routes, NavLink, Navigate } from 'react-router-dom';
import { TaskSubmission } from './pages/TaskSubmission';
import { TaskDashboard } from './pages/TaskDashboard';
import { RepositoryBrowser } from './pages/RepositoryBrowser';
import { AgentActivityFeed } from './pages/AgentActivityFeed';
import { ApprovalGate } from './pages/ApprovalGate';
import { FeatureFlagAdmin } from './pages/FeatureFlagAdmin';
import { ExecutionTimeline } from './pages/ExecutionTimeline';
import { WorkflowGraph } from './pages/WorkflowGraph';
import { LiveLogViewer } from './pages/LiveLogViewer';
import { DiffViewer } from './pages/DiffViewer';
import { MemoryInspector } from './pages/MemoryInspector';
import { ReasoningTrace } from './pages/ReasoningTrace';

const NAV_ITEMS = [
  { path: 'dashboard', label: 'Dashboard' },
  { path: 'submit', label: 'New Task' },
  { path: 'approvals', label: 'Approvals' },
  { path: 'repositories', label: 'Repos' },
  { path: 'activity', label: 'Activity' },
  { path: 'memory', label: 'Memory' },
  { path: 'flags', label: 'Flags' },
];

export function AepRouter() {
  return (
    <div className="flex h-full">
      {/* Sidebar Navigation */}
      <nav className="w-48 border-r bg-gray-50 p-4 space-y-1">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          AEP
        </h2>
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `block px-3 py-1.5 rounded text-sm ${
                isActive ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        <Routes>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<TaskDashboard />} />
          <Route path="submit" element={<TaskSubmission />} />
          <Route path="approvals" element={<ApprovalGate />} />
          <Route path="repositories" element={<RepositoryBrowser />} />
          <Route path="activity" element={<AgentActivityFeed />} />
          <Route path="memory" element={<MemoryInspector />} />
          <Route path="flags" element={<FeatureFlagAdmin />} />
          <Route path="executions/:id" element={<ExecutionDetailRoutes />} />
          <Route path="executions/:id/timeline" element={<ExecutionDetailRoutes />} />
          <Route path="executions/:id/graph" element={<ExecutionDetailRoutes />} />
          <Route path="executions/:id/logs" element={<ExecutionDetailRoutes />} />
          <Route path="executions/:id/diff" element={<ExecutionDetailRoutes />} />
          <Route path="executions/:id/trace" element={<ExecutionDetailRoutes />} />
        </Routes>
      </div>
    </div>
  );
}

/**
 * Execution detail sub-routes with tab navigation.
 */
function ExecutionDetailRoutes() {
  // Extract execution ID from URL
  const pathParts = window.location.pathname.split('/');
  const execIdx = pathParts.indexOf('executions');
  const executionId = execIdx >= 0 ? pathParts[execIdx + 1] : '';
  const activeTab = pathParts[execIdx + 2] || 'timeline';

  const tabs = [
    { key: 'timeline', label: 'Timeline' },
    { key: 'graph', label: 'Workflow' },
    { key: 'logs', label: 'Logs' },
    { key: 'diff', label: 'Diffs' },
    { key: 'trace', label: 'Trace' },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar */}
      <div className="border-b px-6 pt-4">
        <div className="flex gap-4">
          {tabs.map(tab => (
            <NavLink
              key={tab.key}
              to={`/aep/executions/${executionId}/${tab.key}`}
              className={`pb-2 text-sm border-b-2 ${
                activeTab === tab.key
                  ? 'border-blue-500 text-blue-600 font-medium'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </NavLink>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'timeline' && <ExecutionTimeline executionId={executionId} />}
        {activeTab === 'graph' && <WorkflowGraph executionId={executionId} />}
        {activeTab === 'logs' && <LiveLogViewer executionId={executionId} />}
        {activeTab === 'diff' && <DiffViewer executionId={executionId} />}
        {activeTab === 'trace' && <ReasoningTrace executionId={executionId} />}
      </div>
    </div>
  );
}
