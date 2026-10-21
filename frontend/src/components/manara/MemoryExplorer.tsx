/* ============================================================
   MANARA — Memory Explorer (Page 03) — CLOSURE version
   Evidence examination + audit log + bitemporal replay
   Fixes: no silent catch, full audit pagination, EN/AR, error states
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import {
  manaraApiExt,
  type DecisionItem,
  type CutoffResponse,
} from './api-client';
import {
  Loader2, AlertCircle, FileText, Gavel, Calendar,
  ChevronLeft, ChevronRight,
} from 'lucide-react';

const VERDICT_COLORS: Record<string, string> = {
  candidate: 'bg-gray-100 text-gray-600',
  supported: 'bg-green-100 text-green-700',
  contested: 'bg-amber-100 text-amber-700',
  refuted: 'bg-red-100 text-red-700',
  superseded: 'bg-gray-100 text-gray-500',
};

const EDGE_COLORS: Record<string, string> = {
  supports: '#3A8A5C',
  refutes: '#C44545',
  qualifies: '#C49445',
};

interface DataState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useAsyncData<T>(fn: () => Promise<T>, deps: unknown[]): DataState<T> {
  const [state, setState] = React.useState<DataState<T>>({ data: null, loading: true, error: null });
  React.useEffect(() => {
    let cancelled = false;
    setState(s => ({ ...s, loading: true, error: null }));
    fn()
      .then(data => { if (!cancelled) setState({ data, loading: false, error: null }); })
      .catch(e => {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : 'Failed to load';
          setState({ data: null, loading: false, error: msg });
        }
      });
    return () => { cancelled = true; };
  }, deps);
  return state;
}

const PAGE_SIZE = 25;

export function MemoryExplorer({ investigationId }: { investigationId: string }) {
  const { t } = useLanguage();
  const [verdictFilter, setVerdictFilter] = React.useState('');
  const [cutoffDate, setCutoffDate] = React.useState('');
  const [cutoffResult, setCutoffResult] = React.useState<CutoffResponse | null>(null);
  const [cutoffLoading, setCutoffLoading] = React.useState(false);
  const [cutoffError, setCutoffError] = React.useState<string | null>(null);
  const [auditPage, setAuditPage] = React.useState(0);
  const [selectedDecision, setSelectedDecision] = React.useState<DecisionItem | null>(null);

  // Each data source has its own error state — NO silent catch
  const evidenceState = useAsyncData(
    () => manaraApiExt.evidence(investigationId),
    [investigationId]
  );
  const claimsState = useAsyncData(
    () => manaraApiExt.claims(investigationId, verdictFilter || undefined),
    [investigationId, verdictFilter]
  );
  const edgesState = useAsyncData(
    () => manaraApiExt.edges(investigationId),
    [investigationId]
  );
  const decisionsState = useAsyncData(
    () => manaraApiExt.decisions(investigationId),
    [investigationId]
  );

  const handleReplay = async () => {
    if (!cutoffDate || !investigationId) return;
    setCutoffLoading(true);
    setCutoffError(null);
    try {
      const iso = new Date(cutoffDate).toISOString();
      const result = await manaraApiExt.atCutoff(investigationId, iso);
      setCutoffResult(result);
    } catch (e) {
      setCutoffError(e instanceof Error ? e.message : 'Bitemporal replay failed');
    } finally {
      setCutoffLoading(false);
    }
  };

  // Audit table pagination
  const allDecisions = decisionsState.data || [];
  const sortedDecisions = [...allDecisions].sort((a, b) => b.decided_at.localeCompare(a.decided_at));
  const totalPages = Math.ceil(sortedDecisions.length / PAGE_SIZE);
  const pagedDecisions = sortedDecisions.slice(auditPage * PAGE_SIZE, (auditPage + 1) * PAGE_SIZE);

  return (
    <div className="space-y-6">
      <h2 className="font-serif text-[22px] font-semibold text-[var(--manara-ink)]">
        {t('nav.memory')}
      </h2>
      <p className="text-[12px] text-[var(--manara-ink-muted)] font-mono">{investigationId}</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Evidence + Claims */}
        <div className="space-y-4">
          {/* Evidence */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
                {t('memory.evidence')} ({evidenceState.data?.length ?? 0})
              </h3>
            </div>
            {evidenceState.loading ? (
              <div className="flex items-center gap-2 py-4">
                <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
                <span className="text-[12px] text-[var(--manara-ink-muted)]">{t('common.loading')}</span>
              </div>
            ) : evidenceState.error ? (
              <div className="py-4">
                <AlertCircle className="size-4 text-[var(--manara-error)] mb-1" />
                <p className="text-[12px] text-[var(--manara-error)]">{evidenceState.error}</p>
              </div>
            ) : !evidenceState.data || evidenceState.data.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">{t('memory.noEvidence')}</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {evidenceState.data.map(ev => (
                  <div key={ev.id} className="px-3 py-2 rounded-lg bg-[var(--manara-mist)]/50">
                    <p className="text-[12px] font-mono text-[var(--manara-ink)]">{ev.id}</p>
                    <p className="text-[10px] text-[var(--manara-ink-muted)]">
                      {ev.source_id} · {ev.kind}
                    </p>
                    <div className="flex gap-3 text-[9px] text-[var(--manara-ink-muted)] mt-1">
                      <span>{t('memory.observed')}: {ev.observed_at?.split('T')[0] || 'N/A'}</span>
                      <span>{t('memory.ingested')}: {ev.ingested_at.split('T')[0]}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Claims with relationships */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
                {t('memory.claims')} ({claimsState.data?.length ?? 0})
              </h3>
              <select
                value={verdictFilter}
                onChange={e => setVerdictFilter(e.target.value)}
                className="ml-auto text-[11px] px-2 py-1 rounded border border-[var(--manara-mist)]"
              >
                <option value="">{t('memory.allVerdicts')}</option>
                <option value="candidate">{t('memory.candidate')}</option>
                <option value="supported">{t('memory.supported')}</option>
                <option value="contested">{t('memory.contested')}</option>
                <option value="refuted">{t('memory.refuted')}</option>
                <option value="superseded">{t('memory.superseded')}</option>
              </select>
            </div>
            {claimsState.loading ? (
              <div className="flex items-center gap-2 py-4">
                <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
                <span className="text-[12px] text-[var(--manara-ink-muted)]">{t('common.loading')}</span>
              </div>
            ) : claimsState.error ? (
              <div className="py-4">
                <AlertCircle className="size-4 text-[var(--manara-error)] mb-1" />
                <p className="text-[12px] text-[var(--manara-error)]">{claimsState.error}</p>
              </div>
            ) : !claimsState.data || claimsState.data.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">{t('memory.noClaims')}</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {claimsState.data.map(cl => {
                  const claimEdges = (edgesState.data || []).filter(e => e.claim_id === cl.id);
                  const supporting = claimEdges.filter(e => e.relation === 'supports');
                  const refuting = claimEdges.filter(e => e.relation === 'refutes');
                  const qualifying = claimEdges.filter(e => e.relation === 'qualifies');
                  return (
                    <div key={cl.id} className="px-3 py-2 rounded-lg bg-[var(--manara-mist)]/50">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${VERDICT_COLORS[cl.verdict] || 'bg-gray-100'}`}>
                          {cl.verdict}
                        </span>
                      </div>
                      <p className="text-[12px] text-[var(--manara-ink)]">{cl.statement}</p>
                      {claimEdges.length > 0 && (
                        <div className="flex gap-3 mt-1 text-[10px]">
                          <span style={{ color: EDGE_COLORS.supports }}>
                            {t('memory.supports')}: {supporting.length}
                          </span>
                          <span style={{ color: EDGE_COLORS.refutes }}>
                            {t('memory.refutes')}: {refuting.length}
                          </span>
                          <span style={{ color: EDGE_COLORS.qualifies }}>
                            {t('memory.qualifies')}: {qualifying.length}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right: Audit Log + Bitemporal Replay */}
        <div className="space-y-4">
          {/* Audit Table (OPEN-09: filterable, newest-first, pagination) */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <Gavel className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
                {t('memory.auditLog')} ({allDecisions.length})
              </h3>
            </div>
            {decisionsState.loading ? (
              <div className="flex items-center gap-2 py-4">
                <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
                <span className="text-[12px] text-[var(--manara-ink-muted)]">{t('common.loading')}</span>
              </div>
            ) : decisionsState.error ? (
              <div className="py-4">
                <AlertCircle className="size-4 text-[var(--manara-error)] mb-1" />
                <p className="text-[12px] text-[var(--manara-error)]">{decisionsState.error}</p>
              </div>
            ) : sortedDecisions.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">{t('memory.noDecisions')}</p>
            ) : (
              <>
                <div className="overflow-x-auto max-h-48 overflow-y-auto">
                  <table className="w-full text-[11px]">
                    <thead className="sticky top-0 bg-white">
                      <tr className="text-left text-[var(--manara-ink-muted)] border-b border-[var(--manara-mist)]">
                        <th className="py-1 pr-2">{t('memory.time')}</th>
                        <th className="py-1 pr-2">{t('memory.type')}</th>
                        <th className="py-1 pr-2">{t('memory.actor')}</th>
                        <th className="py-1">{t('memory.rationale')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedDecisions.map(d => (
                        <tr
                          key={d.id}
                          className="border-b border-[var(--manara-mist)]/50 cursor-pointer hover:bg-[var(--manara-mist)]/30"
                          onClick={() => setSelectedDecision(selectedDecision?.id === d.id ? null : d)}
                        >
                          <td className="py-1 pr-2 font-mono text-[10px]">{d.decided_at.split('T')[0]}</td>
                          <td className="py-1 pr-2">{d.decision_type}</td>
                          <td className="py-1 pr-2">{d.actor}</td>
                          <td className="py-1 text-[var(--manara-ink-muted)] truncate max-w-[120px]">{d.rationale}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Selected decision detail */}
                {selectedDecision && (
                  <div className="mt-2 p-2 rounded-lg bg-[var(--manara-mist)]/50 text-[11px]">
                    <p className="font-mono text-[var(--manara-teal)]">{selectedDecision.decision_type}</p>
                    <p className="text-[var(--manara-ink)] mt-1">{selectedDecision.rationale}</p>
                    {selectedDecision.evidence_id && <p className="text-[10px] text-[var(--manara-ink-muted)] mt-1">Evidence: {selectedDecision.evidence_id}</p>}
                    {selectedDecision.claim_id && <p className="text-[10px] text-[var(--manara-ink-muted)]">Claim: {selectedDecision.claim_id}</p>}
                  </div>
                )}

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between mt-2">
                    <button
                      onClick={() => setAuditPage(p => Math.max(0, p - 1))}
                      disabled={auditPage === 0}
                      className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-[var(--manara-teal)] disabled:opacity-30"
                    >
                      <ChevronLeft className="size-3" /> {t('common.prev')}
                    </button>
                    <span className="text-[10px] text-[var(--manara-ink-muted)]">
                      {t('memory.page')} {auditPage + 1} / {totalPages} · {t('memory.showing')} {pagedDecisions.length} {t('memory.of')} {sortedDecisions.length}
                    </span>
                    <button
                      onClick={() => setAuditPage(p => Math.min(totalPages - 1, p + 1))}
                      disabled={auditPage >= totalPages - 1}
                      className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-[var(--manara-teal)] disabled:opacity-30"
                    >
                      {t('common.next')} <ChevronRight className="size-3" />
                    </button>
                  </div>
                )}
                {sortedDecisions.length > PAGE_SIZE && totalPages <= 1 && (
                  <p className="text-[10px] text-[var(--manara-ink-muted)] mt-2 text-center">
                    {t('memory.showing')} {pagedDecisions.length} {t('memory.of')} {sortedDecisions.length}
                  </p>
                )}
              </>
            )}
          </div>

          {/* Bitemporal Replay (OPEN-10) */}
          <div className="rounded-[12px] bg-[var(--manara-ink)] p-4 text-white">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold">{t('memory.bitemporalReplay')}</h3>
            </div>
            <p className="text-[11px] text-white/50 mb-3">{t('memory.replayDescription')}</p>
            <div className="flex gap-2 mb-3">
              <input
                type="datetime-local"
                value={cutoffDate}
                onChange={e => setCutoffDate(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded-lg bg-white/10 text-white text-[12px] border border-white/20"
              />
              <button
                onClick={handleReplay}
                disabled={!cutoffDate || cutoffLoading}
                className="px-4 py-1.5 rounded-lg bg-[var(--manara-teal)] text-white text-[12px] font-medium disabled:opacity-50"
              >
                {cutoffLoading ? '...' : t('memory.replay')}
              </button>
            </div>
            {cutoffError && (
              <div className="mb-3 p-2 rounded-lg bg-red-500/10 text-[11px] text-red-300">
                <AlertCircle className="size-3 inline mr-1" />{cutoffError}
              </div>
            )}
            {cutoffResult && (
              <div className="p-3 rounded-lg bg-white/5">
                <p className="text-[11px] text-white/70 mb-2">
                  {t('memory.atCutoff')} {cutoffResult.cutoff.split('T')[0]}, MANARA {t('memory.knewAbout')} {cutoffResult.visible_evidence_count} {t('memory.evidenceItems')}:
                </p>
                {cutoffResult.visible_evidence.length > 0 ? (
                  <div className="space-y-1">
                    {cutoffResult.visible_evidence.map(ev => (
                      <div key={ev.id} className="text-[10px] font-mono text-white/60">
                        {ev.id} — {ev.source_id}
                        <span className="text-white/40 ml-2">
                          {t('memory.observed')}: {ev.observed_at?.split('T')[0] || 'N/A'} · {t('memory.ingested')}: {ev.ingested_at.split('T')[0]}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-white/40">{t('memory.noEvidenceAtCutoff')}</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
