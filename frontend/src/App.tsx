import * as React from 'react';
import { LanguageProvider, useLanguage } from './components/manara/i18n';
import { Sidebar } from './components/manara/Sidebar';
import { Header } from './components/manara/Header';
import { Hero } from './components/manara/Hero';
import { ComposeResultCard } from './components/manara/ComposeResult';
import { InvestigationWorkspace } from './components/manara/InvestigationWorkspace';
import { MemoryExplorer } from './components/manara/MemoryExplorer';
import { manaraApi, ManaraApiError, type ComposeResponse } from './components/manara/api-client';

type Page = 'home' | 'workspace' | 'memory';

function ManaraShell() {
  const { t } = useLanguage();
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [status, setStatus] = React.useState<'online' | 'offline' | 'checking'>('checking');
  const [query, setQuery] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<ComposeResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [page, setPage] = React.useState<Page>('home');
  const [investigationId, setInvestigationId] = React.useState<string | null>(null);
  const resultRef = React.useRef<HTMLDivElement | null>(null);

  const trimmed = query.trim();
  const isValid = trimmed.length >= 10;
  const overLimit = query.length > 1000;

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await manaraApi.status();
        if (!cancelled) setStatus(s._source === 'live' ? 'online' : 'offline');
      } catch { if (!cancelled) setStatus('offline'); }
    })();
    return () => { cancelled = true; };
  }, []);

  React.useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileOpen]);

  React.useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [result]);

  const handleSubmit = async () => {
    if (!isValid || submitting || overLimit) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await manaraApi.compose(trimmed);
      setResult(r);
      setInvestigationId(r.investigation_id);
    } catch (e) {
      let msg = 'Failed to compose investigation';
      if (e instanceof ManaraApiError) {
        const det = e.detail as { detail?: { message?: string } } | undefined;
        msg = det?.detail?.message ?? e.message;
      } else if (e instanceof Error) {
        msg = e.message;
      }
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    setResult(null);
    setError(null);
  };

  const handleNavigate = (target: Page) => {
    setPage(target);
    setMobileOpen(false);
  };

  const headerTitle = page === 'home' ? t('nav.home') :
    page === 'workspace' ? t('nav.workspace') : t('nav.memory');

  return (
    <div className="flex min-h-screen bg-[var(--manara-canvas)]">
      <Sidebar
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed(c => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        activePage={page}
        onNavigate={handleNavigate}
        workspaceEnabled={!!investigationId}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onOpenMobileNav={() => setMobileOpen(true)}
          status={status}
          title={headerTitle}
          subtitle={t('app.tagline')}
        />

        <main id="main-content" className="flex-1 manara-scroll overflow-y-auto">
            {page === 'home' && (
              <>
                {/* MANARA-UI-PAGE01-SOURCE-INTEGRATION-01: Hero renders full-width
                    per the HTML/CSS source reference (no max-w container wrapping it) */}
                <Hero
                  query={query}
                  onQueryChange={setQuery}
                  onSubmit={handleSubmit}
                  onClear={handleClear}
                  onExample={(text) => { setQuery(text); setResult(null); setError(null); }}
                  submitting={submitting}
                  isValid={isValid}
                  overLimit={overLimit}
                />
                <div className="mx-auto w-full max-w-6xl px-4 md:px-8 pb-8">
                <ComposeResultCard
                  ref={resultRef}
                  submitting={submitting}
                  result={result}
                  error={error}
                  onRetry={() => { setError(null); handleSubmit(); }}
                  onClear={handleClear}
                />
                {result && investigationId && (
                  <div className="mt-4 text-center">
                    <button
                      onClick={() => handleNavigate('workspace')}
                      className="px-6 py-2.5 rounded-lg bg-[var(--manara-teal)] text-white text-[13px] font-medium"
                    >
                      Open Investigation Workspace →
                    </button>
                  </div>
                )}
                </div>
              </>
            )}

            {page === 'workspace' && investigationId && (
              <div className="mx-auto w-full max-w-6xl px-4 py-8 md:px-8 md:py-12">
                <InvestigationWorkspace investigationId={investigationId} />
              </div>
            )}

            {page === 'memory' && investigationId && (
              <div className="mx-auto w-full max-w-6xl px-4 py-8 md:px-8 md:py-12">
                <MemoryExplorer investigationId={investigationId} />
              </div>
            )}

            {page !== 'home' && !investigationId && (
              <div className="mx-auto w-full max-w-6xl px-4 py-8 md:px-8 md:py-12 text-center py-20">
                <p className="text-[var(--manara-ink-muted)]">
                  Submit a research question on the Home page first to start an investigation.
                </p>
                <button
                  onClick={() => handleNavigate('home')}
                  className="mt-4 px-4 py-2 rounded-lg bg-[var(--manara-teal)] text-white text-[13px]"
                >
                  Go to Home
                </button>
              </div>
            )}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <LanguageProvider>
      <ManaraShell />
    </LanguageProvider>
  );
}
