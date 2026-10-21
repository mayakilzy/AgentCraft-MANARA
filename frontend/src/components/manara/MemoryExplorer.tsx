/* ============================================================
   MANARA — Memory Explorer (Page 03)
   Evidence examination + audit log + bitemporal replay
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import { manaraApiExt, type EvidenceItem, type ClaimItem, type EdgeItem, type DecisionItem, type CutoffResponse } from './api-client';
import { Loader2, FileText, Gavel, Calendar } from 'lucide-react';

export function MemoryExplorer({ investigationId }: { investigationId: string }) {
  const { t } = useLanguage();
  const [evidence, setEvidence] = React.useState<EvidenceItem[]>([]);
  const [claims, setClaims] = React.useState<ClaimItem[]>([]);
  const [edges, setEdges] = React.useState<EdgeItem[]>([]);
  const [decisions, setDecisions] = React.useState<DecisionItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [, setError] = React.useState<string | null>(null);
  const [verdictFilter, setVerdictFilter] = React.useState<string>('');
  const [cutoffDate, setCutoffDate] = React.useState('');
  const [cutoffResult, setCutoffResult] = React.useState<CutoffResponse | null>(null);
  const [cutoffLoading, setCutoffLoading] = React.useState(false);

  React.useEffect(() => {
    if (!investigationId) return;
    let cancelled = false;

    const loadData = async () => {
      try {
        const [ev, cl, ed, dec] = await Promise.all([
          manaraApiExt.evidence(investigationId).catch(() => []),
          manaraApiExt.claims(investigationId, verdictFilter || undefined).catch(() => []),
          manaraApiExt.edges(investigationId).catch(() => []),
          manaraApiExt.decisions(investigationId).catch(() => []),
        ]);
        if (!cancelled) {
          setEvidence(ev);
          setClaims(cl);
          setEdges(ed);
          setDecisions(dec);
          setLoading(false);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setLoading(false);
          setError(e instanceof Error ? e.message : 'Failed to load memory');
        }
      }
    };

    loadData();
    return () => { cancelled = true; };
  }, [investigationId, verdictFilter]);

  const handleReplay = async () => {
    if (!cutoffDate || !investigationId) return;
    setCutoffLoading(true);
    try {
      const iso = new Date(cutoffDate).toISOString();
      const result = await manaraApiExt.atCutoff(investigationId, iso);
      setCutoffResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Bitemporal replay failed');
    } finally {
      setCutoffLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="size-8 animate-spin text-[var(--manara-teal)]" />
        <span className="ml-3 text-[var(--manara-ink-muted)]">Loading memory...</span>
      </div>
    );
  }

  const filteredClaims = verdictFilter ? claims.filter(c => c.verdict === verdictFilter) : claims;
  const sortedDecisions = [...decisions].sort((a, b) => b.decided_at.localeCompare(a.decided_at));

  return (
    <div className="space-y-6">
      <h2 className="font-serif text-[22px] font-semibold text-[var(--manara-ink)]">
        {t('nav.memory')}
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Evidence + Claims */}
        <div className="space-y-4">
          {/* Evidence */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">Evidence ({evidence.length})</h3>
            </div>
            {evidence.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">No evidence in this investigation.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {evidence.map((ev) => (
                  <div key={ev.id} className="px-3 py-2 rounded-lg bg-[var(--manara-mist)]/50">
                    <p className="text-[12px] font-mono text-[var(--manara-ink)]">{ev.id}</p>
                    <p className="text-[10px] text-[var(--manara-ink-muted)]">
                      {ev.source_id} · {ev.kind} · observed: {ev.observed_at?.split('T')[0] || 'N/A'} · ingested: {ev.ingested_at.split('T')[0]}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Claims with relationships */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">Claims ({filteredClaims.length})</h3>
              <select
                value={verdictFilter}
                onChange={(e) => setVerdictFilter(e.target.value)}
                className="ml-auto text-[11px] px-2 py-1 rounded border border-[var(--manara-mist)]"
              >
                <option value="">All verdicts</option>
                <option value="candidate">Candidate</option>
                <option value="supported">Supported</option>
                <option value="contested">Contested</option>
                <option value="refuted">Refuted</option>
                <option value="superseded">Superseded</option>
              </select>
            </div>
            {filteredClaims.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">No claims found.</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {filteredClaims.map((cl) => {
                  const claimEdges = edges.filter(e => e.claim_id === cl.id);
                  const supporting = claimEdges.filter(e => e.relation === 'supports');
                  const refuting = claimEdges.filter(e => e.relation === 'refutes');
                  const qualifying = claimEdges.filter(e => e.relation === 'qualifies');
                  return (
                    <div key={cl.id} className="px-3 py-2 rounded-lg bg-[var(--manara-mist)]/50">
                      <p className="text-[12px] text-[var(--manara-ink)] mb-1">{cl.statement}</p>
                      <div className="flex gap-3 text-[10px]">
                        <span className="text-green-600">Supports: {supporting.length}</span>
                        <span className="text-red-600">Refutes: {refuting.length}</span>
                        <span className="text-amber-600">Qualifies: {qualifying.length}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right: Audit Log + Bitemporal Replay */}
        <div className="space-y-4">
          {/* Audit Log (OPEN-09: filterable table, newest-first) */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <Gavel className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">Audit Log ({sortedDecisions.length})</h3>
            </div>
            {sortedDecisions.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">No decisions recorded.</p>
            ) : (
              <div className="overflow-x-auto max-h-64">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="text-left text-[var(--manara-ink-muted)] border-b border-[var(--manara-mist)]">
                      <th className="py-1 pr-2">Time</th>
                      <th className="py-1 pr-2">Type</th>
                      <th className="py-1 pr-2">Actor</th>
                      <th className="py-1">Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedDecisions.slice(0, 50).map((d) => (
                      <tr key={d.id} className="border-b border-[var(--manara-mist)]/50">
                        <td className="py-1 pr-2 font-mono text-[10px]">{d.decided_at.split('T')[0]}</td>
                        <td className="py-1 pr-2">{d.decision_type}</td>
                        <td className="py-1 pr-2">{d.actor}</td>
                        <td className="py-1 text-[var(--manara-ink-muted)] truncate max-w-[120px]">{d.rationale}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {sortedDecisions.length > 50 && (
                  <p className="text-[10px] text-[var(--manara-ink-muted)] mt-2">
                    Showing 50 of {sortedDecisions.length} decisions. Client-side pagination.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Bitemporal Replay (OPEN-10: date-time picker + explicit Replay) */}
          <div className="rounded-[12px] bg-[var(--manara-ink)] p-4 text-white">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold">Bitemporal Replay</h3>
            </div>
            <p className="text-[11px] text-white/50 mb-3">
              See what MANARA knew at a specific point in time.
            </p>
            <div className="flex gap-2 mb-3">
              <input
                type="datetime-local"
                value={cutoffDate}
                onChange={(e) => setCutoffDate(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded-lg bg-white/10 text-white text-[12px] border border-white/20"
              />
              <button
                onClick={handleReplay}
                disabled={!cutoffDate || cutoffLoading}
                className="px-4 py-1.5 rounded-lg bg-[var(--manara-teal)] text-white text-[12px] font-medium disabled:opacity-50"
              >
                {cutoffLoading ? 'Replaying...' : 'Replay'}
              </button>
            </div>
            {cutoffResult && (
              <div className="mt-3 p-3 rounded-lg bg-white/5">
                <p className="text-[11px] text-white/70 mb-2">
                  At {cutoffResult.cutoff.split('T')[0]}, MANARA knew about {cutoffResult.visible_evidence_count} evidence item(s):
                </p>
                {cutoffResult.visible_evidence.length > 0 ? (
                  <div className="space-y-1">
                    {cutoffResult.visible_evidence.map((ev) => (
                      <div key={ev.id} className="text-[10px] font-mono text-white/60">
                        {ev.id} — {ev.source_id} — observed: {ev.observed_at?.split('T')[0] || 'N/A'}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-white/40">No evidence was visible at this cutoff.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
