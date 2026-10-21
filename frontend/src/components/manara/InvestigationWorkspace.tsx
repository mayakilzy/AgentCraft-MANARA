/* ============================================================
   MANARA — Investigation Workspace (Page 02) — CLOSURE version
   Intelligence Observatory — dark analytical surface
   Fixes: no silent catch, interactive graph, investigation selector,
   full EN/AR, proper error states
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import {
  manaraApiExt,
  type WorkflowResponse,
  type EvidenceItem,
  type ClaimItem,
  type EdgeItem,
  type InvestigationSummary,
} from './api-client';
import {
  Loader2, AlertCircle, ChevronRight, Network, FileText,
  MessageSquare, RefreshCw, List, Maximize2,
} from 'lucide-react';

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

/* ============================================================
   Interactive Knowledge Graph — SVG with zoom/pan
   ============================================================ */
function KnowledgeGraph({ edges, claims, evidence }: {
  edges: EdgeItem[];
  claims: ClaimItem[];
  evidence: EvidenceItem[];
}) {
  const { t } = useLanguage();
  const [showList, setShowList] = React.useState(false);
  const [selectedNode, setSelectedNode] = React.useState<string | null>(null);
  const [zoom, setZoom] = React.useState(1);
  const [pan, setPan] = React.useState({ x: 0, y: 0 });
  const svgRef = React.useRef<SVGSVGElement>(null);
  const isDragging = React.useRef(false);
  const lastPos = React.useRef({ x: 0, y: 0 });

  // Build nodes from claims + evidence
  const nodes = React.useMemo(() => {
    const claimNodes = claims.map((c, i) => ({
      id: c.id,
      type: 'claim',
      label: c.statement.slice(0, 40) + (c.statement.length > 40 ? '…' : ''),
      verdict: c.verdict,
      x: 200 + Math.cos((i / claims.length) * 2 * Math.PI) * 120,
      y: 150 + Math.sin((i / claims.length) * 2 * Math.PI) * 120,
    }));
    const evIds = new Set(edges.map(e => e.evidence_id));
    const evidenceNodes: typeof claimNodes = Array.from(evIds).map((id, i) => {
      const ev = evidence.find(e => e.id === id);
      return {
        id,
        type: 'evidence',
        label: ev ? `${ev.source_id} · ${ev.kind}` : id,
        verdict: '',
        x: 400 + Math.cos((i / evIds.size) * 2 * Math.PI) * 100,
        y: 150 + Math.sin((i / evIds.size) * 2 * Math.PI) * 100,
      };
    });
    return [...claimNodes, ...evidenceNodes];
  }, [claims, evidence, edges]);

  const handleMouseDown = (e: React.MouseEvent) => {
    isDragging.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    setPan(p => ({ x: p.x + dx, y: p.y + dy }));
    lastPos.current = { x: e.clientX, y: e.clientY };
  };
  const handleMouseUp = () => { isDragging.current = false; };
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.3, Math.min(3, z * delta)));
  };

  if (edges.length === 0) {
    return (
      <div className="text-center py-8">
        <Network className="size-8 mx-auto text-white/20 mb-2" />
        <p className="text-[12px] text-white/40">
          {t('workspace.noEdges')}
        </p>
      </div>
    );
  }

  if (showList) {
    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[14px] font-semibold text-white">Relationships ({edges.length})</h3>
          <button
            onClick={() => setShowList(false)}
            className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-white/60 hover:text-white"
          >
            <Maximize2 className="size-3" /> Graph
          </button>
        </div>
        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {edges.map(edge => (
            <div
              key={edge.edge_id}
              className="px-2 py-1.5 rounded-md bg-white/5 cursor-pointer hover:bg-white/10"
              onClick={() => setSelectedNode(edge.claim_id === selectedNode ? null : edge.claim_id)}
            >
              <div className="flex items-center gap-2">
                <div className="size-2 rounded-full" style={{ background: EDGE_COLORS[edge.relation] || '#888' }} />
                <span className="text-[10px] font-mono text-white/70 uppercase">{edge.relation}</span>
                <span className="text-[10px] text-white/40">w={edge.weight}</span>
              </div>
              <p className="text-[10px] text-white/50 mt-0.5 font-mono">
                {edge.claim_id} → {edge.evidence_id}
              </p>
              {edge.notes && <p className="text-[10px] text-white/40 mt-0.5 italic">{edge.notes}</p>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[14px] font-semibold text-white">Knowledge Graph</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom(z => Math.max(0.3, z - 0.2))}
            className="px-1.5 py-0.5 rounded text-white/60 hover:text-white text-[11px]"
          >−</button>
          <span className="text-[10px] text-white/40 font-mono">{Math.round(zoom * 100)}%</span>
          <button
            onClick={() => setZoom(z => Math.min(3, z + 0.2))}
            className="px-1.5 py-0.5 rounded text-white/60 hover:text-white text-[11px]"
          >+</button>
          <button
            onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
            className="px-1.5 py-0.5 rounded text-white/60 hover:text-white text-[11px]"
          >Reset</button>
          <button
            onClick={() => setShowList(true)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-white/60 hover:text-white"
          >
            <List className="size-3" /> List
          </button>
        </div>
      </div>
      <svg
        ref={svgRef}
        width="100%"
        height="280"
        viewBox="0 0 600 300"
        className="rounded-lg bg-white/5 cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {edges.map(edge => {
            const fromNode = nodes.find(n => n.id === edge.claim_id);
            const toNode = nodes.find(n => n.id === edge.evidence_id);
            if (!fromNode || !toNode) return null;
            return (
              <g key={edge.edge_id}>
                <line
                  x1={fromNode.x} y1={fromNode.y}
                  x2={toNode.x} y2={toNode.y}
                  stroke={EDGE_COLORS[edge.relation] || '#888'}
                  strokeWidth={1.5 + edge.weight}
                  opacity={0.7}
                />
                <text
                  x={(fromNode.x + toNode.x) / 2}
                  y={(fromNode.y + toNode.y) / 2 - 5}
                  fill={EDGE_COLORS[edge.relation] || '#888'}
                  fontSize="9"
                  textAnchor="middle"
                  className="font-mono"
                >
                  {edge.relation}
                </text>
              </g>
            );
          })}
          {/* Nodes */}
          {nodes.map(node => (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className="cursor-pointer"
              onClick={() => setSelectedNode(node.id === selectedNode ? null : node.id)}
            >
              <circle
                r={node.type === 'claim' ? 20 : 15}
                fill={node.type === 'claim' ? '#2C7380' : '#BB9362'}
                opacity={selectedNode && selectedNode !== node.id ? 0.3 : 0.9}
                stroke="white"
                strokeWidth={selectedNode === node.id ? 2 : 0.5}
              />
              <text
                y={node.type === 'claim' ? -25 : -20}
                fill="white"
                fontSize="8"
                textAnchor="middle"
                className="font-mono"
              >
                {node.id.slice(0, 12)}
              </text>
              <text
                y={5}
                fill="white"
                fontSize="7"
                textAnchor="middle"
              >
                {node.type === 'claim' ? node.verdict : node.type}
              </text>
            </g>
          ))}
        </g>
      </svg>
      {/* Selected node detail */}
      {selectedNode && (() => {
        const claim = claims.find(c => c.id === selectedNode);
        const ev = evidence.find(e => e.id === selectedNode);
        const nodeEdges = edges.filter(e => e.claim_id === selectedNode || e.evidence_id === selectedNode);
        return (
          <div className="mt-2 p-2 rounded-lg bg-white/5">
            <p className="text-[11px] text-white/80 font-mono">{selectedNode}</p>
            {claim && <p className="text-[11px] text-white/60 mt-1">{claim.statement}</p>}
            {ev && <p className="text-[11px] text-white/60 mt-1">{ev.source_id} · {ev.kind}</p>}
            <div className="mt-1 flex gap-2">
              {nodeEdges.map(e => (
                <span key={e.edge_id} className="text-[9px] px-1.5 py-0.5 rounded"
                  style={{ background: (EDGE_COLORS[e.relation] || '#888') + '20', color: EDGE_COLORS[e.relation] || '#888' }}>
                  {e.relation}
                </span>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

/* ============================================================
   Investigation Workspace main component
   ============================================================ */
export function InvestigationWorkspace({ investigationId, onInvestigationChange }: {
  investigationId: string;
  onInvestigationChange?: (id: string) => void;
}) {
  const { t } = useLanguage();
  const [invList, setInvList] = React.useState<InvestigationSummary[]>([]);
  const [showInvList, setShowInvList] = React.useState(false);
  const [workflow, setWorkflow] = React.useState<WorkflowResponse | null>(null);
  const [wfLoading, setWfLoading] = React.useState(true);
  const [wfError, setWfError] = React.useState<string | null>(null);
  const [transitioning, setTransitioning] = React.useState(false);

  // Evidence, claims, edges — each with its own error state (NO silent catch)
  const evidenceState = useAsyncData(() => manaraApiExt.evidence(investigationId), [investigationId]);
  const claimsState = useAsyncData(() => manaraApiExt.claims(investigationId), [investigationId]);
  const edgesState = useAsyncData(() => manaraApiExt.edges(investigationId), [investigationId]);

  // Load workflow + poll every 5s
  React.useEffect(() => {
    if (!investigationId) return;
    let cancelled = false;

    const loadWorkflow = async () => {
      try {
        const wf = await manaraApiExt.workflow(investigationId);
        if (!cancelled) { setWorkflow(wf); setWfLoading(false); setWfError(null); }
      } catch (e) {
        if (!cancelled) {
          setWfLoading(false);
          setWfError(e instanceof Error ? e.message : 'Failed to load workflow');
        }
      }
    };

    loadWorkflow();
    const interval = setInterval(loadWorkflow, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [investigationId]);

  // Load investigation list
  React.useEffect(() => {
    manaraApiExt.investigations()
      .then(list => setInvList(list))
      .catch(() => {}); // Investigation list is optional — failure is non-critical
  }, []);

  const handleTransition = async (targetState: string) => {
    if (!investigationId || transitioning) return;
    setTransitioning(true);
    try {
      const result = await manaraApiExt.transition(investigationId, targetState);
      if (!result.transitioned && result.blocker) {
        setWfError(`${t('workspace.blocked')}: ${result.blocker}`);
      }
      const wf = await manaraApiExt.workflow(investigationId);
      setWorkflow(wf);
    } catch (e) {
      setWfError(e instanceof Error ? e.message : 'Transition failed');
    } finally {
      setTransitioning(false);
    }
  };

  const currentState = workflow?.state || 'unknown';
  const currentStateIndex = FSM_STATES.indexOf(currentState as typeof FSM_STATES[number]);
  const nextState = currentStateIndex >= 0 && currentStateIndex < FSM_STATES.length - 1
    ? FSM_STATES[currentStateIndex + 1] : null;

  return (
    <div className="space-y-6">
      {/* Header with investigation selector */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-[22px] font-semibold text-[var(--manara-ink)]">
            {t('nav.workspace')}
          </h2>
          <button
            onClick={() => setShowInvList(!showInvList)}
            className="text-[12px] text-[var(--manara-ink-muted)] font-mono hover:text-[var(--manara-teal)]"
          >
            {investigationId} ▾
          </button>
        </div>
        {workflow?.blocker && (
          <div className="px-3 py-1.5 rounded-lg bg-red-50 border border-red-200 text-[12px] text-red-700">
            ⚠ {workflow.blocker}
          </div>
        )}
      </div>

      {/* Investigation list dropdown */}
      {showInvList && invList.length > 0 && (
        <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-3 shadow-lg">
          <p className="text-[11px] text-[var(--manara-ink-muted)] mb-2">{t('workspace.selectInvestigation')}</p>
          <div className="space-y-1">
            {invList.map(inv => (
              <button
                key={inv.id}
                onClick={() => { onInvestigationChange?.(inv.id); setShowInvList(false); }}
                className={`w-full text-left px-3 py-2 rounded-lg text-[12px] hover:bg-[var(--manara-mist)] ${
                  inv.id === investigationId ? 'bg-[var(--manara-mist)] font-medium' : ''
                }`}
              >
                <span className="font-mono text-[var(--manara-teal)]">{inv.id.slice(0, 16)}</span>
                <span className="text-[var(--manara-ink-muted)] ml-2">· {inv.state || 'unknown'}</span>
                <p className="text-[10px] text-[var(--manara-ink-muted)] truncate">{inv.topic}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-4">
        {/* Left: 13-state FSM */}
        <div className="rounded-[12px] bg-[var(--manara-ink)] p-4 text-white">
          <h3 className="text-[11px] uppercase tracking-wider text-white/50 mb-3">{t('workspace.states')}</h3>
          {wfLoading ? (
            <div className="flex items-center gap-2 py-4">
              <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
              <span className="text-[12px] text-white/40">{t('common.loading')}</span>
            </div>
          ) : wfError ? (
            <div className="py-4">
              <AlertCircle className="size-4 text-red-400 mb-1" />
              <p className="text-[11px] text-red-300">{wfError}</p>
              <button onClick={() => window.location.reload()} className="mt-2 text-[10px] text-[var(--manara-teal)] hover:underline">
                <RefreshCw className="size-3 inline" /> {t('common.retry')}
              </button>
            </div>
          ) : (
            <>
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
              {/* Transition history */}
              {workflow && workflow.transitions.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/10">
                  <p className="text-[10px] uppercase tracking-wider text-white/40 mb-2">{t('workspace.history')}</p>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {workflow.transitions.slice().reverse().map((tr, i) => (
                      <div key={i} className="text-[10px] text-white/40 font-mono">
                        {tr.from || '∅'} → {tr.to}
                        <p className="text-white/30">{tr.at.split('T')[0]} · {tr.actor}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {nextState && currentState !== 'archived' && (
                <button
                  onClick={() => handleTransition(nextState)}
                  disabled={transitioning}
                  className="w-full mt-3 px-3 py-2 rounded-lg bg-[var(--manara-teal)] text-white text-[12px] font-medium disabled:opacity-50"
                >
                  {transitioning ? '...' : `→ ${nextState}`}
                </button>
              )}
            </>
          )}
        </div>

        {/* Center: Evidence + Claims */}
        <div className="space-y-4">
          {/* Evidence */}
          <div className="rounded-[12px] bg-white border border-[var(--manara-mist)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="size-4 text-[var(--manara-teal)]" />
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
                {t('workspace.evidence')} ({evidenceState.data?.length ?? 0})
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
                <button onClick={() => window.location.reload()} className="mt-1 text-[11px] text-[var(--manara-teal)]">{t('common.retry')}</button>
              </div>
            ) : !evidenceState.data || evidenceState.data.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">{t('workspace.noEvidence')}</p>
            ) : (
              <div className="space-y-2">
                {evidenceState.data.map(ev => (
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
              <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
                {t('workspace.claims')} ({claimsState.data?.length ?? 0})
              </h3>
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
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">{t('workspace.noClaims')}</p>
            ) : (
              <div className="space-y-2">
                {claimsState.data.map(cl => (
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
          {edgesState.loading ? (
            <div className="flex items-center gap-2 py-8 justify-center">
              <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
              <span className="text-[12px] text-white/40">{t('common.loading')}</span>
            </div>
          ) : edgesState.error ? (
            <div className="py-8 text-center">
              <AlertCircle className="size-4 text-red-400 mx-auto mb-1" />
              <p className="text-[11px] text-red-300">{edgesState.error}</p>
            </div>
          ) : edgesState.data ? (
            <KnowledgeGraph
              edges={edgesState.data}
              claims={claimsState.data || []}
              evidence={evidenceState.data || []}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
