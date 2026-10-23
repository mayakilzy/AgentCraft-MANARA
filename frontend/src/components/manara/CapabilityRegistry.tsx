/* ============================================================
   MANARA — Capability Registry (Page 04 v2) — VISUAL SOURCE CORRECTION
   Source: MANARA_PAGE_04_VISUAL_SOURCE_CORRECTION_v2.zip
   (blob SHA f7ad5ea807c14cb51417d20a5d984fcc7de17b9e)

   DOM + CSS ported from v2 app.js shell() function.
   Existing app shell (Sidebar/Header) reused — only workspace content.
   Real backend data via GET /registry/capabilities.
   ============================================================ */

import * as React from 'react';
import { useLanguage } from './i18n';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || 'http://127.0.0.1:8000';

// v2 data shape (from README adapter contract)
interface CapItem {
  id: string; name_en: string; name_ar?: string;
  description_en: string; description_ar?: string;
  type: string; type_ar?: string; icon: string; status: string;
  version: string; domain_en: string; domain_ar?: string; updated: string;
  features_en: string[]; features_ar?: string[];
  relationships: { id: string; name_en: string; name_ar?: string; symbol: string; color: string }[];
  versions: { name: string; sub?: string; tag?: string }[];
  tests: { name: string; tag?: string }[];
  integrations: { name: string; sub?: string }[];
}

const REL_COLORS = ['#965aff', '#ff6369', '#1dbcc6', '#e93e9a', '#4389ff', '#e9a400', '#28b875'];
const REL_SYMBOLS = ['▤', '▧', '✣', '▥', '▤', '⚙', '▽'];

// Map backend CapabilityResponse → v2 CapItem
function mapBackend(data: Record<string, unknown>[]): CapItem[] {
  return data.map((c, _i) => {
    const graph = c.graph as { complements?: string[]; specializes?: string[]; replaces?: string[]; conflicts_with?: string[] } | undefined;
    const allRels = [
      ...(graph?.complements || []),
      ...(graph?.specializes || []),
      ...(graph?.replaces || []),
      ...(graph?.conflicts_with || []),
    ];
    return {
      id: c.id as string,
      name_en: c.display_name as string,
      name_ar: c.display_name as string,
      description_en: (c.description_long as string) || '',
      description_ar: (c.description_long as string) || '',
      type: (c.kind as string) || 'capability',
      type_ar: (c.kind as string) || 'capability',
      icon: '▤',
      status: c.status === 'approved' ? 'active' : c.status === 'candidate' ? 'beta' : 'off',
      version: `v${c.version}` || 'v0.1.0',
      domain_en: ((c.domains as string[]) || ['Other'])[0],
      domain_ar: ((c.domains as string[]) || ['Other'])[0],
      updated: ((c.updated_at as string) || '').split('T')[0],
      features_en: (c.search_purposes as string[]) || [],
      features_ar: (c.search_purposes as string[]) || [],
      relationships: allRels.slice(0, 7).map((id, j) => ({
        id, name_en: id, name_ar: id, symbol: REL_SYMBOLS[j % 7], color: REL_COLORS[j % 7],
      })),
      versions: [{ name: `v${c.version}`, sub: ((c.updated_at as string) || '').split('T')[0], tag: 'Current' }],
      tests: [],
      integrations: ((c.connector_ids as string[]) || []).map(id => ({ name: id })),
    };
  });
}

export function CapabilityRegistry() {
  const { lang } = useLanguage();
  const ar = lang === 'ar';
  const t = (en: string, a: string) => ar ? a : en;

  const [items, setItems] = React.useState<CapItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState('functions');
  const [q, setQ] = React.useState('');
  const [fStatus, setFStatus] = React.useState('all');
  const [fType, setFType] = React.useState('all');
  const [fDomain, setFDomain] = React.useState('all');
  const [zoom, setZoom] = React.useState(1);

  // Fetch real backend data
  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/registry/capabilities`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (cancelled) return;
        const caps = data.capabilities || data || [];
        const mapped = mapBackend(caps);
        setItems(mapped);
        if (mapped.length > 0) setSelected(mapped[0].id);
        setLoading(false);
      })
      .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    return () => { cancelled = true; };
  }, []);

  const getName = (x: CapItem) => ar ? (x.name_ar || x.name_en) : x.name_en;
  const getDesc = (x: CapItem) => ar ? (x.description_ar || x.description_en) : x.description_en;
  const isActive = (x: CapItem) => x.status === 'active' || x.status === 'available';

  const allTypes = React.useMemo(() => [...new Set(items.map(x => x.type))], [items]);
  const allDomains = React.useMemo(() => [...new Set(items.map(x => ar ? (x.domain_ar || x.domain_en) : x.domain_en))], [items, ar]);

  const matches = React.useMemo(() => items.filter(x => {
    const s = (getName(x) + ' ' + getDesc(x)).toLowerCase().includes(q.toLowerCase());
    const ty = fType === 'all' || x.type === fType;
    const st = fStatus === 'all' || (fStatus === 'active' ? isActive(x) : fStatus === 'off' ? (!isActive(x) && x.status !== 'beta') : x.status === fStatus);
    const d = fDomain === 'all' || (ar ? (x.domain_ar || x.domain_en) : x.domain_en) === fDomain;
    return s && ty && st && d;
  }), [items, q, fType, fStatus, fDomain, ar]);

  const sel = items.find(c => c.id === selected) || items[0];
  const features = ar ? (sel?.features_ar || sel?.features_en || []) : (sel?.features_en || []);
  const rels = sel?.relationships || [];
  const pos = [[200,64],[317,135],[330,260],[284,376],[119,361],[64,255],[91,131]];
  const tabs = [['functions','Key Functions','الوظائف الرئيسية'],['io','Inputs & Outputs','المدخلات والمخرجات'],['config','Configuration','الإعدادات'],['docs','Documentation','التوثيق']];

  if (loading) return <div style={{padding:60,textAlign:'center',color:'#6680aa'}}>{t('Loading capabilities...','جارٍ تحميل القدرات...')}</div>;
  if (error) return <div style={{padding:60,textAlign:'center',color:'#a52d32'}}>{t('Error: ','خطأ: ')}{error}</div>;
  if (!items.length) return <div style={{padding:60,textAlign:'center',color:'#6680aa'}}>{t('No capabilities registered.','لا توجد قدرات مسجلة.')}</div>;

  const statusHtml = (x: CapItem) => (
    <span className={`status ${x.status === 'beta' ? 'beta' : !isActive(x) ? 'off' : ''}`}>
      {x.status === 'beta' ? t('Beta','تجريبية') : isActive(x) ? t('Active','متاحة') : t('Unavailable','غير متاحة')}
    </span>
  );

  return (
    <div className="manara-registry-v2">
      <main className="workspace">
        <div className="three">
          {/* === List card === */}
          <section className="card list-card">
            <div className="list-head">
              <div>
                <h1>{t('Capability Registry','سجل القدرات')}</h1>
                <p className="subheading">{t('Browse and explore available capabilities','تصفح القدرات المتاحة في النظام')}</p>
              </div>
              <button className="new-btn" disabled title={t('Requires an application route','يتطلب وظيفة في التطبيق')}>
                {t('+ New Capability','+ قدرة جديدة')}
              </button>
            </div>
            <label className="findbox">
              <span>⌕</span>
              <input value={q} onChange={e => setQ(e.target.value)} placeholder={t('Search capabilities...','البحث في القدرات...')} aria-label={t('Search capabilities','البحث في القدرات')} />
            </label>
            <div className="filters">
              <select value={fDomain} onChange={e => setFDomain(e.target.value)} aria-label={t('Domain','المجال')}>
                <option value="all">{t('All domains','جميع المجالات')}</option>
                {allDomains.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <select value={fStatus} onChange={e => setFStatus(e.target.value)} aria-label={t('Status','الحالة')}>
                <option value="all">{t('All statuses','جميع الحالات')}</option>
                <option value="active">{t('Active','متاحة')}</option>
                <option value="beta">{t('Beta','تجريبية')}</option>
                <option value="off">{t('Unavailable','غير متاحة')}</option>
              </select>
              <select value={fType} onChange={e => setFType(e.target.value)} aria-label={t('Type','النوع')}>
                <option value="all">{t('All types','جميع الأنواع')}</option>
                {allTypes.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
              <button className="filter-symbol" onClick={() => { setQ(''); setFStatus('all'); setFType('all'); setFDomain('all'); }} aria-label={t('Reset filters','إعادة تعيين المرشحات')}>▽</button>
            </div>
            <div className="list-count">{t(`${matches.length} capabilities`,`${matches.length} قدرة`)}</div>
            <div className="cap-list">
              {matches.length ? matches.map(x => (
                <button key={x.id} className={`cap-item ${x.id === selected ? 'active' : ''}`} onClick={() => { setSelected(x.id); setTab('functions'); }} aria-pressed={x.id === selected}>
                  <span className="cap-icon">{x.icon || '▤'}</span>
                  <span className="cap-copy"><span className="cap-name">{getName(x)}</span><span className="cap-desc">{getDesc(x)}</span></span>
                  {statusHtml(x)}
                </button>
              )) : <p className="empty">{t('No capabilities match the current filters.','لا توجد قدرات مطابقة للمرشحات الحالية.')}</p>}
            </div>
          </section>

          {/* === Detail card === */}
          <section className="card detail-card">
            {sel ? (
              <>
                <div className="detail-top">
                  <div>
                    <h2>{getName(sel)}</h2>
                    <div className="chips">
                      {statusHtml(sel)}
                      <span className="chip">{ar ? (sel.type_ar || sel.type) : sel.type}</span>
                      <span className="chip id" dir="ltr">{sel.id}</span>
                    </div>
                  </div>
                  <span className="cap-icon">{sel.icon || '▤'}</span>
                </div>
                <section className="detail-section">
                  <h3 className="section-title">{t('Description','الوصف')}</h3>
                  <p className="section-text">{getDesc(sel)}</p>
                </section>
                <div className="facts">
                  <div className="fact"><small>{t('Version','الإصدار')}</small><b dir="ltr">{sel.version || '—'}</b></div>
                  <div className="fact"><small>{t('Type','النوع')}</small><b>{ar ? (sel.type_ar || sel.type) : sel.type}</b></div>
                  <div className="fact"><small>{t('Domain','المجال')}</small><b>{ar ? (sel.domain_ar || sel.domain_en) : sel.domain_en}</b></div>
                  <div className="fact"><small>{t('Last Updated','آخر تحديث')}</small><b dir="ltr">{sel.updated || '—'}</b></div>
                </div>
                <div className="tabs">
                  {tabs.map(([k, en, arabic]) => (
                    <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{t(en, arabic)}</button>
                  ))}
                </div>
                <div className="detail-body">
                  {tab === 'functions' ? (
                    <div className="checklist">
                      {features.length ? features.map((s, i) => (
                        <div key={i} className="checkline"><span className="check">✓</span><span>{s}</span></div>
                      )) : <div className="empty">{t('No function details supplied.','لا تتوفر معلومات الوظائف.')}</div>}
                    </div>
                  ) : tab === 'io' ? (
                    <p className="empty">{t('Input and output contracts are not supplied.','لا تتوفر بيانات المدخلات والمخرجات.')}</p>
                  ) : tab === 'config' ? (
                    <p className="empty">{t('Configuration is managed by the application.','تدار الإعدادات من خلال التطبيق.')}</p>
                  ) : (
                    <p className="empty">{t('Documentation appears here when available.','يظهر التوثيق هنا عند توفره.')}</p>
                  )}
                </div>
              </>
            ) : <p className="empty">{t('Select a capability','اختر قدرة')}</p>}
          </section>

          {/* === Graph card === */}
          <section className="card graph-card">
            <div className="graph-head">
              <span>{t('Capability Ecosystem','الرسم التوضيحي للقدرات')}</span>
              <span className="hint" aria-hidden="true">ⓘ</span>
            </div>
            <div className="graph-stage">
              <svg viewBox="0 0 400 460" role="img" aria-label={t('Capability relationship visualization','رسم علاقات القدرات')}>
                <g transform={`translate(200 233) scale(${zoom}) translate(-200 -233)`}>
                  {rels.slice(0, 7).map((e, i) => {
                    const [xx, yy] = pos[i % pos.length];
                    const col = e.color || '#318ed8';
                    return (
                      <g key={i}>
                        <path className="edge" d={`M 200 232 Q ${(xx+200)/2+((i%2)?-20:20)} ${(yy+232)/2} ${xx} ${yy}`} stroke={col} />
                        <circle cx={xx} cy={yy} r={30} fill={col} opacity={0.10} />
                        <circle cx={xx} cy={yy} r={26} fill={col} opacity={0.12} />
                        <g className="graph-node" role="button" tabIndex={0} aria-label={e.name_en}>
                          <circle cx={xx} cy={yy} r={24} fill="transparent" stroke={col} strokeWidth={1} opacity={0.36} />
                          <text x={xx} y={yy+7} textAnchor="middle" fontSize={23} fill={col}>{e.symbol || '◈'}</text>
                        </g>
                        <text x={xx} y={yy+43} textAnchor="middle">{ar ? (e.name_ar || e.name_en) : e.name_en}</text>
                      </g>
                    );
                  })}
                  <circle cx={200} cy={233} r={47} fill="#d9ecff" stroke="#a0c5ff" strokeWidth={2} />
                  <circle cx={200} cy={233} r={35} fill="#126af3" />
                  <text x={200} y={245} textAnchor="middle" style={{fontSize:'34px',fill:'white'}}>{sel?.icon || '▤'}</text>
                  <text x={200} y={300} textAnchor="middle" style={{fontSize:'12px',fontWeight:800}}>{sel ? getName(sel) : ''}</text>
                </g>
              </svg>
            </div>
            <div className="graph-ctrl">
              <button onClick={() => setZoom(1)}>{t('Fit to View','إعادة الضبط')} ⌂</button>
              <div className="zoom">
                <button onClick={() => setZoom(z => Math.max(0.6, z - 0.15))} aria-label={t('Zoom out','تصغير')}>−</button>
                <button>{Math.round(zoom * 100)}%</button>
                <button onClick={() => setZoom(z => Math.min(1.7, z + 0.15))} aria-label={t('Zoom in','تكبير')}>+</button>
              </div>
              <button aria-label={t('Full screen graph','تكبير الرسم')}>⛶</button>
            </div>
          </section>
        </div>

        {/* === Bottom panels === */}
        <div className="bottom">
          {(() => {
            const versions = sel?.versions?.length ? sel.versions : (sel?.version ? [{name: sel.version, sub: sel.updated, tag: t('Current','الحالي')}] : []);
            const tests = sel?.tests || [];
            const integrations = sel?.integrations || [];
            const related = (sel?.relationships || []).slice(0, 4).map(r => ({ name: ar ? (r.name_ar || r.name_en) : r.name_en, icon: r.symbol }));
            const panels = [
              { title: t('Versions','الإصدارات'), entries: versions },
              { title: t('Validation & Tests','الاختبارات'), entries: tests },
              { title: t('Integrations & Dependencies','الاعتماديات'), entries: integrations },
              { title: t('Related Capabilities','قدرات ذات صلة'), entries: related },
            ];
            return panels.map((p, pi) => (
              <section key={pi} className="card mini-panel">
                <div className="mini-head"><span>{p.title}</span><a href="#" onClick={e => e.preventDefault()}>{t('View All','عرض الكل')}</a></div>
                {p.entries.length ? p.entries.map((e, i) => (
                  <div key={i} className="mini-entry">
                    <span className="small-icon">{(e as {icon?: string}).icon || ['▤','⚙','☷','▥'][i % 4]}</span>
                    <span style={{flex:1}}><strong>{(e as {name?: string}).name || String(e)}</strong>{(e as {sub?: string}).sub ? <small>{(e as {sub?: string}).sub}</small> : null}</span>
                    {(e as {tag?: string}).tag ? <span className="status">{(e as {tag?: string}).tag}</span> : null}
                  </div>
                )) : <p className="empty">{t('No records available.','لا توجد سجلات متاحة.')}</p>}
              </section>
            ));
          })()}
        </div>
      </main>
    </div>
  );
}
