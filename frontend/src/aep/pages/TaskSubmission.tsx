/**
 * Task Submission page — Phase 5.
 *
 * Allows users to submit a new autonomous engineering task.
 */
import { useState } from 'react';
import { submitTask, triggerPlanning } from '../api/client';
import { useRepositories } from '../hooks/useAepData';

export function TaskSubmission() {
  const { repositories } = useRepositories();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [repositoryId, setRepositoryId] = useState('');
  const [branch, setBranch] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ id: string; state: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const execution = await submitTask({
        title,
        description,
        repository_id: repositoryId || undefined,
        branch: branch || undefined,
      });
      setResult({ id: execution.id, state: execution.state });
      // Auto-trigger planning
      await triggerPlanning(execution.id);
      setResult(prev => prev ? { ...prev, state: 'PLANNING' } : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Submit Autonomous Task</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Title</label>
          <input
            type="text"
            value={title}
            onChange={e => setTitle(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
            placeholder="Brief title for the task"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            className="w-full px-3 py-2 border rounded-md h-32"
            placeholder="Detailed description of what you want done..."
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Repository (optional)</label>
          <select
            value={repositoryId}
            onChange={e => setRepositoryId(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
          >
            <option value="">-- Select repository --</option>
            {repositories.map(repo => (
              <option key={repo.id} value={repo.id}>
                {repo.owner}/{repo.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Branch (optional)</label>
          <input
            type="text"
            value={branch}
            onChange={e => setBranch(e.target.value)}
            className="w-full px-3 py-2 border rounded-md"
            placeholder="main"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !title || !description}
          className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? 'Submitting...' : 'Submit Task'}
        </button>
      </form>
      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md">
          <p className="font-medium">Task submitted successfully!</p>
          <p className="text-sm text-gray-600">
            ID: {result.id} | State: {result.state}
          </p>
        </div>
      )}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-700">{error}</p>
        </div>
      )}
    </div>
  );
}
