'use client';

import * as React from 'react';
import { Search, Sparkles, ArrowRight, Eraser, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';
import { LighthouseHeroIllustration } from './Lighthouse';
import { Pill } from './Badges';

/* ============================================================
   Hero — headline, subheadline, decorative lighthouse,
   research question composer, 3-step workflow, examples
   ============================================================ */

interface HeroProps {
  query: string;
  onQueryChange: (v: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  onExample: (text: string) => void;
  submitting: boolean;
  isValid: boolean;
  overLimit: boolean;
}

const STEPS = [
  { key: 'step1', icon: Search },
  { key: 'step2', icon: Sparkles },
  { key: 'step3', icon: ArrowRight },
] as const;

const EXAMPLES = [
  'home.examples.1',
  'home.examples.2',
  'home.examples.3',
] as const;

export function Hero({
  query,
  onQueryChange,
  onSubmit,
  onClear,
  onExample,
  submitting,
  isValid,
  overLimit,
}: HeroProps) {
  const { t, dir } = useLanguage();
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);

  // Keyboard shortcut: Cmd/Ctrl+Enter to submit
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      onSubmit();
    }
  };

  const charCount = query.length;

  return (
    <section aria-labelledby="home-headline" className="relative">
      {/* ── Hero top: headline + illustration ────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8 lg:gap-12 items-start">
        {/* Left: copy + composer */}
        <div className="flex flex-col">
          {/* Eyebrow */}
          <div className="mb-4 flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block h-px w-8"
              style={{ background: 'var(--manara-brass)' }}
            />
            <span className="font-ui text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--manara-brass)]">
              {t('app.name')} · {t('app.tagline')}
            </span>
          </div>

          {/* Headline */}
          <h1
            id="home-headline"
            className="font-serif text-[34px] leading-[1.12] sm:text-[42px] md:text-[52px] md:leading-[1.08] font-semibold text-[var(--manara-ink)] tracking-[-0.015em]"
          >
            {t('home.headline.prefix')}{' '}
            <span className="relative inline-block">
              <span className="text-[var(--manara-teal)]">{t('home.headline.accent')}</span>
              <span
                aria-hidden
                className="absolute -bottom-1 inset-x-0 h-[3px] rounded-full"
                style={{
                  background: 'linear-gradient(90deg, var(--manara-teal) 0%, transparent 90%)',
                  opacity: 0.5,
                }}
              />
            </span>{' '}
            {t('home.headline.suffix')}
          </h1>

          <p className="mt-5 max-w-[640px] font-ui text-[15px] md:text-[16px] leading-[1.7] text-[var(--manara-ink-light)]">
            {t('home.subheadline')}
          </p>

          {/* Composer */}
          <div className="mt-7">
            <ComposerCard
              ref={textareaRef}
              query={query}
              onQueryChange={onQueryChange}
              onSubmit={onSubmit}
              onClear={onClear}
              onKeyDown={onKeyDown}
              submitting={submitting}
              isValid={isValid}
              overLimit={overLimit}
              charCount={charCount}
            />

            {/* Examples */}
            <div className="mt-5">
              <div className="mb-2 font-ui text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--manara-ink-muted)]">
                {t('home.examples.label')}
              </div>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => onExample(t(k))}
                    className={cn(
                      'group inline-flex max-w-full items-center gap-2 rounded-md border border-[var(--manara-mist)] bg-[var(--manara-white)] px-3 py-1.5',
                      'text-start font-ui text-[12px] leading-snug text-[var(--manara-ink-light)] manara-shadow-soft',
                      'hover:border-[var(--manara-teal)] hover:text-[var(--manara-ink)] transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
                    )}
                  >
                    <span className="line-clamp-1">{t(k)}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right: lighthouse illustration */}
        <div className="relative order-first lg:order-last">
          <div className="relative mx-auto aspect-square w-full max-w-[360px] lg:max-w-none">
            <div
              aria-hidden
              className="absolute inset-0 rounded-[16px]"
              style={{
                background:
                  'radial-gradient(circle at 60% 35%, rgba(242, 200, 121, 0.16) 0%, transparent 55%), linear-gradient(160deg, #F7F8F6 0%, #E8EFF1 100%)',
                border: '1px solid var(--manara-mist)',
              }}
            />
            <LighthouseHeroIllustration
              className="relative size-full"
              aria-hidden
            />
            <div className="absolute bottom-3 inset-x-3 flex justify-center">
              <Pill variant="brass" className="backdrop-blur-sm whitespace-nowrap overflow-hidden text-ellipsis max-w-full">
                <span className="size-1.5 rounded-full bg-[var(--manara-brass)] shrink-0" />
                <span className="truncate">{t('app.name')} · {dir === 'rtl' ? 'منارة' : 'Guiding light for research'}</span>
              </Pill>
            </div>
          </div>
        </div>
      </div>

      {/* ── Workflow ─────────────────────────────────────────── */}
      <div className="mt-14 md:mt-20">
        <div className="mb-6 flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block h-px w-8"
            style={{ background: 'var(--manara-teal)' }}
          />
          <span className="font-ui text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--manara-teal)]">
            {dir === 'rtl' ? 'كيف يعمل' : 'How it works'}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div
                key={step.key}
                className={cn(
                  'relative flex flex-col gap-3 rounded-[10px] border border-[var(--manara-mist)] bg-[var(--manara-white)] p-5 manara-shadow-soft',
                )}
              >
                <div className="flex items-center justify-between">
                  <div
                    className="flex size-9 items-center justify-center rounded-md"
                    style={{
                      background: 'rgba(44, 115, 128, 0.10)',
                      color: 'var(--manara-teal)',
                    }}
                  >
                    <Icon className="size-[18px]" />
                  </div>
                  <span className="font-serif text-[28px] font-semibold leading-none text-[var(--manara-mist)]">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                </div>
                <div>
                  <h3 className="font-serif text-[16px] font-semibold text-[var(--manara-ink)]">
                    {t(`home.${step.key}.title`)}
                  </h3>
                  <p className="mt-1 font-ui text-[13px] leading-[1.6] text-[var(--manara-ink-light)]">
                    {t(`home.${step.key}.desc`)}
                  </p>
                </div>
                {idx < STEPS.length - 1 && (
                  <span
                    aria-hidden
                    className="hidden md:block absolute top-1/2 -translate-y-1/2 size-3"
                    style={
                      dir === 'rtl'
                        ? { left: -10, background: 'var(--manara-mist)', borderRadius: 9999 }
                        : { right: -10, background: 'var(--manara-mist)', borderRadius: 9999 }
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ============================================================
   Composer card — textarea + char counter + actions
   ============================================================ */

const ComposerCard = React.forwardRef<
  HTMLTextAreaElement,
  {
    query: string;
    onQueryChange: (v: string) => void;
    onSubmit: () => void;
    onClear: () => void;
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    submitting: boolean;
    isValid: boolean;
    overLimit: boolean;
    charCount: number;
  }
>(function ComposerCard(
  { query, onQueryChange, onSubmit, onClear, onKeyDown, submitting, isValid, overLimit, charCount },
  ref,
) {
  const { t, dir } = useLanguage();
  const remaining = 1000 - charCount;
  const counterColor = overLimit
    ? 'var(--coverage-none)'
    : remaining < 100
      ? 'var(--coverage-operational)'
      : 'var(--manara-ink-muted)';

  return (
    <div
      className={cn(
        'rounded-[10px] border bg-[var(--manara-white)] p-4 md:p-5 manara-shadow-soft-lg',
        overLimit ? 'border-[var(--coverage-none)]/40' : 'border-[var(--manara-mist)]',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <label
          htmlFor="manara-query"
          className="font-ui text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--manara-ink)]"
        >
          {t('home.composerLabel')}
        </label>
        <span
          className="font-mono text-[11px] tabular-nums"
          style={{ color: counterColor }}
          aria-live="polite"
        >
          {charCount} / 1000
        </span>
      </div>

      <p className="mt-1 font-ui text-[12px] leading-[1.55] text-[var(--manara-ink-muted)]">
        {t('home.composerHint')}
      </p>

      <div className="relative mt-3">
        <textarea
          id="manara-query"
          ref={ref}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={t('home.placeholder')}
          maxLength={1200}
          rows={5}
          aria-label={t('home.composerLabel')}
          aria-describedby="manara-query-help manara-query-counter"
          aria-invalid={overLimit || (query.length > 0 && !isValid)}
          className={cn(
            'w-full resize-y rounded-md border bg-[var(--manara-canvas)] px-3.5 py-3 font-ui text-[14px] leading-[1.6]',
            'text-[var(--manara-ink)] placeholder:text-[var(--manara-ink-muted)]/70',
            'transition-colors',
            'focus:outline-none focus:border-[var(--manara-teal)] focus:ring-2 focus:ring-[var(--manara-teal)]/25',
            overLimit
              ? 'border-[var(--coverage-none)]/60'
              : 'border-[var(--manara-mist)]',
          )}
        />
      </div>

      <div
        id="manara-query-help"
        className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1"
      >
        <span className="font-ui text-[11px] text-[var(--manara-ink-muted)]">
          {dir === 'rtl' ? '⌘/Ctrl + Enter للإرسال' : '⌘/Ctrl + Enter to submit'}
        </span>
        {query.length > 0 && !isValid && !overLimit && (
          <span className="inline-flex items-center gap-1 font-ui text-[11px] text-[var(--coverage-operational)]">
            <AlertTriangle className="size-3" />
            {dir === 'rtl' ? `بحاجة إلى ${10 - query.trim().length} أحرف إضافية` : `${10 - query.trim().length} more characters needed`}
          </span>
        )}
        {overLimit && (
          <span className="inline-flex items-center gap-1 font-ui text-[11px] text-[var(--coverage-none)]">
            <AlertTriangle className="size-3" />
            {dir === 'rtl' ? 'تجاوز الحد الأقصى' : 'Over the 1000-character limit'}
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onClick={onSubmit}
          disabled={!isValid || submitting || overLimit}
          aria-busy={submitting}
          className={cn(
            'inline-flex h-11 items-center gap-2 rounded-md px-5 font-ui text-[13.5px] font-semibold',
            'transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)] focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50',
            !isValid || submitting || overLimit
              ? 'bg-[var(--manara-mist)] text-[var(--manara-ink-muted)]'
              : 'bg-[var(--manara-teal)] text-[var(--manara-white)] hover:bg-[var(--manara-teal-dark)] manara-shadow-soft',
          )}
        >
          {submitting ? (
            <>
              <Spinner />
              <span>{t('home.composing')}</span>
            </>
          ) : (
            <>
              <Sparkles className="size-4" />
              <span>{t('home.submit')}</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onClear}
          disabled={submitting || query.length === 0}
          className={cn(
            'inline-flex h-11 items-center gap-2 rounded-md border border-[var(--manara-mist)] bg-[var(--manara-white)] px-4',
            'font-ui text-[13px] font-medium text-[var(--manara-ink-light)]',
            'hover:border-[var(--manara-ink-muted)] hover:text-[var(--manara-ink)] transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
            'disabled:cursor-not-allowed disabled:opacity-40',
          )}
        >
          <Eraser className="size-3.5" />
          <span>{t('home.clear')}</span>
        </button>

        <div className="ml-auto hidden sm:flex items-center">
          <span id="manara-query-counter" className="sr-only">
            {charCount} of 1000 characters
          </span>
        </div>
      </div>
    </div>
  );
});

/* Need to import result symbol for the disabled state above */
// (ComposerCard is intentionally a controlled component — no result state here.)

/* ============================================================
   Spinner — small, calm
   ============================================================ */
function Spinner() {
  return (
    <svg
      className="size-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
