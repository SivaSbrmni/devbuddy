/**
 * Repository Browser — Phase 5.
 *
 * Manage registered repositories available for AEP execution.
 */
import { useState } from 'react';
import { useRepositories } from '../hooks/useAepData';
import { registerRepository, deleteRepository } from '../api/client';

export function RepositoryBrowser() {
  const { repositories, loading, error, refresh } = useRepositories();
  const [showForm, setShowForm] = useState(false);
  const [owner, setOwner] = useState('');
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await registerRepository({ owner, name });
      setOwner('');
      setName('');
      setShowForm(false);
      refresh();
    } catch {
      // Error handled by hook
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Unregister this repository?')) return;
    await deleteRepository(id);
    refresh();
  };

  if (loading) return <div className="p-6">Loading repositories...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Repositories</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Register Repository'}
        </button>
      </div>
      {showForm && (
        <form onSubmit={handleRegister} className="mb-6 p-4 border rounded-lg space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Owner (e.g. SivaSbrmni)"
              value={owner}
              onChange={e => setOwner(e.target.value)}
              className="px-3 py-2 border rounded-md"
              required
            />
            <input
              type="text"
              placeholder="Repository name"
              value={name}
              onChange={e => setName(e.target.value)}
              className="px-3 py-2 border rounded-md"
              required
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
          >
            {submitting ? 'Registering...' : 'Register'}
          </button>
        </form>
      )}
      {repositories.length === 0 ? (
        <p className="text-gray-500">No repositories registered.</p>
      ) : (
        <div className="space-y-2">
          {repositories.map(repo => (
            <div key={repo.id} className="flex items-center justify-between border rounded-lg p-3">
              <div>
                <span className="font-medium">{repo.owner}/{repo.name}</span>
                <span className="ml-2 text-xs text-gray-500">
                  {repo.provider} · {repo.default_branch}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${repo.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {repo.is_active ? 'Active' : 'Inactive'}
                </span>
                <button
                  onClick={() => handleDelete(repo.id)}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
