/**
 * Diff Viewer — Phase 5.
 *
 * Displays code diffs produced by the Coder agent with syntax
 * highlighting and inline annotations from the Reviewer agent.
 */
import { useEffect, useState } from 'react';

interface FileDiff {
  path: string;
  action: 'create' | 'modify' | 'delete';
  content: string;
  additions: number;
  deletions: number;
}

interface ReviewComment {
  file: string;
  line: number;
  severity: string;
  title: string;
  description: string;
}

export function DiffViewer({ executionId }: { executionId: string }) {
  const [diffs, setDiffs] = useState<FileDiff[]>([]);
  const [comments, setComments] = useState<ReviewComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedFile, setExpandedFile] = useState<string | null>(null);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_URL || '';
    const token = localStorage.getItem('auth_token');
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};

    fetch(`${apiBase}/api/v1/aep/executions/${executionId}`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          // Extract diffs from coder step results
          const steps = data.steps || [];
          const coderStep = steps.find((s: any) => s.agent_name === 'coder');
          if (coderStep?.result?.files) {
            setDiffs(coderStep.result.files.map((f: any) => ({
              ...f,
              additions: (f.content || '').split('\n').length,
              deletions: 0,
            })));
          }
          // Extract review comments
          const reviewStep = steps.find((s: any) => s.agent_name === 'reviewer');
          if (reviewStep?.result?.issues) {
            setComments(reviewStep.result.issues);
          }
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [executionId]);

  if (loading) return <div className="p-6">Loading diffs...</div>;

  const actionColors = {
    create: 'text-green-600 bg-green-50',
    modify: 'text-yellow-600 bg-yellow-50',
    delete: 'text-red-600 bg-red-50',
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Code Changes</h1>
      {diffs.length === 0 ? (
        <p className="text-gray-500">No code changes produced yet.</p>
      ) : (
        <div className="space-y-3">
          {/* Summary bar */}
          <div className="flex items-center gap-4 text-sm text-gray-500 pb-3 border-b">
            <span>{diffs.length} file{diffs.length !== 1 ? 's' : ''} changed</span>
            <span className="text-green-600">
              +{diffs.reduce((sum, d) => sum + d.additions, 0)}
            </span>
            <span className="text-red-600">
              -{diffs.reduce((sum, d) => sum + d.deletions, 0)}
            </span>
          </div>

          {/* File list */}
          {diffs.map(diff => (
            <div key={diff.path} className="border rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedFile(expandedFile === diff.path ? null : diff.path)}
                className="w-full flex items-center justify-between p-3 hover:bg-gray-50 text-left"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${actionColors[diff.action]}`}>
                    {diff.action}
                  </span>
                  <span className="font-mono text-sm">{diff.path}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {expandedFile === diff.path ? '▼' : '▶'}
                </span>
              </button>
              {expandedFile === diff.path && (
                <div className="border-t">
                  <pre className="p-4 bg-gray-900 text-gray-200 text-xs overflow-x-auto">
                    <code>{diff.content || '(empty)'}</code>
                  </pre>
                  {/* Inline review comments for this file */}
                  {comments
                    .filter(c => c.file === diff.path)
                    .map((comment, i) => (
                      <div key={i} className="p-3 border-t bg-yellow-50">
                        <div className="flex items-center gap-2 text-xs">
                          <span className={`font-medium ${
                            comment.severity === 'critical' ? 'text-red-600' :
                            comment.severity === 'major' ? 'text-orange-600' :
                            'text-yellow-600'
                          }`}>
                            {comment.severity}
                          </span>
                          <span className="text-gray-500">Line {comment.line}</span>
                        </div>
                        <p className="text-sm font-medium mt-1">{comment.title}</p>
                        <p className="text-xs text-gray-600 mt-0.5">{comment.description}</p>
                      </div>
                    ))
                  }
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
