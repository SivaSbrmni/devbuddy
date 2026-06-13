/**
 * AEP Frontend Module — Phase 5.
 *
 * Mountable, isolated from existing pages. Gated behind the
 * `autonomous_ui_enabled` feature flag on the backend.
 *
 * Required views (spec §9.1):
 *   TaskSubmission, TaskDashboard, WorkflowGraph, ExecutionTimeline,
 *   LiveLogViewer, DiffViewer, RepositoryBrowser, PRPreview,
 *   MemoryInspector, AgentActivityFeed, ReasoningTrace, ApprovalGateUI.
 */
export { TaskSubmission } from './pages/TaskSubmission';
export { TaskDashboard } from './pages/TaskDashboard';
export { RepositoryBrowser } from './pages/RepositoryBrowser';
export { AgentActivityFeed } from './pages/AgentActivityFeed';
export { ApprovalGate } from './pages/ApprovalGate';
export { FeatureFlagAdmin } from './pages/FeatureFlagAdmin';

// Re-export API client and hooks
export * as aepApi from './api/client';
export * from './hooks/useAepData';
