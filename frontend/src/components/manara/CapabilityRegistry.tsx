/* ============================================================
   MANARA — Capability Registry (Page 04) — OWNER-APPROVED SOURCE v1
   Source: MANARA_PAGE_04_CAPABILITY_REGISTRY_EN_AR_OWNER_APPROVED_SOURCE_v1.zip
   (blob SHA 8c2427b208c2b4fc0ba1ff013e8e2cb120c5e110)

   3-panel layout:
   - Left: Capability catalog (search, filters, list)
   - Center: Selected capability details (tabs)
   - Right: Capability Ecosystem relationship graph (SVG, zoom)
   Bottom: Versions, Integrations, Dependencies, Related

   All data from real backend: GET /registry/capabilities
   No fixture data, no fabricated statuses.
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';
import {
  Loader2, AlertCircle, RefreshCw, Search,
  Plus, Minus, Maximize2, Layers, Database, Network,
} from 'lucide-react';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8000';

// ============================================================
// Types — matching backend CapabilityResponse
// ============================================================
interface Capability {
  id: string;
  display_name: string;
  description_long: string;
  status: string;
  version: string;
  kind: string;
  domains: string[];
  subdomains: string[];
  tags: string[];
  keywords_ar: string[];
  keywords_en: string[];
  search_purposes: string[];
  data_types: string[];
  languages: string[];
  positive_examples: string[];
  negative_examples: string[];
  graph: {
    uses_connector: string[];
    complements: string[];
    specializes: string[];
    replaces: string[];
    conflicts_with: string[];
  };
  author: string;
  created_at: string;
  updated_at: string;
  connector_ids: string[];
  quality_contract: Record<string, unknown>;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  temporal_coverage: { earliest: string; latest: string };
  freshness_policy: string;
  forecast_relevance: string;
}

// interface DataState<T> {
//   data: T | null;
//   loading: boolean;
//   error: string | null;
// }

// REMOVED: useAsyncData (unused)<T>(fn: () => Promise<T>, deps: unknown[]): DataState<T> {
  // const [state, setState] = React.useState<DataState<T>>({ data: null, loading: true, error: null });
  // React.useEffect(() => {
  //   let cancelled = false;
  //   setState(s => ({ ...s, loading: true, error: null }));
  //   fn()
  //     .then(data => { if (!cancelled) setState({ data, loading: false, error: null }); })
  //     .catch(e => {
  //       if (!cancelled) {
  //         const msg = e instanceof Error ? e.message : 'Failed to load';
  //         setState({ data: null, loading: false, error: msg });
  //       }
  //     });
  //   return () => { cancelled = true; };
  // }, deps);
  // return state;
// }

// ============================================================
// Status badge colors
// ============================================================
// REMOVED: STATUS_COLORS (unused): Record<string, string> = {
  // candidate: 'bg-amber-100 text-amber-700',
  // approved: 'bg-green-100 text-green-700',
  // rejected: 'bg-red-100 text-red-700',
  // discovered: 'bg-gray-100 text-gray-600',
  // assessed: 'bg-blue-100 text-blue-700',
  // sandbox_tested: 'bg-teal-100 text-teal-700',
  // review_pending: 'bg-orange-100 text-orange-700',
  // quarantined: 'bg-red-100 text-red-700',
  // degraded: 'bg-orange-100 text-orange-700',
  // retired: 'bg-gray-100 text-gray-500',
// };

const STATUS_LABELS_AR: Record<string, string> = {
  candidate: 'مرشّح',
  approved: 'معتمد',
  rejected: 'مرفوض',
  discovered: 'مكتشف',
  assessed: 'مقيّم',
  sandbox_tested: 'مختبَر',
  review_pending: 'بانتظار المراجعة',
  quarantined: 'محجَر عليه',
  degraded: 'متدهور',
  retired: 'متقاعد',
};

// ============================================================
// Main Capability Registry component
// ============================================================
export function CapabilityRegistry() {
  const { t, lang } = useLanguage();
  const isAr = lang === 'ar';

  // State
  const [capabilities, setCapabilities] = React.useState<Capability[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [domainFilter, setDomainFilter] = React.useState('all');
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [activeTab, setActiveTab] = React.useState<'overview' | 'config' | 'examples' | 'related'>('overview');
  const [zoom, setZoom] = React.useState(1);

  // Fetch capabilities from real backend
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/registry/capabilities`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (cancelled) return;
        const caps = data.capabilities || data || [];
        setCapabilities(caps);
        if (caps.length > 0) setSelectedId(caps[0].id);
        setLoading(false);
      })
      .catch(e => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Failed to load capabilities');
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // Derived data
  const allDomains = React.useMemo(() => {
    return Array.from(new Set(capabilities.flatMap(c => c.domains || []))).sort();
  }, [capabilities]);

  const allStatuses = React.useMemo(() => {
    return Array.from(new Set(capabilities.map(c => c.status))).sort();
  }, [capabilities]);

  const allKinds = React.useMemo(() => {
    return Array.from(new Set(capabilities.map(c => c.kind))).sort();
  }, [capabilities]);

  const filteredCapabilities = React.useMemo(() => {
    return capabilities.filter(c => {
      const searchMatch = !searchQuery ||
        c.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.description_long || '').toLowerCase().includes(searchQuery.toLowerCase());
      const domainMatch = domainFilter === 'all' || (c.domains || []).includes(domainFilter);
      const statusMatch = statusFilter === 'all' || c.status === statusFilter;
      const typeMatch = typeFilter === 'all' || c.kind === typeFilter;
      return searchMatch && domainMatch && statusMatch && typeMatch;
    });
  }, [capabilities, searchQuery, domainFilter, statusFilter, typeFilter]);

  const selected = React.useMemo(() => {
    return capabilities.find(c => c.id === selectedId) || null;
  }, [capabilities, selectedId]);

  // Graph nodes: selected capability + its relationships
  const graphNodes = React.useMemo(() => {
    if (!selected) return [];
    const nodes: { id: string; label: string; x: number; y: number; isCenter: boolean; rel: string }[] = [];
    const centerNode = { id: selected.id, label: selected.display_name, x: 200, y: 237, isCenter: true, rel: 'center' };
    nodes.push(centerNode);

    const relationships: { type: string; ids: string[] }[] = [
      { type: 'complements', ids: selected.graph?.complements || [] },
      { type: 'specializes', ids: selected.graph?.specializes || [] },
      { type: 'replaces', ids: selected.graph?.replaces || [] },
      { type: 'conflicts_with', ids: selected.graph?.conflicts_with || [] },
      { type: 'uses_connector', ids: selected.graph?.uses_connector || [] },
    ];

    let angle = 0;
    for (const { type, ids } of relationships) {
      for (const id of ids) {
        const cap = capabilities.find(c => c.id === id);
        const label = cap ? cap.display_name : id;
        const radius = 180;
        const x = 200 + Math.cos(angle) * radius;
        const y = 237 + Math.sin(angle) * radius;
        nodes.push({ id, label, x, y, isCenter: false, rel: type });
        angle += 0.6;
      }
    }
    return nodes;
  }, [selected, capabilities]);

  const EDGE_COLORS: Record<string, string> = {
    complements: '#52caa1',
    specializes: '#48b6df',
    replaces: '#ff8187',
    conflicts_with: '#e1ad23',
    uses_connector: '#9865e8',
  };

  // Render
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-20 justify-center">
        <Loader2 className="size-5 animate-spin text-[var(--manara-teal)]" />
        <span className="text-[13px] text-[var(--manara-ink-muted)]">
          {isAr ? 'جارٍ تحميل القدرات...' : 'Loading capabilities...'}
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-20 text-center">
        <AlertCircle className="size-5 text-[var(--manara-error)] mx-auto mb-2" />
        <p className="text-[13px] text-[var(--manara-error)]">{error}</p>
        <button onClick={() => window.location.reload()} className="mt-3 text-[12px] text-[var(--manara-teal)] hover:underline">
          <RefreshCw className="size-3 inline" /> {isAr ? 'إعادة' : 'Retry'}
        </button>
      </div>
    );
  }

  if (capabilities.length === 0) {
    return (
      <div className="py-20 text-center">
        <Layers className="size-8 mx-auto mb-2 opacity-30" />
        <p className="text-[13px] text-[var(--manara-ink-muted)]">
          {isAr ? 'لا توجد قدرات مسجلة بعد.' : 'No capabilities registered yet.'}
        </p>
      </div>
    );
  }

  return (
    <div className="manara-cr">
      {/* Heading */}
      <div className="manara-cr-heading">
        <div className="manara-cr-overline">{isAr ? 'سجل القدرات' : 'CAPABILITY REGISTRY'}</div>
        <h1 className="manara-cr-title">{t('nav.registry')}</h1>
        <p className="manara-cr-subtitle">
          {isAr
            ? 'تصفح القدرات المتاحة في النظام وابحث واستكشف علاقاتها.'
            : 'Browse, search, and explore available capabilities and their relationships.'}
        </p>
      </div>

      {/* 3-column panels grid */}
      <div className="manara-cr-panels">
        {/* === Registry panel (left) === */}
        <section className="manara-cr-panel manara-cr-registry">
          <div className="manara-cr-registry-heading">
            <div>
              <h2 className="manara-cr-registry-h2">{isAr ? 'قائمة القدرات' : 'Capability List'}</h2>
              <p className="text-[11px] text-[var(--manara-ink-muted)]">
                {filteredCapabilities.length} {isAr ? 'قدرة' : 'capabilities'}
              </p>
            </div>
          </div>

          {/* Search */}
          <div className="manara-cr-search-row">
            <Search className="size-4 text-[var(--manara-ink-muted)]" />
            <input
              type="search"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder={isAr ? 'البحث في القدرات...' : 'Search capabilities...'}
              aria-label={isAr ? 'البحث' : 'Search'}
            />
          </div>

          {/* Filters */}
          <div className="manara-cr-filters">
            <select value={domainFilter} onChange={e => setDomainFilter(e.target.value)} aria-label={isAr ? 'المجال' : 'Domain'}>
              <option value="all">{isAr ? 'جميع المجالات' : 'All Domains'}</option>
              {allDomains.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} aria-label={isAr ? 'الحالة' : 'Status'}>
              <option value="all">{isAr ? 'جميع الحالات' : 'All Statuses'}</option>
              {allStatuses.map(s => <option key={s} value={s}>{isAr ? (STATUS_LABELS_AR[s] || s) : s}</option>)}
            </select>
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} aria-label={isAr ? 'النوع' : 'Type'}>
              <option value="all">{isAr ? 'جميع الأنواع' : 'All Types'}</option>
              {allKinds.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          {/* Capability list */}
          <div className="manara-cr-cap-list">
            {filteredCapabilities.length === 0 ? (
              <p className="text-[12px] text-[var(--manara-ink-muted)] py-8 text-center">
                {isAr ? 'لا توجد قدرات مطابقة' : 'No matching capabilities'}
              </p>
            ) : (
              filteredCapabilities.map(cap => (
                <button
                  key={cap.id}
                  className={`manara-cr-cap-row ${selectedId === cap.id ? 'selected' : ''}`}
                  onClick={() => { setSelectedId(cap.id); setActiveTab('overview'); }}
                >
                  <span className="manara-cr-cap-icon"><Layers className="size-6" /></span>
                  <div className="manara-cr-cap-copy">
                    <strong>{cap.display_name}</strong>
                    <small>{cap.id} · {cap.kind}</small>
                  </div>
                  <span className={`manara-cr-badge ${cap.status}`}>
                    {isAr ? (STATUS_LABELS_AR[cap.status] || cap.status) : cap.status}
                  </span>
                </button>
              ))
            )}
          </div>
        </section>

        {/* === Detail panel (center) === */}
        <section className="manara-cr-panel manara-cr-detail">
          {selected ? (
            <>
              {/* Detail header */}
              <div className="manara-cr-detail-top">
                <div className="manara-cr-detail-header">
                  <span className="manara-cr-cap-icon manara-cr-detail-icon"><Layers className="size-7" /></span>
                  <div>
                    <h2 className="manara-cr-detail-h2">{selected.display_name}</h2>
                    <div className="manara-cr-pills">
                      <span className="manara-cr-pill">{selected.id}</span>
                      <span className="manara-cr-pill">{selected.kind}</span>
                      <span className={`manara-cr-badge ${selected.status}`}>
                        {isAr ? (STATUS_LABELS_AR[selected.status] || selected.status) : selected.status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="manara-cr-description">
                <h3 className="manara-cr-section-title">{isAr ? 'الوصف' : 'Description'}</h3>
                <p>{selected.description_long}</p>
              </div>

              {/* Metadata grid */}
              <dl className="manara-cr-metadata">
                <div>
                  <dt>{isAr ? 'الإصدار' : 'Version'}</dt>
                  <dd>{selected.version}</dd>
                </div>
                <div>
                  <dt>{isAr ? 'النوع' : 'Type'}</dt>
                  <dd>{selected.kind}</dd>
                </div>
                <div>
                  <dt>{isAr ? 'المجالات' : 'Domains'}</dt>
                  <dd>{(selected.domains || []).join(', ')}</dd>
                </div>
                  <div>
                  <dt>{isAr ? 'آخر تحديث' : 'Updated'}</dt>
                  <dd>{selected.updated_at?.split('T')[0] || '—'}</dd>
                </div>
              </dl>

              {/* Detail tabs */}
              <div className="manara-cr-detail-tabs">
                <button className={activeTab === 'overview' ? 'current' : ''} onClick={() => setActiveTab('overview')}>
                  {isAr ? 'نظرة عامة' : 'Overview'}
                </button>
                <button className={activeTab === 'config' ? 'current' : ''} onClick={() => setActiveTab('config')}>
                  {isAr ? 'الإعدادات' : 'Config'}
                </button>
                <button className={activeTab === 'examples' ? 'current' : ''} onClick={() => setActiveTab('examples')}>
                  {isAr ? 'أمثلة' : 'Examples'}
                </button>
                <button className={activeTab === 'related' ? 'current' : ''} onClick={() => setActiveTab('related')}>
                  {isAr ? 'مرتبط' : 'Related'}
                </button>
              </div>

              {/* Tab content */}
              <div className="manara-cr-tab-content">
                {activeTab === 'overview' && (
                  <>
                    <h3 className="manara-cr-section-title">{isAr ? 'الوظائف الرئيسية' : 'Key Functions'}</h3>
                    <ul className="manara-cr-checklist">
                      {(selected.search_purposes || []).map((purpose, i) => (
                        <li key={i}>
                          <span>✓</span>
                          {purpose}
                        </li>
                      ))}
                      {(selected.search_purposes || []).length === 0 && (
                        <li><span>—</span>{isAr ? 'لا توجد وظائف مسجلة' : 'No functions recorded'}</li>
                      )}
                    </ul>
                  </>
                )}
                {activeTab === 'config' && (
                  <>
                    <h3 className="manara-cr-section-title">{isAr ? 'الإعدادات' : 'Configuration'}</h3>
                    <p className="text-[12px] text-[var(--manara-ink-muted)]">
                      <strong>{isAr ? 'سياسة التحديث:' : 'Freshness policy:'}</strong> {selected.freshness_policy || '—'}<br />
                      <strong>{isAr ? 'الصلة بالتنبؤ:' : 'Forecast relevance:'}</strong> {selected.forecast_relevance || '—'}<br />
                      <strong>{isAr ? 'التغطية الزمنية:' : 'Temporal coverage:'}</strong> {selected.temporal_coverage?.earliest || '—'} → {selected.temporal_coverage?.latest || '—'}<br />
                      <strong>{isAr ? 'اللغات:' : 'Languages:'}</strong> {(selected.languages || []).join(', ')}<br />
                      <strong>{isAr ? 'أنواع البيانات:' : 'Data types:'}</strong> {(selected.data_types || []).join(', ')}
                    </p>
                  </>
                )}
                {activeTab === 'examples' && (
                  <>
                    <h3 className="manara-cr-section-title">{isAr ? 'أمثلة إيجابية' : 'Positive Examples'}</h3>
                    <ul className="manara-cr-checklist">
                      {(selected.positive_examples || []).slice(0, 5).map((ex, i) => (
                        <li key={i}><span>✓</span>{ex}</li>
                      ))}
                    </ul>
                    {selected.negative_examples && selected.negative_examples.length > 0 && (
                      <>
                        <h3 className="manara-cr-section-title mt-4">{isAr ? 'أمثلة سلبية' : 'Negative Examples'}</h3>
                        <ul className="manara-cr-checklist">
                          {selected.negative_examples.slice(0, 3).map((ex, i) => (
                            <li key={i}><span style={{ background: '#c44545' }}>✕</span>{ex}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </>
                )}
                {activeTab === 'related' && (
                  <>
                    <h3 className="manara-cr-section-title">{isAr ? 'العلاقات' : 'Relationships'}</h3>
                    {graphNodes.length <= 1 ? (
                      <p className="text-[12px] text-[var(--manara-ink-muted)]">
                        {isAr ? 'لا توجد علاقات مسجلة لهذه القدرة.' : 'No relationships recorded for this capability.'}
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {graphNodes.filter(n => !n.isCenter).map((node, i) => (
                          <div key={i} className="text-[11px] py-2 border-b border-[var(--manara-mist)]">
                            <span className="font-mono uppercase" style={{ color: EDGE_COLORS[node.rel] || '#888' }}>
                              {node.rel}
                            </span>
                            <span className="ml-2 text-[var(--manara-ink)]">{node.label}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          ) : (
            <div className="manara-cr-detail-empty">
              <p>{isAr ? 'اختر قدرة لاستعراض تفاصيلها.' : 'Select a capability to inspect its details.'}</p>
            </div>
          )}
        </section>

        {/* === Ecosystem panel (right) === */}
        <section className="manara-cr-panel manara-cr-ecosystem">
          <div className="manara-cr-panel-head">
            <h2 className="manara-cr-ecosystem-h2">
              <span className="manara-cr-teal">ⓘ</span> {isAr ? 'نظام القدرات' : 'Capability Ecosystem'}
            </h2>
            <button onClick={() => setZoom(1)} className="manara-cr-icon-btn" aria-label={isAr ? 'إعادة' : 'Reset'}>
              <Maximize2 className="size-4" />
            </button>
          </div>
          <div className="manara-cr-graph-frame">
            {graphNodes.length <= 1 ? (
              <div className="manara-cr-graph-empty">
                <Network className="size-8 mx-auto mb-2 opacity-30" />
                <p className="text-[12px] text-[var(--manara-ink-muted)]">
                  {isAr ? 'لا توجد علاقات لعرضها' : 'No relationships to display'}
                </p>
              </div>
            ) : (
              <svg
                viewBox="0 0 400 475"
                className="manara-cr-graph-svg"
                role="img"
                aria-label={isAr ? 'رسم علاقات القدرات' : 'Capability relationship graph'}
              >
                <g transform={`translate(${200 * (1 - zoom)}, ${240 * (1 - zoom)}) scale(${zoom})`}>
                  {/* Edges */}
                  {graphNodes.filter(n => !n.isCenter).map((node, i) => {
                    const center = graphNodes[0];
                    const midX = (center.x + node.x) / 2 + (i % 2 ? 12 : -12);
                    const midY = (center.y + node.y) / 2;
                    return (
                      <path
                        key={i}
                        d={`M ${center.x} ${center.y} Q ${midX} ${midY} ${node.x} ${node.y}`}
                        stroke={EDGE_COLORS[node.rel] || '#888'}
                        strokeWidth="2"
                        fill="none"
                        opacity="0.7"
                      />
                    );
                  })}
                  {/* Nodes */}
                  {graphNodes.map((node, i) => (
                    <g
                      key={i}
                      className="cursor-pointer"
                      transform={`translate(${node.x},${node.y})`}
                      role="button"
                      tabIndex={0}
                      aria-label={node.label}
                      onClick={() => { if (!node.isCenter) setSelectedId(node.id); }}
                      onKeyDown={e => { if ((e.key === 'Enter' || e.key === ' ') && !node.isCenter) { e.preventDefault(); setSelectedId(node.id); } }}
                    >
                      <circle r={node.isCenter ? 39 : 30} fill={node.isCenter ? '#e2f0ff' : '#f8fafd'} />
                      <circle r={node.isCenter ? 28 : 20} fill={node.isCenter ? '#086ff2' : 'transparent'} stroke={node.isCenter ? '#7baeff' : '#dce8f7'} strokeWidth={node.isCenter ? 3 : 2} />
                      <text y="5" textAnchor="middle" fill={node.isCenter ? '#fff' : '#1864ad'} fontSize={node.isCenter ? 14 : 11} fontWeight="700">
                        {node.isCenter ? '◆' : '◈'}
                      </text>
                      <text y={node.isCenter ? 55 : 45} textAnchor="middle" fontSize="10" fontWeight="600" fill="#15385b">
                        {node.label.length > 20 ? node.label.slice(0, 19) + '…' : node.label}
                      </text>
                    </g>
                  ))}
                </g>
              </svg>
            )}
          </div>
          {/* Graph controls */}
          <div className="manara-cr-graph-controls">
            <button onClick={() => setZoom(z => Math.max(0.65, z - 0.1))} aria-label="Zoom out"><Minus className="size-3" /></button>
            <span className="text-[12px] px-2 text-[var(--manara-ink-muted)]">{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom(z => Math.min(1.5, z + 0.1))} aria-label="Zoom in"><Plus className="size-3" /></button>
            <button onClick={() => setZoom(1)}>{isAr ? 'إعادة' : 'Reset'}</button>
          </div>
        </section>
      </div>

      {/* Bottom panels */}
      <div className="manara-cr-bottom-panels">
        {/* Versions */}
        <div className="manara-cr-bottom-card">
          <div className="manara-cr-bottom-head">
            <h3>{isAr ? 'الإصدارات' : 'Versions'}</h3>
          </div>
          <div className="manara-cr-bottom-list">
            <div className="manara-cr-mini-row">
              <span className="manara-cr-mini-icon"><Layers className="size-3" /></span>
              <span className="manara-cr-mini-main">v{selected?.version || '—'}
                <small>{isAr ? 'الإصدار الحالي' : 'Current version'}</small>
              </span>
            </div>
          </div>
        </div>

        {/* Integrations */}
        <div className="manara-cr-bottom-card">
          <div className="manara-cr-bottom-head">
            <h3>{isAr ? 'التكاملات' : 'Integrations'}</h3>
          </div>
          <div className="manara-cr-bottom-list">
            {(selected?.connector_ids || []).length > 0 ? (
              selected?.connector_ids?.map((conn, i) => (
                <div key={i} className="manara-cr-mini-row">
                  <span className="manara-cr-mini-icon"><Database className="size-3" /></span>
                  <span className="manara-cr-mini-main">{conn}</span>
                </div>
              ))
            ) : (
              <p className="text-[10px] text-[var(--manara-ink-muted)] py-2">
                {isAr ? 'لا توجد موصلات مسجلة' : 'No connectors registered'}
              </p>
            )}
          </div>
        </div>

        {/* Dependencies */}
        <div className="manara-cr-bottom-card">
          <div className="manara-cr-bottom-head">
            <h3>{isAr ? 'الاعتماديات' : 'Dependencies'}</h3>
          </div>
          <div className="manara-cr-bottom-list">
            {graphNodes.filter(n => !n.isCenter).length > 0 ? (
              graphNodes.filter(n => !n.isCenter).map((node, i) => (
                <div key={i} className="manara-cr-mini-row">
                  <span className="manara-cr-mini-icon" style={{ background: EDGE_COLORS[node.rel] ? `${EDGE_COLORS[node.rel]}20` : '#e5f2ff' }}>
                    ◈
                  </span>
                  <span className="manara-cr-mini-main">{node.label}
                    <small>{node.rel}</small>
                  </span>
                </div>
              ))
            ) : (
              <p className="text-[10px] text-[var(--manara-ink-muted)] py-2">
                {isAr ? 'لا توجد اعتماديات' : 'No dependencies'}
              </p>
            )}
          </div>
        </div>

        {/* Related capabilities */}
        <div className="manara-cr-bottom-card">
          <div className="manara-cr-bottom-head">
            <h3>{isAr ? 'قدرات ذات صلة' : 'Related Capabilities'}</h3>
          </div>
          <div className="manara-cr-bottom-list">
            {capabilities.filter(c => c.id !== selectedId).slice(0, 4).map(cap => (
              <div
                key={cap.id}
                className="manara-cr-mini-row cursor-pointer"
                onClick={() => { setSelectedId(cap.id); setActiveTab('overview'); }}
              >
                <span className="manara-cr-mini-icon"><Layers className="size-3" /></span>
                <span className="manara-cr-mini-main">{cap.display_name}
                  <small>{cap.id}</small>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
