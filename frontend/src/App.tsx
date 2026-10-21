import * as React from 'react';
import { LanguageProvider, useLanguage } from './components/manara/i18n';
import { Sidebar } from './components/manara/Sidebar';
import { Header } from './components/manara/Header';
import { Hero } from './components/manara/Hero';
import {
  ComposeResultCard,
} from './components/manara/ComposeResult';
import {
  manaraApi,
  ManaraApiError,
  type ComposeResponse,
} from './components/manara/api-client';

/* ============================================================
   MANARA — Investigation Home

   Page-level state:
   - service status (online / offline / checking)
   - composer value (string) + validity
   - submitting flag
   - compose result (success) | error | null
   - sidebar collapsed (desktop/tablet) + mobile drawer open
   ============================================================ */

function ManaraShell() {
  const { t, dir } = useLanguage();

  // Sidebar + drawer
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);

  // Status
  const [status, setStatus] = React.useState<'online' | 'offline' | 'checking'>('checking');

  // Composer
  const [query, setQuery] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<ComposeResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const resultRef = React.useRef<HTMLDivElement | null>(null);

  const trimmed = query.trim();
  const isValid = trimmed.length >= 10;
  const overLimit = query.length > 1000;

  // Fetch status on mount
  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await manaraApi.status();
        if (!cancelled) setStatus(s._source === 'live' ? 'online' : 'offline');
      } catch {
        if (!cancelled) setStatus('offline');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Close mobile drawer on Escape
  React.useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileOpen]);

  // Scroll to result when it appears
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
    } catch (e) {
      let msg = t('error.compose');
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

  const handleRetry = () => {
    setError(null);
    handleSubmit();
  };

  const handleExample = (text: string) => {
    setQuery(text);
    setResult(null);
    setError(null);
  };

  return (
    <div
      className="flex min-h-screen bg-[var(--manara-canvas)]"
      style={{ direction: dir }}
    >
      <Sidebar
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Header
          onOpenMobileNav={() => setMobileOpen(true)}
          status={status}
          title={t('nav.home')}
          subtitle={t('app.tagline')}
        />

        <main
          id="main-content"
          className="flex-1 manara-scroll overflow-y-auto"
        >
          <div className="mx-auto w-full max-w-6xl px-4 py-8 md:px-8 md:py-12">
            <Hero
              query={query}
              onQueryChange={setQuery}
              onSubmit={handleSubmit}
              onClear={handleClear}
              onExample={handleExample}
              submitting={submitting}
              isValid={isValid}
              overLimit={overLimit}
            />

            <ComposeResultCard
              ref={resultRef}
              submitting={submitting}
              result={result}
              error={error}
              onRetry={handleRetry}
              onClear={handleClear}
            />
          </div>
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
