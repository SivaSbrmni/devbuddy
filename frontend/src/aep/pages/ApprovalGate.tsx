/**
 * Approval Gate UI — Phase 5.
 *
 * Shows executions awaiting approval and allows operators to
 * approve or reject plans.
 */
import { useState } from 'react';
import { useExecutions } from '../hooks/useAepData';
import { approveExecution, rejectExecution, getExecution } from '../api/client';
import type { Execution } from '../api/client';

export function ApprovalGate() {
  const { executions, loading, error, refresh } = useExecutions();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const pendingApproval = executions.filter(e => e.state === 'AWAITING_APPROVAL');

  const handleApprove = async (id: string) => {
    setProcessing(true);
    try {
      await approveExecution(id);
      refresh();
      setSelectedId(null);
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async (id: string) => {
    setProcessing(true);
    try {
      await rejectExecution(id, rejectReason || undefined);
      refresh();
      setSelectedId(null);
      setRejectReason('');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) return <div className="p-6">Loading...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Approval Gate</h1>
      {pendingApproval.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg">No tasks awaiting approval</p>
          <p className="text-sm mt-1">
            Tasks will appear here when the planner produces a plan that needs human review.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {pendingApproval.map(exec => (
            <div key={exec.id} className="border rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium">{exec.title}</h3>
                  <p className="text-sm text-gray-600 mt-1">{exec.description}</p>
                </div>
                <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-medium">
                  Awaiting Approval
                </span>
              </div>
              {selectedId === exec.id ? (
                <div className="mt-4 space-y-3">
                  <textarea
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    placeholder="Rejection reason (optional)..."
                    className="w-full px-3 py-2 border rounded-md text-sm"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApprove(exec.id)}
                      disabled={processing}
                      className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                    >
                      Approve & Execute
                    </button>
                    <button
                      onClick={() => handleReject(exec.id)}
                      disabled={processing}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => setSelectedId(null)}
                      className="px-4 py-2 border rounded hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setSelectedId(exec.id)}
                  className="mt-3 px-3 py-1 border rounded text-sm hover:bg-gray-50"
                >
                  Review Plan
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
