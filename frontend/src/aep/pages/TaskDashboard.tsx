/**
 * Task Dashboard page — Phase 5.
 *
 * Overview of all AEP executions with state, timing, and actions.
 */
import { useExecutions } from '../hooks/useAepData';
import { approveExecution, rejectExecution } from '../api/client';

const STATE_COLORS: Record<string, string> = {
  PENDING: 'bg-gray-100 text-gray-800',
  PLANNING: 'bg-blue-100 text-blue-800',
  AWAITING_APPROVAL: 'bg-yellow-100 text-yellow-800',
  EXECUTING: 'bg-purple-100 text-purple-800',
  VALIDATING: 'bg-indigo-100 text-indigo-800',
  REVIEWING: 'bg-cyan-100 text-cyan-800',
  COMPLETED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-gray-200 text-gray-600',
};

export function TaskDashboard() {
  const { executions, loading, error, refresh } = useExecutions();

  const handleApprove = async (id: string) => {
    await approveExecution(id);
    refresh();
  };

  const handleReject = async (id: string) => {
    await rejectExecution(id);
    refresh();
  };

  if (loading) return <div className="p-6">Loading executions...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Task Dashboard</h1>
        <button onClick={refresh} className="px-3 py-1 border rounded hover:bg-gray-50">
          Refresh
        </button>
      </div>
      {executions.length === 0 ? (
        <p className="text-gray-500">No executions yet. Submit a task to get started.</p>
      ) : (
        <div className="space-y-3">
          {executions.map(exec => (
            <div key={exec.id} className="border rounded-lg p-4 hover:shadow-sm">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium">{exec.title}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {exec.description?.slice(0, 120)}
                    {exec.description && exec.description.length > 120 ? '...' : ''}
                  </p>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATE_COLORS[exec.state] || 'bg-gray-100'}`}>
                  {exec.state}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
                <span>Tokens: {exec.token_input + exec.token_output}</span>
                <span>{exec.created_at ? new Date(exec.created_at).toLocaleString() : ''}</span>
              </div>
              {exec.state === 'AWAITING_APPROVAL' && (
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => handleApprove(exec.id)}
                    className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleReject(exec.id)}
                    className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                  >
                    Reject
                  </button>
                </div>
              )}
              {exec.error && (
                <p className="mt-2 text-sm text-red-600">{exec.error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
