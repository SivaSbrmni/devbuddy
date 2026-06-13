/**
 * Feature Flag Admin — Phase 5.
 *
 * Admin UI for viewing and toggling AEP feature flags.
 */
import { useFlags } from '../hooks/useAepData';
import { toggleFlag } from '../api/client';

export function FeatureFlagAdmin() {
  const { flags, loading, error, refresh } = useFlags();

  const handleToggle = async (name: string, currentEnabled: boolean) => {
    await toggleFlag(name, !currentEnabled);
    refresh();
  };

  if (loading) return <div className="p-6">Loading flags...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Feature Flags</h1>
      <div className="space-y-2">
        {flags.map(flag => (
          <div key={flag.name} className="flex items-center justify-between border rounded-lg p-3">
            <div>
              <span className="font-mono text-sm">{flag.name}</span>
              <span className="ml-2 text-xs text-gray-400">Phase {flag.phase}</span>
              {flag.description && (
                <p className="text-xs text-gray-500 mt-0.5">{flag.description}</p>
              )}
            </div>
            <button
              onClick={() => handleToggle(flag.name, flag.enabled)}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                flag.enabled ? 'bg-green-500' : 'bg-gray-300'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  flag.enabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
