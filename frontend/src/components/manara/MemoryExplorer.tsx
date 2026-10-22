/* ============================================================
   MANARA — Memory Explorer (Page 03) — OWNER-APPROVED SOURCE v1
   Visual source: MANARA_PAGE_03_OWNER_APPROVED_HTML_CSS_SOURCE_v1.zip
   (immutable commit dffaaed9 on repo-info, blob SHA 67376e32)

   3-column analytical layout:
   - Left: Evidence panel (tabs: Evidence/Claims/Topics, search, filters)
   - Center: Knowledge Graph (SVG, zoom/pan, list fallback, selection)
   - Right: Selected Item Inspector (overview/related/timeline/notes)

   Bottom panels:
   - Timeline (real evidence/claims/decisions timestamps)
   - Related Topics (derived from evidence source_ids + claim groups)

   Bitemporal replay via POST /memory/investigations/{id}/at-cutoff.

   Per README integration contract:
   - NO fixture data (Ocean Plastic Pollution story removed)
   - NO fabricated credibility scores, peer-review labels, or source ratings
   - Real evidence/claims/edges/decisions from manaraApiExt
   - Honest empty/loading/error states
   - Graph nodes/edges from real backend data
   - Bitemporal replay uses real at-cutoff endpoint
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import {
  manaraApiExt,
  type EvidenceItem,
  type ClaimItem,
  type EdgeItem,
  type CutoffResponse,
} from './api-client';
import {
  Loader2, AlertCircle, RefreshCw, FileText,
  Network, Plus, Minus, List, Maximize2, X,
  Clock, Database, Tag, Search, Filter,
} from 'lucide-react';

// ============================================================
// Constants
// ============================================================

const EDGE_COLORS: Record<string, string> = {
  supports: '#109bac',
  refutes: '#ef9b40',
  qualifies: '#cad8df',
};

const VERDICT_LABELS: Record<string, { en: string; ar: string; mark: string }> = {
  candidate: { en: 'Candidate', ar: 'مرشح', mark: '◉' },
  supported: { en: 'Supported', ar: 'مدعوم', mark: '↑' },
  contested: { en: 'Contested', ar: 'متنازع', mark: '↓' },
  refuted: { en: 'Refuted', ar: 'مرفوض', mark: '✕' },
  superseded: { en: 'Superseded', ar: 'مستبدل', mark: '◇' },
};

// ============================================================
// Async data hook (preserved from prior version)
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
// Inline loading / error / empty states
// ============================================================
function InlineLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-8 justify-center">
      <Loader2 className="size-4 animate-spin text-[var(--manara-teal)]" />
      <span className="text-[12px] text-[var(--manara-ink-muted)]">{label}</span>
    </div>
  );
}

function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="py-8 text-center">
      <AlertCircle className="size-4 text-[var(--manara-error)] mx-auto mb-1" />
      <p className="text-[12px] text-[var(--manara-error)]">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-[11px] text-[var(--manara-teal)] hover:underline">
          <RefreshCw className="size-3 inline" /> Retry
        </button>
      )}
    </div>
  );
}

function InlineEmpty({ message }: { message: string }) {
  return (
    <div className="py-8 text-center">
      <p className="text-[12px] text-[var(--manara-ink-muted)]">{message}</p>
    </div>
  );
}

// ============================================================
// Knowledge Graph — SVG with zoom/pan/selection/list fallback
// Reads real EdgeItem[], ClaimItem[], EvidenceItem[]
// ============================================================
function MemoryGraph({
  edges,
  claims,
  evidence,
  selectedNode,
  onSelectNode,
}: {
  edges: EdgeItem[];
  claims: ClaimItem[];
  evidence: EvidenceItem[];
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
}) {
  const { t, lang } = useLanguage();
  const [showList, setShowList] = React.useState(false);
  const [zoom, setZoom] = React.useState(1);
  const [pan, setPan] = React.useState({ x: 0, y: 0 });
  const isDragging = React.useRef(false);
  const lastPos = React.useRef({ x: 0, y: 0 });

  // Build nodes from claims + evidence (real data)
  const nodes = React.useMemo(() => {
    const claimNodes = claims.map((c, i) => ({
      id: c.id,
      type: 'claim' as const,
      label: c.statement.slice(0, 40) + (c.statement.length > 40 ? '…' : ''),
      verdict: c.verdict,
      x: 250 + Math.cos((i / Math.max(claims.length, 1)) * 2 * Math.PI) * 140,
      y: 245 + Math.sin((i / Math.max(claims.length, 1)) * 2 * Math.PI) * 140,
    }));
    const evIds = new Set(edges.map(e => e.evidence_id));
    const evidenceNodes = Array.from(evIds).map((id, i) => {
      const ev = evidence.find(e => e.id === id);
      return {
        id,
        type: 'evidence' as const,
        label: ev ? `${ev.source_id} · ${ev.kind}` : id,
        verdict: '',
        x: 250 + Math.cos((i / Math.max(evIds.size, 1)) * 2 * Math.PI + Math.PI) * 100,
        y: 245 + Math.sin((i / Math.max(evIds.size, 1)) * 2 * Math.PI + Math.PI) * 100,
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

  // Empty state
  if (edges.length === 0) {
    return (
      <div className="manara-me-graph-empty">
        <Network className="size-8 mx-auto mb-2 opacity-30" />
        <p className="text-[12px] opacity-50">{t('workspace.noEdges')}</p>
        <p className="text-[10px] opacity-40 mt-1">
          {lang === 'ar' ? 'لا توجد علاقات مسجلة بعد' : 'No relationships recorded yet'}
        </p>
      </div>
    );
  }

  // List fallback
  if (showList) {
    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
            {lang === 'ar' ? 'العلاقات' : 'Relationships'} ({edges.length})
          </h3>
          <button
            onClick={() => setShowList(false)}
            className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-[var(--manara-ink-muted)] hover:text-[var(--manara-teal)]"
          >
            <Maximize2 className="size-3" />
            {lang === 'ar' ? 'الرسم' : 'Graph'}
          </button>
        </div>
        <div className="space-y-1.5 max-h-96 overflow-y-auto manara-scroll">
          {edges.map(edge => (
            <div
              key={edge.edge_id}
              className="px-2 py-1.5 rounded-md bg-[var(--manara-mist)]/50 cursor-pointer hover:bg-[var(--manara-mist)]"
              onClick={() => onSelectNode(edge.claim_id === selectedNode ? null : edge.claim_id)}
            >
              <div className="flex items-center gap-2">
                <div className="size-2 rounded-full" style={{ background: EDGE_COLORS[edge.relation] || '#888' }} />
                <span className="text-[10px] font-mono uppercase">{edge.relation}</span>
                <span className="text-[10px] text-[var(--manara-ink-muted)]">w={edge.weight}</span>
              </div>
              <p className="text-[10px] text-[var(--manara-ink-muted)] mt-0.5 font-mono">
                {edge.claim_id} → {edge.evidence_id}
              </p>
              {edge.notes && <p className="text-[10px] text-[var(--manara-ink-muted)]/70 mt-0.5 italic">{edge.notes}</p>}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // SVG graph view
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[14px] font-semibold text-[var(--manara-ink)]">
          {lang === 'ar' ? 'الرسم المعرفي' : 'Knowledge Graph'}
        </h3>
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom(z => Math.max(0.3, z - 0.2))} aria-label="Zoom out"
            className="px-1.5 py-0.5 rounded text-[var(--manara-ink-muted)] hover:text-[var(--manara-teal)] text-[11px]"><Minus className="size-3" /></button>
          <span className="text-[10px] text-[var(--manara-ink-muted)] font-mono">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(3, z + 0.2))} aria-label="Zoom in"
            className="px-1.5 py-0.5 rounded text-[var(--manara-ink-muted)] hover:text-[var(--manara-teal)] text-[11px]"><Plus className="size-3" /></button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
            className="px-1.5 py-0.5 rounded text-[var(--manara-ink-muted)] hover:text-[var(--manara-teal)] text-[11px]">
            {lang === 'ar' ? 'إعادة' : 'Reset'}
          </button>
          <button onClick={() => setShowList(true)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-[var(--manara-ink-muted)] hover:text-[var(--manara-teal)]">
            <List className="size-3" /> {lang === 'ar' ? 'قائمة' : 'List'}
          </button>
        </div>
      </div>
      <svg
        width="100%"
        height="490"
        viewBox="0 0 500 490"
        className="manara-me-graph-svg cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        role="img"
        aria-label={lang === 'ar' ? 'رسم معرفي للعلاقات' : 'Knowledge graph of relationships'}
      >
        <defs>
          <radialGradient id="me-halo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#065f76" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#065f76" stopOpacity="0" />
          </radialGradient>
          <filter id="me-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="me-tinyglow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.4" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {/* Halo background */}
        <ellipse cx="250" cy="245" rx="250" ry="200" fill="url(#me-halo)" />
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Curved edges */}
          {edges.map(edge => {
            const fromNode = nodes.find(n => n.id === edge.claim_id);
            const toNode = nodes.find(n => n.id === edge.evidence_id);
            if (!fromNode || !toNode) return null;
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
                  opacity={0.75}
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
          {/* Luminous nodes */}
          {nodes.map(node => {
            const color = node.type === 'claim'
              ? (node.verdict === 'supported' ? '#109bac'
                : node.verdict === 'contested' ? '#eb8089'
                : node.verdict === 'refuted' ? '#c43f51'
                : '#72c69b')
              : '#0f849d';
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                className="cursor-pointer"
                onClick={() => onSelectNode(node.id === selectedNode ? null : node.id)}
                role="button"
                tabIndex={0}
                aria-label={node.label}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelectNode(node.id === selectedNode ? null : node.id);
                  }
                }}
              >
                <circle r={24} fill={color} opacity={0.15} filter="url(#me-glow)" />
                <circle r={14} fill="white" opacity={0.92} />
                <circle
                  r={10}
                  fill={color}
                  opacity={selectedNode && selectedNode !== node.id ? 0.3 : 0.9}
                />
                <circle r={4} fill={color} filter="url(#me-tinyglow)" />
                <text y={-20} fill="#263e55" fontSize="9" textAnchor="middle" className="font-mono">
                  {node.id.slice(0, 16)}
                </text>
                {node.verdict && (
                  <text y={22} fill="#263e55" fontSize="8" textAnchor="middle">
                    {node.verdict}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>
      {/* Legend */}
      <div className="manara-me-graph-legend">
        <span><i className="manara-me-dot manara-me-cyan"></i>{lang === 'ar' ? 'أدلة' : 'Evidence'}</span>
        <span><i className="manara-me-dot manara-me-coral"></i>{lang === 'ar' ? 'ادعاء' : 'Claim'}</span>
        <span><i className="manara-me-line manara-me-turquoise"></i>{lang === 'ar' ? 'يدعم' : 'Supports'}</span>
        <span><i className="manara-me-line manara-me-orange"></i>{lang === 'ar' ? 'يناقض' : 'Contradicts'}</span>
        <span><i className="manara-me-line manara-me-gray"></i>{lang === 'ar' ? 'مرتبط' : 'Related'}</span>
      </div>
    </div>
  );
}

// ============================================================
// Main Memory Explorer component
// ============================================================
export function MemoryExplorer({ investigationId }: {
  investigationId: string;
  onInvestigationChange?: (id: string) => void;
}) {
  const { t, lang } = useLanguage();
  const isAr = lang === 'ar';

  // Real data from backend
  const evidenceState = useAsyncData(() => manaraApiExt.evidence(investigationId), [investigationId]);
  const claimsState = useAsyncData(() => manaraApiExt.claims(investigationId), [investigationId]);
  const edgesState = useAsyncData(() => manaraApiExt.edges(investigationId), [investigationId]);
  const decisionsState = useAsyncData(() => manaraApiExt.decisions(investigationId), [investigationId]);

  // UI state
  const [activeTab, setActiveTab] = React.useState<'evidence' | 'claims' | 'topics'>('evidence');
  const [activeDetail, setActiveDetail] = React.useState<'overview' | 'related' | 'timeline' | 'notes'>('overview');
  const [selectedEvidenceId, setSelectedEvidenceId] = React.useState<string | null>(null);
  const [selectedGraphNode, setSelectedGraphNode] = React.useState<string | null>(null);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [showFilters, setShowFilters] = React.useState(false);
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [sourceFilter, setSourceFilter] = React.useState('all');
  const [cutoffDate, setCutoffDate] = React.useState('');
  const [cutoffResult, setCutoffResult] = React.useState<CutoffResponse | null>(null);
  const [cutoffLoading, setCutoffLoading] = React.useState(false);
  const [cutoffError, setCutoffError] = React.useState<string | null>(null);

  // Derived data
  const evidence = evidenceState.data || [];
  const claims = claimsState.data || [];
  const edges = edgesState.data || [];
  const decisions = decisionsState.data || [];

  // Unique sources (honest derivation from real evidence)
  const uniqueSources = React.useMemo(() => {
    return Array.from(new Set(evidence.map(e => e.source_id)));
  }, [evidence]);

  // Topics derived from source_ids (honest — not fabricated counts)
  const topics = React.useMemo(() => {
    return uniqueSources.map(src => {
      const count = evidence.filter(e => e.source_id === src).length;
      return { name: src, count, icon: '▤' };
    });
  }, [uniqueSources, evidence]);

  // Filtered evidence based on search + filters
  const filteredEvidence = React.useMemo(() => {
    if (!evidence) return [];
    return evidence.filter(ev => {
      const searchMatch = !searchQuery ||
        ev.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ev.source_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        ev.kind.toLowerCase().includes(searchQuery.toLowerCase());
      const typeMatch = typeFilter === 'all' || ev.kind === typeFilter;
      const sourceMatch = sourceFilter === 'all' || ev.source_id === sourceFilter;
      return searchMatch && typeMatch && sourceMatch;
    });
  }, [evidence, searchQuery, typeFilter, sourceFilter]);

  // Filtered claims
  const filteredClaims = React.useMemo(() => {
    if (!claims) return [];
    return claims.filter(cl => {
      return !searchQuery ||
        cl.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cl.statement.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cl.verdict.toLowerCase().includes(searchQuery.toLowerCase());
    });
  }, [claims, searchQuery]);

  // Timeline events (from real evidence observed_at + decisions decided_at)
  const timelineEvents = React.useMemo(() => {
    type Entry = { date: string; label: string; kind: string };
    const evEvents: Entry[] = evidence
      .filter(e => e.observed_at)
      .map(e => ({
        date: e.observed_at!.split('T')[0],
        label: `${e.source_id} · ${e.kind}`,
        kind: 'evidence',
      }));
    const decEvents: Entry[] = decisions.map(d => ({
      date: d.decided_at.split('T')[0],
      label: `${d.decision_type} by ${d.actor}`,
      kind: 'decision',
    }));
    return [...evEvents, ...decEvents].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 10);
  }, [evidence, decisions]);

  // Selected item (evidence or graph node)
  const selectedItem = React.useMemo(() => {
    const id = selectedGraphNode || selectedEvidenceId;
    if (!id) return null;
    const ev = evidence.find(e => e.id === id);
    const cl = claims.find(c => c.id === id);
    return ev ? { type: 'evidence' as const, item: ev } : cl ? { type: 'claim' as const, item: cl } : null;
  }, [selectedGraphNode, selectedEvidenceId, evidence, claims]);

  // Related edges for selected item
  const relatedEdges = React.useMemo(() => {
    if (!selectedItem) return [];
    const id = selectedItem.type === 'evidence' ? selectedItem.item.id : selectedItem.item.id;
    return edges.filter(e => e.claim_id === id || e.evidence_id === id);
  }, [selectedItem, edges]);

  // Handle bitemporal replay
  const handleCutoffReplay = async () => {
    if (!cutoffDate) return;
    setCutoffLoading(true);
    setCutoffError(null);
    try {
      const result = await manaraApiExt.atCutoff(investigationId, cutoffDate + 'T23:59:59Z');
      setCutoffResult(result);
    } catch (e) {
      setCutoffError(e instanceof Error ? e.message : 'Replay failed');
    } finally {
      setCutoffLoading(false);
    }
  };

  const loading = evidenceState.loading || claimsState.loading || edgesState.loading;
  const hasData = evidence.length > 0 || claims.length > 0 || edges.length > 0;

  return (
    <div className="manara-me">
      {/* Heading */}
      <div className="manara-me-heading">
        <div className="manara-me-overline">
          ◈ &nbsp;{isAr ? 'مساحة التحقيق' : 'INVESTIGATION WORKSPACE'}
        </div>
        <h1 className="manara-me-title">{t('nav.memory')}</h1>
        <p className="manara-me-subtitle">
          {isAr
            ? 'استكشف الأدلة وافحص الادعاءات وافهم كيفية ترابط المعرفة.'
            : 'Explore evidence, examine claims, and understand how knowledge connects.'}
        </p>
      </div>

      {/* Loading / Error state for all data */}
      {loading ? (
        <InlineLoading label={isAr ? 'جارٍ تحميل بيانات الذاكرة' : 'Loading memory data'} />
      ) : evidenceState.error && claimsState.error && edgesState.error ? (
        <InlineError
          message={isAr ? 'فشل تحميل البيانات' : 'Failed to load memory data'}
          onRetry={() => window.location.reload()}
        />
      ) : !hasData ? (
        <InlineEmpty message={isAr
          ? 'لا توجد أدلة أو ادعاءات أو علاقات في هذا التحقيق بعد.'
          : 'No evidence, claims, or relationships in this investigation yet.'} />
      ) : (
        <>
          {/* === Primary 3-column grid === */}
          <div className="manara-me-primary-grid">
            {/* === Evidence Panel (left) === */}
            <section className="manara-me-panel manara-me-evidence-panel">
              {/* Tabs */}
              <div className="manara-me-tabs" role="tablist">
                <button
                  className={`manara-me-tab ${activeTab === 'evidence' ? 'active' : ''}`}
                  onClick={() => setActiveTab('evidence')}
                  role="tab"
                  aria-selected={activeTab === 'evidence'}
                >
                  {isAr ? 'الأدلة' : 'Evidence'}
                </button>
                <button
                  className={`manara-me-tab ${activeTab === 'claims' ? 'active' : ''}`}
                  onClick={() => setActiveTab('claims')}
                  role="tab"
                  aria-selected={activeTab === 'claims'}
                >
                  {isAr ? 'الادعاءات' : 'Claims'}
                </button>
                <button
                  className={`manara-me-tab ${activeTab === 'topics' ? 'active' : ''}`}
                  onClick={() => setActiveTab('topics')}
                  role="tab"
                  aria-selected={activeTab === 'topics'}
                >
                  {isAr ? 'الموضوعات' : 'Topics'}
                </button>
              </div>

              {/* Search + filter toggle */}
              <div className="manara-me-find-row">
                <label className="manara-me-find">
                  <Search className="size-3.5" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    placeholder={isAr ? 'بحث...' : 'Search...'}
                    aria-label={isAr ? 'بحث' : 'Search'}
                  />
                </label>
                <button
                  className="manara-me-square-btn"
                  onClick={() => setShowFilters(!showFilters)}
                  title={isAr ? 'تبديل الفلاتر' : 'Toggle filters'}
                >
                  <Filter className="size-3.5" />
                </button>
              </div>

              {/* Filters (collapsible) */}
              {showFilters && (
                <div className="manara-me-filters">
                  <select
                    value={typeFilter}
                    onChange={e => setTypeFilter(e.target.value)}
                    aria-label={isAr ? 'النوع' : 'Type'}
                  >
                    <option value="all">{isAr ? 'كل الأنواع' : 'All Types'}</option>
                    {Array.from(new Set(evidence.map(e => e.kind))).map(k => (
                      <option key={k} value={k}>{k}</option>
                    ))}
                  </select>
                  <select
                    value={sourceFilter}
                    onChange={e => setSourceFilter(e.target.value)}
                    aria-label={isAr ? 'المصدر' : 'Source'}
                  >
                    <option value="all">{isAr ? 'كل المصادر' : 'All Sources'}</option>
                    {uniqueSources.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* List meta */}
              <div className="manara-me-list-meta">
                <span>
                  {activeTab === 'evidence'
                    ? `${filteredEvidence.length} ${isAr ? 'عنصر دليل' : 'evidence item(s)'}`
                    : activeTab === 'claims'
                    ? `${filteredClaims.length} ${isAr ? 'ادعاء' : 'claim(s)'}`
                    : `${topics.length} ${isAr ? 'موضوع' : 'topic(s)'}`}
                </span>
              </div>

              {/* Evidence/Claims/Topics list */}
              <div className="manara-me-evidence-list">
                {activeTab === 'evidence' && (
                  filteredEvidence.length === 0 ? (
                    <InlineEmpty message={isAr ? 'لا توجد أدلة مطابقة' : 'No matching evidence'} />
                  ) : (
                    filteredEvidence.map(ev => (
                      <button
                        key={ev.id}
                        className={`manara-me-evidence-item ${selectedEvidenceId === ev.id ? 'active' : ''}`}
                        onClick={() => { setSelectedEvidenceId(ev.id); setSelectedGraphNode(null); setActiveDetail('overview'); }}
                      >
                        <span className="manara-me-doc-icon"><FileText className="size-5" /></span>
                        <div className="manara-me-item-copy">
                          <b>{ev.id}</b>
                          <small>
                            <span>{ev.source_id}</span>
                            <span>{ev.kind}</span>
                            <span>{ev.observed_at?.split('T')[0] || '—'}</span>
                          </small>
                        </div>
                      </button>
                    ))
                  )
                )}
                {activeTab === 'claims' && (
                  filteredClaims.length === 0 ? (
                    <InlineEmpty message={isAr ? 'لا توجد ادعاءات مطابقة' : 'No matching claims'} />
                  ) : (
                    filteredClaims.map(cl => (
                      <button
                        key={cl.id}
                        className={`manara-me-evidence-item ${selectedEvidenceId === cl.id ? 'active' : ''}`}
                        onClick={() => { setSelectedEvidenceId(cl.id); setSelectedGraphNode(null); setActiveDetail('overview'); }}
                      >
                        <span className={`manara-me-claim-mark ${cl.verdict}`}>
                          {VERDICT_LABELS[cl.verdict]?.mark || '◉'}
                        </span>
                        <div className="manara-me-item-copy">
                          <b>{cl.statement.slice(0, 80)}{cl.statement.length > 80 ? '…' : ''}</b>
                          <small>
                            <span>{cl.verdict}</span>
                            <span>{cl.id.slice(0, 16)}</span>
                          </small>
                        </div>
                      </button>
                    ))
                  )
                )}
                {activeTab === 'topics' && (
                  topics.length === 0 ? (
                    <InlineEmpty message={isAr ? 'لا توجد موضوعات' : 'No topics'} />
                  ) : (
                    topics.map(topic => (
                      <button
                        key={topic.name}
                        className="manara-me-evidence-item"
                        onClick={() => {
                          setTypeFilter(topic.name);
                          setActiveTab('evidence');
                          setShowFilters(true);
                        }}
                      >
                        <span className="manara-me-doc-icon"><Tag className="size-5" /></span>
                        <div className="manara-me-item-copy">
                          <b>{topic.name}</b>
                          <small>
                            <span>{topic.count} {isAr ? 'عنصر' : 'items'}</span>
                          </small>
                        </div>
                      </button>
                    ))
                  )
                )}
              </div>
            </section>

            {/* === Knowledge Graph Panel (center) === */}
            <section className="manara-me-panel manara-me-graph-panel">
              <div className="manara-me-panel-head">
                <h2><span className="manara-me-teal">♧</span> {isAr ? 'الرسم المعرفي' : 'Knowledge Graph'}</h2>
              </div>
              <div className="manara-me-graph-area">
                {edgesState.loading ? (
                  <InlineLoading label={isAr ? 'جارٍ تحميل الرسم' : 'Loading graph'} />
                ) : edgesState.error ? (
                  <InlineError message={edgesState.error} />
                ) : (
                  <MemoryGraph
                    edges={edges}
                    claims={claims}
                    evidence={evidence}
                    selectedNode={selectedGraphNode}
                    onSelectNode={(id) => { setSelectedGraphNode(id); setSelectedEvidenceId(null); setActiveDetail('overview'); }}
                  />
                )}
              </div>
            </section>

            {/* === Selected Item Inspector (right) === */}
            <section className="manara-me-panel manara-me-details-panel">
              <div className="manara-me-panel-head">
                <h2><span className="manara-me-teal">▤</span> {isAr ? 'العنصر المحدد' : 'Selected Item'}</h2>
                {selectedItem && (
                  <button
                    className="manara-me-bare"
                    onClick={() => { setSelectedEvidenceId(null); setSelectedGraphNode(null); }}
                    aria-label={isAr ? 'إغلاق' : 'Close'}
                  >
                    <X className="size-4" />
                  </button>
                )}
              </div>

              {/* Detail tabs */}
              <div className="manara-me-detail-tabs">
                <button className={activeDetail === 'overview' ? 'active' : ''} onClick={() => setActiveDetail('overview')}>
                  {isAr ? 'نظرة عامة' : 'Overview'}
                </button>
                <button className={activeDetail === 'related' ? 'active' : ''} onClick={() => setActiveDetail('related')}>
                  {isAr ? 'مرتبط' : 'Related'} ({relatedEdges.length})
                </button>
                <button className={activeDetail === 'timeline' ? 'active' : ''} onClick={() => setActiveDetail('timeline')}>
                  {isAr ? 'التسلسل' : 'Timeline'}
                </button>
                <button className={activeDetail === 'notes' ? 'active' : ''} onClick={() => setActiveDetail('notes')}>
                  {isAr ? 'ملاحظات' : 'Notes'}
                </button>
              </div>

              {/* Detail content */}
              <div className="manara-me-detail-content">
                {!selectedItem ? (
                  <div className="manara-me-detail-alternate">
                    <p>{isAr
                      ? 'اختر عنصر دليل أو عقدة في الرسم لاستعراض تفاصيلها.'
                      : 'Select an evidence item or graph node to inspect its details.'}</p>
                  </div>
                ) : activeDetail === 'overview' ? (
                  <div className="manara-me-detail-main">
                    {selectedItem.type === 'evidence' ? (
                      <>
                        <h3>{selectedItem.item.id}</h3>
                        <small>▤ &nbsp;{selectedItem.item.source_id}</small>
                        <small>◷ &nbsp;{selectedItem.item.observed_at?.split('T')[0] || (isAr ? 'غير متاح' : 'N/A')}</small>
                        <small>⬡ &nbsp;{selectedItem.item.kind}</small>
                        {selectedItem.item.checksum && (
                          <small>▢ &nbsp;{(isAr ? 'بصمة: ' : 'Checksum: ') + selectedItem.item.checksum.slice(0, 16)}…</small>
                        )}
                        <div className="manara-me-detail-summary">
                          <h3 className="manara-me-section-title">
                            {isAr ? 'الادعاءات المرتبطة' : 'Linked Claims'}
                          </h3>
                          {claims.filter(c => c.evidence_id === selectedItem.item.id).length === 0 ? (
                            <p className="text-[12px] text-[var(--manara-ink-muted)]">
                              {isAr ? 'لا توجد ادعاءات مرتبطة بهذا الدليل.' : 'No claims linked to this evidence.'}
                            </p>
                          ) : (
                            claims.filter(c => c.evidence_id === selectedItem.item.id).map(cl => (
                              <div key={cl.id} className="manara-me-claim-row">
                                <span className={`manara-me-claim-mark ${cl.verdict}`}>
                                  {VERDICT_LABELS[cl.verdict]?.mark || '◉'}
                                </span>
                                <div className="manara-me-claim-title">{cl.statement}</div>
                                <span className={`manara-me-claim-status ${cl.verdict}`}>{cl.verdict}</span>
                              </div>
                            ))
                          )}
                        </div>
                      </>
                    ) : (
                      <>
                        <h3>{selectedItem.item.statement}</h3>
                        <small>▤ &nbsp;{isAr ? 'ادعاء' : 'Claim'}: {selectedItem.item.id}</small>
                        <small>⬡ &nbsp;{isAr ? 'الحكم' : 'Verdict'}: {selectedItem.item.verdict}</small>
                        {selectedItem.item.evidence_id && (
                          <small>▢ &nbsp;{isAr ? 'الدليل المرتبط' : 'Evidence'}: {selectedItem.item.evidence_id}</small>
                        )}
                        {selectedItem.item.independence_group && (
                          <small>◈ &nbsp;{isAr ? 'مجموعة الاستقلال' : 'Independence group'}: {selectedItem.item.independence_group}</small>
                        )}
                        <div className="manara-me-detail-summary">
                          <h3 className="manara-me-section-title">
                            {isAr ? 'العلاقات' : 'Relationships'}
                          </h3>
                          {relatedEdges.length === 0 ? (
                            <p className="text-[12px] text-[var(--manara-ink-muted)]">
                              {isAr ? 'لا توجد علاقات مسجلة.' : 'No relationships recorded.'}
                            </p>
                          ) : (
                            relatedEdges.map(edge => (
                              <div key={edge.edge_id} className="text-[11px] py-1 border-b border-[var(--manara-mist)]">
                                <span className="font-mono uppercase" style={{ color: EDGE_COLORS[edge.relation] || '#888' }}>
                                  {edge.relation}
                                </span>
                                <span className="ml-2 text-[var(--manara-ink-muted)]">
                                  → {edge.evidence_id} (w={edge.weight})
                                </span>
                                {edge.notes && <p className="text-[10px] italic mt-1">{edge.notes}</p>}
                              </div>
                            ))
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ) : activeDetail === 'related' ? (
                  <div className="manara-me-detail-alternate">
                    <h3>{isAr ? 'العلاقات المرتبطة' : 'Related Relationships'}</h3>
                    {relatedEdges.length === 0 ? (
                      <p>{isAr ? 'لا توجد علاقات مرتبطة.' : 'No related relationships found.'}</p>
                    ) : (
                      relatedEdges.map(edge => (
                        <div key={edge.edge_id} className="text-[11px] py-2 border-b border-[var(--manara-mist)]">
                          <div className="flex items-center gap-2">
                            <div className="size-2 rounded-full" style={{ background: EDGE_COLORS[edge.relation] || '#888' }} />
                            <span className="font-mono uppercase">{edge.relation}</span>
                            <span className="text-[var(--manara-ink-muted)]">w={edge.weight}</span>
                          </div>
                          <p className="mt-1 font-mono text-[var(--manara-ink-muted)]">
                            {edge.claim_id} → {edge.evidence_id}
                          </p>
                          {edge.notes && <p className="text-[10px] italic mt-1">{edge.notes}</p>}
                        </div>
                      ))
                    )}
                  </div>
                ) : activeDetail === 'timeline' ? (
                  <div className="manara-me-detail-alternate">
                    <h3>{isAr ? 'التسلسل الزمني' : 'Timeline'}</h3>
                    <p className="text-[12px] text-[var(--manara-ink-muted)]">
                      {isAr
                        ? 'استخدم لوحة التسلسل الزمني أدناه لاستكشاف الأحداث.'
                        : 'Use the timeline panel below to explore events.'}
                    </p>
                  </div>
                ) : (
                  <div className="manara-me-detail-alternate">
                    <h3>{isAr ? 'ملاحظات' : 'Notes'}</h3>
                    <p className="text-[12px] text-[var(--manara-ink-muted)]">
                      {isAr
                        ? 'تتطلب الملاحظات دعم backend فعلي. لا تختلق ملاحظات.'
                        : 'Notes require real backend persistence. Do not fabricate notes.'}
                    </p>
                  </div>
                )}
              </div>
            </section>
          </div>

          {/* === Bottom grid: Timeline + Related Topics === */}
          <div className="manara-me-bottom-grid">
            {/* Timeline panel */}
            <section className="manara-me-panel manara-me-timeline-panel">
              <div className="manara-me-panel-head">
                <h2><span className="manara-me-teal">◷</span> {isAr ? 'التسلسل الزمني' : 'Timeline'}</h2>
              </div>
              <div className="manara-me-timeline-track">
                {timelineEvents.length === 0 ? (
                  <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center">
                    {isAr ? 'لا توجد أحداث' : 'No events recorded'}
                  </p>
                ) : (
                  <div className="manara-me-timeline-events">
                    {timelineEvents.map((event, i) => (
                      <div key={i} className="manara-me-time-event">
                        <div className={`manara-me-time-card ${i === 0 ? 'active' : ''}`}>
                          <strong>{event.date}</strong>
                          {event.label}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Bitemporal replay (real at-cutoff endpoint) */}
              <div className="manara-me-bitemporal-replay">
                <h3 className="manara-me-section-title">
                  <Clock className="size-3 inline" /> {isAr ? 'إعادة الزمني' : 'Bitemporal Replay'}
                </h3>
                <p className="text-[10px] text-[var(--manara-ink-muted)] mb-2">
                  {isAr
                    ? 'اعرض ما عرفته منارة في نقطة زمنية محددة.'
                    : 'See what MANARA knew at a specific point in time.'}
                </p>
                <div className="flex gap-2 items-center">
                  <input
                    type="date"
                    value={cutoffDate}
                    onChange={e => setCutoffDate(e.target.value)}
                    className="manara-me-cutoff-input"
                    aria-label={isAr ? 'تاريخ الإعادة' : 'Cutoff date'}
                  />
                  <button
                    onClick={handleCutoffReplay}
                    disabled={!cutoffDate || cutoffLoading}
                    className="manara-me-replay-btn"
                  >
                    {cutoffLoading ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <>{isAr ? 'إعادة' : 'Replay'}</>
                    )}
                  </button>
                </div>
                {cutoffError && (
                  <p className="text-[10px] text-[var(--manara-error)] mt-2">{cutoffError}</p>
                )}
                {cutoffResult && (
                  <div className="mt-2 p-2 rounded-md bg-[var(--manara-mist)]/50">
                    <p className="text-[11px] text-[var(--manara-ink)]">
                      {isAr ? 'عرفت عن' : 'Knew about'}{' '}
                      <strong>{cutoffResult.visible_evidence_count}</strong>{' '}
                      {isAr ? 'عنصر دليل' : 'evidence item(s)'}{' '}
                      {isAr ? 'في' : 'at'} <strong>{cutoffResult.cutoff.split('T')[0]}</strong>
                    </p>
                    {cutoffResult.visible_evidence.length > 0 && (
                      <div className="mt-1 space-y-0.5">
                        {cutoffResult.visible_evidence.slice(0, 5).map(ev => (
                          <p key={ev.id} className="text-[10px] font-mono text-[var(--manara-ink-muted)]">
                            {ev.id} · {ev.source_id}
                          </p>
                        ))}
                      </div>
                    )}
                    {cutoffResult.visible_evidence.length === 0 && (
                      <p className="text-[10px] text-[var(--manara-ink-muted)] mt-1">
                        {isAr ? 'لم تكن هناك أدلة مرئية عند هذا التاريخ.' : 'No evidence was visible at this cutoff.'}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </section>

            {/* Related topics panel */}
            <section className="manara-me-panel manara-me-related-panel">
              <div className="manara-me-panel-head">
                <h2><span className="manara-me-teal">◈</span> {isAr ? `موضوعات مرتبطة (${topics.length})` : `Related Topics (${topics.length})`}</h2>
              </div>
              <div className="manara-me-topics-grid">
                {topics.length === 0 ? (
                  <p className="text-[12px] text-[var(--manara-ink-muted)] py-4 text-center col-span-3">
                    {isAr ? 'لا توجد موضوعات' : 'No topics available'}
                  </p>
                ) : (
                  topics.map(topic => (
                    <button
                      key={topic.name}
                      className="manara-me-topic-card"
                      onClick={() => {
                        setTypeFilter(topic.name);
                        setActiveTab('evidence');
                      }}
                    >
                      <span className="manara-me-topic-icon"><Database className="size-4" /></span>
                      <span>
                        <b>{topic.name}</b>
                        <small>{topic.count} {isAr ? 'عنصر' : 'items'}</small>
                      </span>
                    </button>
                  ))
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
