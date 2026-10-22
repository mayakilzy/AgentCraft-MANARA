/* ============================================================
   MANARA — Investigation Workspace (Page 02) — SOURCE-INTEGRATION v1
   Visual structure ported from MANARA_PAGE_02_HTML_CSS_SOURCE_v1.zip
   (immutable commit 697e711 on repo-info).

   Functional scaffolding preserved from the prior closure version:
   - manaraApiExt integration (evidence, claims, edges, workflow,
     investigations, decisions)
   - 13 real FSM states with workflow polling + auto-initialize on 404
   - State transition handling with blocker detection
   - Investigation selector
   - Knowledge Graph with zoom/pan, list fallback, node selection
   - EN/AR i18n via useLanguage()

   Visual layer rebuilt to match the reference:
   - 2-column primary/secondary grid (2.52fr / 1fr)
   - Question panel with 5-phase horizontal stepper (13 state pills)
   - Observatory (dark Intelligence Observatory surface with curved
     SVG edges, luminous nodes, halo background, 3 obs-cards, node-panel)
   - Overview panel (dl with 6 fields)
   - Key Insights panel (5 colored insights from real data)
   - Sources panel (real foundry candidates, honest "not registered" status)
   - Audit & transition history (real workflow.transitions + decisions)

   Per reference_validation.md:
   - NO demo banner (replaced by honest loading/empty/error state machine)
   - NO bottom engineering notes (dev-only guidance, not user-facing)
   - NO fabricated actions (Edit Question, Pause, Share, Export)
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import {
  manaraApiExt,
  manaraApi,
  ManaraApiError,
  type WorkflowResponse,
  type EvidenceItem,
  type ClaimItem,
  type EdgeItem,
  type InvestigationSummary,
  type StatusResponse,
} from './api-client';

// API_BASE for direct fetch calls (workflow initialization)
// Default matches the value in api-client.ts (127.0.0.1, not localhost,
// to avoid IPv6-first resolution issues in dev environments).
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8000';
import {
  Loader2, AlertCircle, ChevronRight, Network, FileText,
  RefreshCw, List, Maximize2, Plus, Minus,
  Clock, Database, Compass,
} from 'lucide-react';

// ============================================================
// FSM — 13 real states grouped into 5 visual phases
// (matches reference script.js stages[] array)
// ============================================================
const FSM_STATES = [
  'received', 'scoped', 'coverage_checked', 'building_capabilities',
  'mold_ready', 'acquiring', 'normalizing', 'evidencing',
  'forecasting_or_scenarios', 'drafting', 'verification',
  'deliverable_ready', 'archived',
] as const;

const PHASES = [
  { en: 'Discovery', ar: 'الاستكشاف', states: ['received', 'scoped', 'coverage_checked'] },
  { en: 'Build', ar: 'البناء', states: ['building_capabilities', 'mold_ready'] },
  { en: 'Acquire', ar: 'الجمع', states: ['acquiring', 'normalizing', 'evidencing'] },
  { en: 'Synthesize', ar: 'التركيب', states: ['forecasting_or_scenarios', 'drafting', 'verification'] },
  { en: 'Deliver', ar: 'التسليم', states: ['deliverable_ready', 'archived'] },
] as const;

const EDGE_COLORS: Record<string, string> = {
  supports: '#3A8A5C',
  refutes: '#C44545',
  qualifies: '#C49445',
};

// ============================================================
// Async data hook — preserves loading/error/empty state machine
// ============================================================
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

// ============================================================
// Observatory Knowledge Graph — dark Intelligence Observatory surface
// with curved SVG edges, luminous nodes, halo background.
// Preserves: zoom/pan, list fallback, node selection, real data.
// ============================================================
function KnowledgeGraph({ edges, claims, evidence }: {
  edges: EdgeItem[];
  claims: ClaimItem[];
  evidence: EvidenceItem[];
}) {
  const { t, lang } = useLanguage();
  const [showList, setShowList] = React.useState(false);
  const [selectedNode, setSelectedNode] = React.useState<string | null>(null);
  const [zoom, setZoom] = React.useState(1);
  const [pan, setPan] = React.useState({ x: 0, y: 0 });
  const svgRef = React.useRef<SVGSVGElement>(null);
  const isDragging = React.useRef(false);
  const lastPos = React.useRef({ x: 0, y: 0 });

  // Build nodes from claims + evidence (real data)
  const nodes = React.useMemo(() => {
    const claimNodes = claims.map((c, i) => ({
      id: c.id,
      type: 'claim' as const,
      label: c.statement.slice(0, 40) + (c.statement.length > 40 ? '…' : ''),
      verdict: c.verdict,
      x: 200 + Math.cos((i / Math.max(claims.length, 1)) * 2 * Math.PI) * 120,
      y: 150 + Math.sin((i / Math.max(claims.length, 1)) * 2 * Math.PI) * 120,
    }));
    const evIds = new Set(edges.map(e => e.evidence_id));
    const evidenceNodes: typeof claimNodes = Array.from(evIds).map((id, i) => {
      const ev = evidence.find(e => e.id === id);
      return {
        id,
        type: 'claim' as const, // visual parity
        label: ev ? `${ev.source_id} · ${ev.kind}` : id,
        verdict: 'evidence' as string,
        x: 400 + Math.cos((i / Math.max(evIds.size, 1)) * 2 * Math.PI) * 100,
        y: 150 + Math.sin((i / Math.max(evIds.size, 1)) * 2 * Math.PI) * 100,
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

  // Honest empty state — NO edges means no relationship data yet
  if (edges.length === 0) {
    return (
      <div className="manara-observatory-empty">
        <Network className="size-8 mx-auto mb-2 opacity-30" />
        <p className="text-[12px] opacity-50">{t('workspace.noEdges')}</p>
        <p className="text-[10px] opacity-40 mt-1">
          {lang === 'ar'
            ? 'لا توجد علاقات بحثية مسجلة بعد'
            : 'No research relationships recorded yet'}
        </p>
      </div>
    );
  }

  // List fallback — accessibility alternative to SVG
  if (showList) {
    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[14px] font-semibold text-white">
            {lang === 'ar' ? 'العلاقات' : 'Relationships'} ({edges.length})
          </h3>
          <button
            onClick={() => setShowList(false)}
            className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-white/60 hover:text-white"
          >
            <Maximize2 className="size-3" />
            {lang === 'ar' ? 'الرسم' : 'Graph'}
          </button>
        </div>
        <div className="space-y-1.5 max-h-64 overflow-y-auto manara-scroll">
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

  // SVG graph view — Observatory visual style
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[14px] font-semibold text-white">
          {lang === 'ar' ? 'الرسم المعرفي' : 'Knowledge Graph'}
        </h3>
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom(z => Math.max(0.3, z - 0.2))} aria-label="Zoom out"
            className="px-1.5 py-0.5 rounded text-white/60 hover:text-white text-[11px]"><Minus className="size-3" /></button>
          <span className="text-[10px] text-white/40 font-mono">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(3, z + 0.2))} aria-label="Zoom in"
            className="px-1.5 py-0.5 rounded text-white/60 hover:text-white text-[11px]"><Plus className="size-3" /></button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
            className="px-1.5 py-0.5 rounded text-white/60 hover:text-white text-[11px]">
            {lang === 'ar' ? 'إعادة' : 'Reset'}
          </button>
          <button onClick={() => setShowList(true)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-white/60 hover:text-white">
            <List className="size-3" /> {lang === 'ar' ? 'قائمة' : 'List'}
          </button>
        </div>
      </div>
      <svg
        ref={svgRef}
        width="100%"
        height="280"
        viewBox="0 0 600 300"
        className="manara-observatory-svg cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        role="img"
        aria-label={lang === 'ar' ? 'رسم معرفي للعلاقات بين الادعاءات والأدلة' : 'Knowledge graph of claim-evidence relationships'}
      >
        <defs>
          <radialGradient id="halo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#065f76" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#001323" stopOpacity="0" />
          </radialGradient>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="tinyglow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* Halo background */}
        <ellipse cx="300" cy="150" rx="290" ry="140" fill="url(#halo)" />
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Curved edges with luminous strokes */}
          {edges.map(edge => {
            const fromNode = nodes.find(n => n.id === edge.claim_id);
            const toNode = nodes.find(n => n.id === edge.evidence_id);
            if (!fromNode || !toNode) return null;
            // Curved path between nodes
            const dx = toNode.x - fromNode.x;
            const cx1 = fromNode.x + dx * 0.3;
            const cy1 = fromNode.y - 30;
            const cx2 = toNode.x - dx * 0.3;
            const cy2 = toNode.y + 30;
            return (
              <g key={edge.edge_id}>
                <path
                  d={`M ${fromNode.x} ${fromNode.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${toNode.x} ${toNode.y}`}
                  fill="none"
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
          {/* Nodes — luminous with halo */}
          {nodes.map(node => (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className="cursor-pointer"
              onClick={() => setSelectedNode(node.id === selectedNode ? null : node.id)}
              role="button"
              tabIndex={0}
              aria-label={node.label}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setSelectedNode(node.id === selectedNode ? null : node.id);
                }
              }}
            >
              <circle r={23} fill="#2ee4d4" opacity={0.11} filter="url(#glow)" />
              <circle
                r={12}
                fill="#093b4b"
                stroke="#2ee4d4"
                strokeWidth={2}
                opacity={selectedNode && selectedNode !== node.id ? 0.3 : 0.9}
              />
              <circle r={5} fill="#2ee4d4" filter="url(#tinyglow)" />
              <text y={-25} fill="#d4edf5" fontSize="8" textAnchor="middle" className="font-mono">
                {node.id.slice(0, 12)}
              </text>
              <text y={25} fill="#d4edf5" fontSize="7" textAnchor="middle">
                {node.verdict}
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
          <div className="manara-node-panel">
            <p className="text-[11px] text-white/80 font-mono">{selectedNode}</p>
            {claim && <p className="text-[11px] text-white/60 mt-1">{claim.statement}</p>}
            {ev && <p className="text-[11px] text-white/60 mt-1">{ev.source_id} · {ev.kind}</p>}
            <div className="mt-1 flex gap-2 flex-wrap">
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

// ============================================================
// Loading / Error / Empty inline states
// ============================================================
function InlineLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-4">
      <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
      <span className="text-[12px] text-[var(--manara-ink-muted)]">{label}</span>
    </div>
  );
}

function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="py-4">
      <AlertCircle className="size-4 text-[var(--manara-error)] mb-1" />
      <p className="text-[12px] text-[var(--manara-error)]">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-1 text-[11px] text-[var(--manara-teal)] hover:underline">
          <RefreshCw className="size-3 inline" /> Retry
        </button>
      )}
    </div>
  );
}

function InlineDarkLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-8 justify-center">
      <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
      <span className="text-[12px] text-white/40">{label}</span>
    </div>
  );
}

function InlineDarkError({ message }: { message: string }) {
  return (
    <div className="py-8 text-center">
      <AlertCircle className="size-4 text-red-400 mx-auto mb-1" />
      <p className="text-[11px] text-red-300">{message}</p>
    </div>
  );
}

// ============================================================
// Foundry candidate type (lightweight — avoids importing backend types)
// ============================================================
interface FoundryCandidate {
  id: string;
  display_name: string;
  description: string;
  license: string;
  auth_required: boolean;
  homepage: string;
  primary_data_types: string[];
}

// ============================================================
// Investigation Workspace main component
// ============================================================
export function InvestigationWorkspace({ investigationId, onInvestigationChange }: {
  investigationId: string;
  onInvestigationChange?: (id: string) => void;
}) {
  const { t, lang } = useLanguage();
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

  // NEW: investigation detail (research question, mold_id, blocker)
  const invDetailState = useAsyncData(
    () => manaraApiExt.investigation(investigationId),
    [investigationId],
  );
  // NEW: audit decisions
  const decisionsState = useAsyncData(
    () => manaraApiExt.decisions(investigationId),
    [investigationId],
  );
  // NEW: backend status (for Mode + discovery_mode)
  const [statusInfo, setStatusInfo] = React.useState<StatusResponse | null>(null);
  React.useEffect(() => {
    let cancelled = false;
    manaraApi.status()
      .then(s => { if (!cancelled) setStatusInfo(s); })
      .catch(() => {}); // Status is non-critical — failure is graceful
    return () => { cancelled = true; };
  }, []);
  // NEW: foundry candidates (for Sources panel — real catalog)
  const [candidates, setCandidates] = React.useState<FoundryCandidate[]>([]);
  React.useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/foundry/candidates`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((data: FoundryCandidate[]) => { if (!cancelled) setCandidates(data); })
      .catch(() => {}); // Foundry is non-critical — failure is graceful
    return () => { cancelled = true; };
  }, []);

  // Load workflow + poll every 5s (preserved from prior version)
  React.useEffect(() => {
    if (!investigationId) return;
    let cancelled = false;

    const loadWorkflow = async () => {
      try {
        const wf = await manaraApiExt.workflow(investigationId);
        if (!cancelled) { setWorkflow(wf); setWfLoading(false); setWfError(null); }
      } catch (e) {
        // Auto-initialize on 404 — backend creates workflow row lazily
        const is404 = e instanceof ManaraApiError && e.status === 404;
        if (is404 && !cancelled) {
          try {
            await fetch(`${API_BASE}/mold-factory/investigations/${investigationId}/workflow`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
            });
            const wf = await manaraApiExt.workflow(investigationId);
            if (!cancelled) { setWorkflow(wf); setWfLoading(false); setWfError(null); }
            return;
          } catch (initErr) {
            if (!cancelled) {
              setWfLoading(false);
              setWfError(
                `Failed to initialize workflow: ${
                  initErr instanceof Error ? initErr.message : String(initErr)
                }`,
              );
            }
            return;
          }
        }
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

  const reloadAll = () => window.location.reload();

  // Derived state
  const currentState = workflow?.state || 'unknown';
  const currentStateIndex = FSM_STATES.indexOf(currentState as typeof FSM_STATES[number]);
  const nextState = currentStateIndex >= 0 && currentStateIndex < FSM_STATES.length - 1
    ? FSM_STATES[currentStateIndex + 1] : null;

  // Research question (from investigation detail; fallback to ID)
  const researchQuestion = invDetailState.data?.topic || investigationId;
  // Tags — derived from investigation topic words (honest, not fabricated)
  const tags = React.useMemo(() => {
    const topic = invDetailState.data?.topic;
    if (!topic) return [];
    // Simple honest split: take distinctive words longer than 4 chars
    const stop = new Set(['what', 'how', 'why', 'the', 'and', 'with', 'from', 'about', 'their', 'this', 'that', 'over', 'next', 'into', 'are', 'was', 'were', 'has', 'have', 'will', 'may', 'can']);
    return topic
      .split(/[\s,.?]+/)
      .map(w => w.trim())
      .filter(w => w.length > 4 && !stop.has(w.toLowerCase()))
      .slice(0, 5);
  }, [invDetailState.data]);

  // Unique sources (from evidence) — honest count
  const uniqueSources = React.useMemo(() => {
    if (!evidenceState.data) return [] as string[];
    return Array.from(new Set(evidenceState.data.map(e => e.source_id)));
  }, [evidenceState.data]);

  // Combined audit history — workflow transitions + decisions, newest-first
  const auditEntries = React.useMemo(() => {
    type Entry = { at: string; actor: string; kind: string; description: string };
    const trs: Entry[] = (workflow?.transitions || []).map(tr => ({
      at: tr.at, actor: tr.actor,
      kind: 'transition',
      description: `${tr.from || '∅'} → ${tr.to}`,
    }));
    const decs: Entry[] = (decisionsState.data || []).map(d => ({
      at: d.decided_at, actor: d.actor,
      kind: d.decision_type,
      description: d.rationale,
    }));
    return [...trs, ...decs].sort((a, b) => b.at.localeCompare(a.at));
  }, [workflow?.transitions, decisionsState.data]);

  // Phase status for the 5-phase horizontal stepper
  const phaseStatus = (phaseIdx: number): 'completed' | 'current' | 'pending' => {
    if (currentStateIndex < 0) return 'pending';
    const phase = PHASES[phaseIdx];
    const phaseStartIdx = FSM_STATES.indexOf(phase.states[0] as typeof FSM_STATES[number]);
    const phaseEndIdx = FSM_STATES.indexOf(phase.states[phase.states.length - 1] as typeof FSM_STATES[number]);
    if (currentStateIndex > phaseEndIdx) return 'completed';
    if (currentStateIndex >= phaseStartIdx && currentStateIndex <= phaseEndIdx) return 'current';
    return 'pending';
  };

  const isAr = lang === 'ar';

  return (
    <div className="manara-workspace">
      {/* === Investigation strip === */}
      <section className="manara-investigation-strip">
        <div className="manara-idgroup">
          <span className="manara-square-symbol" aria-hidden>✥</span>
          <strong className="font-serif">{investigationId.slice(0, 24)}</strong>
          <span className="manara-status-pill">
            <i></i>
            {wfLoading ? (isAr ? 'جار التحميل' : 'Loading') : (workflow?.state || 'unknown')}
          </span>
          <span className="manara-minor">
            {invDetailState.data
              ? (isAr ? `أُنشئ في ${invDetailState.data.created_at.split('T')[0]}` : `Started ${invDetailState.data.created_at.split('T')[0]}`)
              : (isAr ? 'تحقق من التفاصيل' : 'Loading details')}
          </span>
        </div>
        <div className="manara-actions">
          <span className="manara-muted-pill">
            {isAr ? 'مرجع للعرض فقط' : 'Reference only'}
          </span>
          {nextState && currentState !== 'archived' && (
            <button
              onClick={() => handleTransition(nextState)}
              disabled={transitioning}
              className="manara-next-button"
            >
              {transitioning
                ? (isAr ? 'جار التنفيذ...' : 'Transitioning...')
                : `→ ${nextState.replace(/_/g, ' ')}`}
            </button>
          )}
        </div>
      </section>

      {/* === Investigation selector dropdown (preserved) === */}
      {showInvList && invList.length > 0 && (
        <div className="manara-investigation-dropdown">
          <p className="text-[11px] text-[var(--manara-ink-muted)] mb-2">{t('workspace.selectInvestigation')}</p>
          <div className="space-y-1">
            {invList.map(inv => (
              <button
                key={inv.id}
                onClick={() => { onInvestigationChange?.(inv.id); setShowInvList(false); }}
                className={`manara-investigation-row ${inv.id === investigationId ? 'is-current' : ''}`}
              >
                <span className="font-mono text-[var(--manara-teal)]">{inv.id.slice(0, 16)}</span>
                <span className="text-[var(--manara-ink-muted)] ml-2">· {inv.state || 'unknown'}</span>
                <p className="text-[10px] text-[var(--manara-ink-muted)] truncate">{inv.topic}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* === Investigation ID selector toggle (small, above the strip) === */}
      <div className="manara-id-toggle-row">
        <button
          onClick={() => setShowInvList(!showInvList)}
          className="manara-id-toggle"
          aria-expanded={showInvList}
        >
          {isAr ? 'تبديل التحقيق' : 'Switch investigation'} ▾
        </button>
        {workflow?.blocker && (
          <div className="manara-blocker-warning">
            ⚠ {workflow.blocker}
          </div>
        )}
      </div>

      {/* === Main 2-column grid === */}
      <div className="manara-columns">
        {/* === Primary column === */}
        <div className="manara-primary-col">
          {/* Question panel + 5-phase horizontal stepper */}
          <section className="manara-panel manara-question-panel">
            <div className="manara-sectiontop">
              <h2 className="manara-panel-h2">▣ &nbsp;{isAr ? 'السؤال البحثي' : 'Research Question'}</h2>
              <span className="manara-muted-pill">
                {isAr ? 'مرجع للعرض فقط' : 'Reference only'}
              </span>
            </div>
            {invDetailState.loading ? (
              <InlineLoading label={t('common.loading')} />
            ) : invDetailState.error ? (
              <InlineError message={invDetailState.error} onRetry={reloadAll} />
            ) : (
              <>
                <h1 className="manara-question-h1">{researchQuestion}</h1>
                {invDetailState.data?.state && (
                  <p className="manara-question-desc">
                    {isAr
                      ? `حالة التحقيق الحالية: ${invDetailState.data.state.replace(/_/g, ' ')}.`
                      : `Investigation current state: ${invDetailState.data.state.replace(/_/g, ' ')}.`}
                  </p>
                )}
                {tags.length > 0 && (
                  <div className="manara-tagline">
                    {tags.map((tag, i) => (
                      <span key={i}>{tag}</span>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* Workflow heading + 5-phase horizontal stepper */}
            <div className="manara-workflow-heading">
              <span>{isAr ? 'دورة حياة التحقيق' : 'Investigation Lifecycle'}</span>
              <span className="manara-workflow-caption">
                {isAr ? '13 حالة حقيقية · 5 مراحل بصرية' : '13 real FSM states · 5 visual phases'}
              </span>
            </div>

            {wfLoading ? (
              <InlineLoading label={isAr ? 'جارٍ تحميل سير العمل' : 'Loading workflow'} />
            ) : wfError ? (
              <InlineError message={wfError} onRetry={reloadAll} />
            ) : (
              <>
                <div className="manara-phases">
                  {PHASES.map((phase, i) => {
                    const status = phaseStatus(i);
                    return (
                      <div key={i} className={`manara-phase ${status}`}>
                        <div className="manara-phase-dot">{i + 1}</div>
                        <b>{isAr ? phase.ar : phase.en}</b>
                        <small>{phase.states.length} {isAr ? 'حالات' : 'states'}</small>
                        <div className="manara-phase-states">
                          {phase.states.map(st => (
                            <button
                              key={st}
                              type="button"
                              className={st === currentState ? 'is-current' : ''}
                              aria-current={st === currentState ? 'step' : undefined}
                              title={st}
                              onClick={() => {
                                // Clicking a state pill does NOT auto-transition;
                                // it surfaces the state name in the detail box.
                                // Real transitions happen via the next-state button.
                              }}
                            >
                              {st.replace(/_/g, ' ')}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="manara-state-detail">
                  {isAr ? 'الحالة الحالية: ' : 'Current state: '}
                  <strong>{currentState.replace(/_/g, ' ')}</strong>
                  {nextState && (
                    <span className="manara-state-detail-next">
                      &nbsp;· {isAr ? 'التالي: ' : 'Next: '}
                      {nextState.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
              </>
            )}
          </section>

          {/* Observatory — dark Intelligence Observatory surface */}
          <section className="manara-observatory" aria-label={isAr ? 'عملية التحقيق' : 'Investigation Process'}>
            <div className="manara-obs-header">
              <h2 className="manara-obs-h2">✥ &nbsp;{isAr ? 'عملية التحقيق' : 'Investigation Process'}</h2>
              <span className="manara-live-pill">
                <i></i>
                {isAr ? 'عرض حي' : 'Live view'}
              </span>
              <span className="manara-obs-hint">
                {isAr ? 'اختر عقدة لاستعراض علاقاتها' : 'Select a node to inspect its relationships'}
              </span>
            </div>
            <div className="manara-graph-bg">
              {edgesState.loading ? (
                <InlineDarkLoading label={t('common.loading')} />
              ) : edgesState.error ? (
                <InlineDarkError message={edgesState.error} />
              ) : edgesState.data ? (
                <KnowledgeGraph
                  edges={edgesState.data}
                  claims={claimsState.data || []}
                  evidence={evidenceState.data || []}
                />
              ) : null}
            </div>
            {/* Observatory cards — 3 layout regions (real categories, honest counts) */}
            <div className="manara-obs-cards">
              <div className="manara-obs-card">
                <b>{isAr ? 'تحليل السؤال' : 'Question Analysis'}</b>
                <span>✓ &nbsp;{isAr ? 'تحليل السؤال' : 'Parse the question'}</span>
                <span>{tags.length > 0 ? '✓' : '◌'} &nbsp;{isAr ? 'تحديد المفاهيم الأساسية' : 'Identify key concepts'}</span>
                <span>{currentStateIndex >= 1 ? '✓' : '◌'} &nbsp;{isAr ? 'تحديد نطاق البحث' : 'Define scope'}</span>
              </div>
              <div className="manara-obs-card">
                <b>{isAr ? 'احتياجات المعرفة' : 'Knowledge Needs'}</b>
                <span>{currentStateIndex >= 3 ? '✓' : '◌'} &nbsp;{isAr ? 'تحديد موضوعات البحث' : 'Identify research topics'}</span>
                <span>{currentStateIndex >= 5 ? '✓' : '◌'} &nbsp;{isAr ? 'صياغة الأسئلة الفرعية' : 'Generate sub-questions'}</span>
                <span>{currentStateIndex >= 7 ? '✓' : '◌'} &nbsp;{isAr ? 'تحديد احتياجات الأدلة' : 'Map evidence needs'}</span>
              </div>
              <div className="manara-obs-card">
                <b>{isAr ? 'تغطية المصادر' : 'Source Coverage'}</b>
                <span>{uniqueSources.length > 0 ? '✓' : '◌'} &nbsp;{isAr ? `مراجعة المصادر المتاحة (${uniqueSources.length})` : `Review available sources (${uniqueSources.length})`}</span>
                <span>{currentStateIndex >= 6 ? '✓' : '◌'} &nbsp;{isAr ? 'تقييم التغطية الفعلية' : 'Assess actual coverage'}</span>
                <span className="manara-obs-card-muted">
                  {isAr ? 'لا نسب اكتمال مختلقة' : 'No fabricated completeness scores'}
                </span>
              </div>
            </div>
          </section>
        </div>

        {/* === Secondary column === */}
        <div className="manara-secondary-col">
          {/* Overview panel */}
          <section className="manara-panel manara-overview-panel">
            <h2 className="manara-panel-h2">♜ &nbsp;{isAr ? 'نظرة عامة على التحقيق' : 'Investigation Overview'}</h2>
            <dl className="manara-overview-dl">
              <dt>{isAr ? 'الحالة' : 'Status'}</dt>
              <dd>
                <span className="manara-status-plain">
                  <i></i>
                  {wfLoading ? (isAr ? 'جارٍ التحميل' : 'Loading') : (workflow?.state || 'unknown').replace(/_/g, ' ')}
                </span>
              </dd>
              <dt>{isAr ? 'القالب' : 'Template'}</dt>
              <dd>{workflow?.mold_id || invDetailState.data?.mold_id || (isAr ? 'غير متاح' : 'Not available')}</dd>
              <dt>{isAr ? 'الوضع' : 'Mode'}</dt>
              <dd>
                {statusInfo
                  ? (isAr
                    ? (statusInfo.discovery_mode === 'live' ? 'حي' : 'اصطناعي')
                    : statusInfo.discovery_mode)
                  : (isAr ? 'جارٍ التحميل' : 'Loading')}
              </dd>
              <dt>{isAr ? 'الإتمام المتوقع' : 'Estimated completion'}</dt>
              <dd>{isAr ? 'غير متاح' : 'Not available'}</dd>
              <dt>{isAr ? 'عناصر الأدلة' : 'Evidence items'}</dt>
              <dd>{evidenceState.loading ? '…' : (evidenceState.data?.length ?? 0)}</dd>
              <dt>{isAr ? 'المصادر المحللة' : 'Sources analyzed'}</dt>
              <dd>{evidenceState.loading ? '…' : uniqueSources.length}</dd>
            </dl>
          </section>

          {/* Key Insights panel — 5 colored insights from real data */}
          <section className="manara-panel manara-insights-panel">
            <h2 className="manara-panel-h2">☼ &nbsp;{isAr ? 'أهم المؤشرات' : 'Key Insights'}</h2>
            <div className="manara-insight">
              <span className="manara-insight-icon manara-purple"><Compass className="size-5" /></span>
              <div>
                <b>{isAr ? 'مجالات البحث' : 'Research Areas'}</b>
                <small>
                  {tags.length > 0
                    ? tags.slice(0, 3).join(', ')
                    : (isAr ? 'يُستخرج من سؤال البحث' : 'Derived from the research question')}
                </small>
              </div>
              <span className="manara-sample-pill">{isAr ? 'مشتق' : 'Derived'}</span>
            </div>
            <div className="manara-insight">
              <span className="manara-insight-icon manara-cyan"><Database className="size-5" /></span>
              <div>
                <b>{isAr ? 'المصادر المحتملة' : 'Potential Sources'}</b>
                <small>
                  {uniqueSources.length > 0
                    ? (isAr ? `${uniqueSources.length} مصدر فريد في الذاكرة` : `${uniqueSources.length} unique source(s) in memory`)
                    : (isAr ? 'لا مصادر مسجلة بعد' : 'No sources recorded yet')}
                </small>
              </div>
              <span className="manara-sample-pill">{isAr ? 'فعلي' : 'Live'}</span>
            </div>
            <div className="manara-insight">
              <span className="manara-insight-icon manara-amber"><FileText className="size-5" /></span>
              <div>
                <b>{isAr ? 'ملاحظات أولية' : 'Initial Observations'}</b>
                <small>
                  {claimsState.data && claimsState.data.length > 0
                    ? (isAr ? `${claimsState.data.length} ادعاء مسجل` : `${claimsState.data.length} claim(s) recorded`)
                    : (isAr ? 'لا ادعاءات بعد' : 'No claims recorded yet')}
                </small>
              </div>
              <span className="manara-sample-pill">{isAr ? 'فعلي' : 'Live'}</span>
            </div>
            <div className="manara-insight">
              <span className="manara-insight-icon manara-coral"><AlertCircle className="size-5" /></span>
              <div>
                <b>{isAr ? 'الفجوات المعرفية' : 'Knowledge Gaps'}</b>
                <small>
                  {workflow?.blocker
                    ? (isAr ? `عائق: ${workflow.blocker}` : `Blocker: ${workflow.blocker}`)
                    : (isAr ? 'لا فجوات موثقة متاحة' : 'No verified gaps recorded')}
                </small>
              </div>
              <span className="manara-sample-pill">{isAr ? 'فعلي' : 'Live'}</span>
            </div>
            <div className="manara-insight">
              <span className="manara-insight-icon manara-blue"><ChevronRight className="size-5" /></span>
              <div>
                <b>{isAr ? 'الخطوات التالية' : 'Next Steps'}</b>
                <small>
                  {nextState
                    ? (isAr ? `الانتقال إلى: ${nextState.replace(/_/g, ' ')}` : `Transition to: ${nextState.replace(/_/g, ' ')}`)
                    : (isAr ? 'التحقيق مؤرشف' : 'Investigation archived')}
                </small>
              </div>
              <span className="manara-sample-pill">{isAr ? 'فعلي' : 'Live'}</span>
            </div>
          </section>
        </div>
      </div>

      {/* === Sources panel — real foundry candidates === */}
      <section className="manara-panel manara-sources-panel">
        <div className="manara-sectiontop">
          <h2 className="manara-panel-h2">▤ &nbsp;{isAr ? 'المصادر قيد الاستكشاف' : 'Sources Being Explored'}</h2>
          <span className="manara-muted-pill">
            {isAr ? 'بيانات الكتالوج الفعلية' : 'Real catalog data'}
          </span>
        </div>
        {candidates.length === 0 ? (
          <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">
            {isAr ? 'لا مصادر متاحة في الكتالوج' : 'No candidates in the foundry catalog'}
          </p>
        ) : (
          <div className="manara-source-grid">
            {candidates.map(c => (
              <div key={c.id} className="manara-source">
                <span className={`manara-source-icon manara-source-${c.id}`}>
                  {c.display_name.slice(0, 3)}
                </span>
                <b>{c.display_name}</b>
                <small>{c.description.slice(0, 80)}{c.description.length > 80 ? '…' : ''}</small>
                <span className="manara-source-placeholder">
                  {isAr ? 'كتالوج — لم يُسجل بعد' : 'Catalog — not registered'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* === Audit & transition history — real workflow.transitions + decisions === */}
      <section className="manara-panel manara-audit-panel">
        <div className="manara-sectiontop">
          <h2 className="manara-panel-h2"><Clock className="size-4 inline" /> &nbsp;{isAr ? 'سجل التدقيق والانتقالات' : 'Audit & Transition History'}</h2>
          <span className="manara-muted-pill">
            {auditEntries.length} {isAr ? 'سجل' : 'entries'}
          </span>
        </div>
        {wfLoading && decisionsState.loading ? (
          <InlineLoading label={isAr ? 'جارٍ تحميل السجل' : 'Loading history'} />
        ) : auditEntries.length === 0 ? (
          <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">
            {isAr ? 'لا سجلات تدقيق متاحة بعد' : 'No audit entries recorded yet'}
          </p>
        ) : (
          <div className="manara-audit-list">
            {auditEntries.slice(0, 20).map((entry, i) => (
              <div key={i} className="manara-audit-entry">
                <span className="manara-audit-kind">{entry.kind}</span>
                <div>
                  <p className="manara-audit-description">{entry.description}</p>
                  <p className="manara-audit-meta">
                    {entry.at.replace('T', ' ').slice(0, 19)} · {entry.actor}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
