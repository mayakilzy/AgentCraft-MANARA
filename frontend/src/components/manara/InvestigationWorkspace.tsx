/* ============================================================
   MANARA — Investigation Workspace (Page 02)
   Intelligence Observatory — dark analytical surface
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import { manaraApiExt, type WorkflowResponse, type EvidenceItem, type ClaimItem, type EdgeItem } from './api-client';
import { Loader2, AlertCircle, ChevronRight, Network, FileText, MessageSquare } from 'lucide-react';

const FSM_STATES = [
  'received', 'scoped', 'coverage_checked', 'building_capabilities',
  'mold_ready', 'acquiring', 'normalizing', 'evidencing',
  'forecasting_or_scenarios', 'drafting', 'verification',
  'deliverable_ready', 'archived',
] as const;

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

export function InvestigationWorkspace({ investigationId }: { investigationId: string }) {
  const { t } = useLanguage();
  const [workflow, setWorkflow] = React.useState<WorkflowResponse | null>(null);
  const [evidence, setEvidence] = React.useState<EvidenceItem[]>([]);
  const [claims, setClaims] = React.useState<ClaimItem[]>([]);
  const [edges, setEdges] = React.useState<EdgeItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [transitioning, setTransitioning] = React.useState(false);

  // Poll workflow every 5 seconds
  React.useEffect(() => {
    if (!investigationId) return;
    let cancelled = false;

    const loadData = async () => {
      try {
        const [wf, ev, cl, ed] = await Promise.all([
          manaraApiExt.workflow(investigationId),
          manaraApiExt.evidence(investigationId).catch(() => []),
          manaraApiExt.claims(investigationId).catch(() => []),
          manaraApiExt.edges(investigationId).catch(() => []),
        ]);
        if (!cancelled) {
          setWorkflow(wf);
          setEvidence(ev);
          setClaims(cl);
          setEdges(ed);
          setLoading(false);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setLoading(false);
          setError(e instanceof Error ? e.message : 'Failed to load investigation');
        }
      }
    };

    loadData();
    const interval = setInterval(loadData, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [investigationId]);

  const handleTransition = async (targetState: string) => {
    if (!investigationId || transitioning) return;
    setTransitioning(true);
    try {
      const result = await manaraApiExt.transition(investigationId, targetState);
      if (!result.transitioned && result.blocker) {
        setError(`Transition blocked: ${result.blocker}`);
      }
      // Refresh workflow
      const wf = await manaraApiExt.workflow(investigationId);
      setWorkflow(wf);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Transition failed');
    } finally {
      setTransitioning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="size-8 animate-spin text-[var(--manara-teal)]" />
        <span className="ml-3 text-[var(--manara-ink-muted)]">Loading investigation...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertCircle className="size-8 text-[var(--manara-error)]" />
        <p className="text-[var(--manara-error)]">{error}</p>
        <button onClick={() => window.location.reload()} className="px-4 py-2 rounded-lg bg-[var(--manara-teal)] text-white">
          Retry
        </button>
      </div>
    );
  }

  const currentState = workflow?.state || 'unknown';
  const currentStateIndex = FSM_STATES.indexOf(currentState as typeof FSM_STATES[number]);
  const nextState = currentStateIndex >= 0 && currentStateIndex < FSM_STATES.length - 1
    ? FSM_STATES[currentStateIndex + 1] : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-[22px] font-semibold text-[var(--manara-ink)]">
            {t('nav.workspace')}
          </h2>
          <p className="text-[13px] text-[var(--manara-ink-muted)] font-mono">
            {investigationId}
          </p>
        </div>
        {workflow?.blocker && (
          <div className="px-3 py-1.5 rounded-lg bg-red-50 border border-red-200 text-[12px] text-red-700">
            ⚠ {workflow.blocker}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-4">
        {/* Left: 13-state FSM stepper */}
        <div className="rounded-[12px] bg-[var(--manara-ink)] p-4 text-white">
          <h3 className="text-[11px] uppercase tracking-wider text-white/50 mb-3">Workflow States</h3>
          <div className="space-y-1">
            {FSM_STATES.map((state, i) => {
              const isCurrent = state === currentState;
              const isPast = i < currentStateIndex;
              return (
                <div
                  key={state}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-[12px] transition-colors ${
                    isCurrent ? 'bg-[var(--manara-teal)] text-white' :
                    isPast ? 'text-white/60' : 'text-white/30'
                  }`}
                >
                  <div className={`size-2 rounded-full ${isCurrent ? 'bg-white' : isPast ? 'bg-white/40' : 'bg-white/15'}`} />
                  <span className="font-mono">{state}</span>
                  {isCurrent && <ChevronRight className="size-3 ml-auto" />}
                </div>
              );
            })}
          </div>
          {nextState && currentState !== 'archived' && (
            <button
              onClick={() => handleTransition(nextState)}
              disabled={transitioning}
              className="w-full mt-3 px-3 py-2 rounded-lg bg-[var(--manara-teal)] text-white text-[12px] font-medium disabled:opacity-50"
            >
              {transitioning ? 'Transitioning...' : `Advance to ${nextState}`}
            </button>
          )}
        </div>

        {/* Center: Evidence + Claims */}
        <div className="space-y-4">
          {/* Evidence */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">Evidence ({evidence.length})</h3>
            </div>
            {evidence.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">
                No evidence collected yet. Acquire evidence from the Foundry.
              </p>
            ) : (
              <div className="space-y-2">
                {evidence.map((ev) => (
                  <div key={ev.id} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-[var(--manara-mist)]/50">
                    <div className="size-2 rounded-full bg-[var(--manara-teal)]" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-mono text-[var(--manara-ink)] truncate">{ev.id}</p>
                      <p className="text-[10px] text-[var(--manara-ink-muted)]">
                        {ev.source_id} · {ev.kind} · {ev.observed_at?.split('T')[0] || 'N/A'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Claims */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">Claims ({claims.length})</h3>
            </div>
            {claims.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">
                No claims recorded yet.
              </p>
            ) : (
              <div className="space-y-2">
                {claims.map((cl) => (
                  <div key={cl.id} className="px-3 py-2 rounded-lg bg-[var(--manara-mist)]/50">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${VERDICT_COLORS[cl.verdict] || 'bg-gray-100'}`}>
                        {cl.verdict}
                      </span>
                      <span className="text-[10px] font-mono text-[var(--manara-ink-muted)]">{cl.id}</span>
                    </div>
                    <p className="text-[12px] text-[var(--manara-ink)]">{cl.statement}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Knowledge Graph */}
        <div className="rounded-[12px] bg-[var(--manara-ink)] p-4 text-white">
          <div className="flex items-center gap-2 mb-3">
            <Network className="size-4 text-[var(--manara-teal)]" />
            <h3 className="text-[14px] font-semibold">Knowledge Graph</h3>
          </div>
          {edges.length === 0 ? (
            <p className="text-[12px] text-white/40 py-4 text-center">
              No relationships recorded yet.
            </p>
          ) : (
            <div className="space-y-2">
              {/* List fallback */}
              {edges.map((edge) => (
                <div key={edge.edge_id} className="px-2 py-1.5 rounded-md bg-white/5">
                  <div className="flex items-center gap-2">
                    <div className="size-2 rounded-full" style={{ background: EDGE_COLORS[edge.relation] || '#888' }} />
                    <span className="text-[10px] font-mono text-white/70">{edge.relation}</span>
                  </div>
                  <p className="text-[10px] text-white/50 mt-0.5 font-mono">
                    {edge.claim_id} → {edge.evidence_id}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
