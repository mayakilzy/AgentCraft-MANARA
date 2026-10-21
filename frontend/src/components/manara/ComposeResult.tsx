
import * as React from 'react';
import {
  AlertTriangle,
  AlertCircle,
  RotateCw,
  Sparkles,
  CheckCircle2,
  Circle,
  Lock,
  Info,
  CornerDownRight,
  Beaker,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';
import {
  CoverageBadge,
  Pill,
} from './Badges';
import type {
  ComposeResponse,
  CoverageEntry,
  GapEntry,
  DetectedNeed,
} from './api-client';

/* ============================================================
   ComposeResultCard — the four states:
   - idle (no result, no error)
   - submitting (loading)
   - error
   - success (the full composition display)
   ============================================================ */

interface ComposeResultCardProps {
  submitting: boolean;
  result: ComposeResponse | null;
  error: string | null;
  onRetry: () => void;
  onClear: () => void;
}

export const ComposeResultCard = React.forwardRef<
  HTMLDivElement,
  ComposeResultCardProps
>(function ComposeResultCard(
  { submitting, result, error, onRetry, onClear },
  ref,
) {
  const { t } = useLanguage();

  if (submitting) {
    return <LoadingState ref={ref} />;
  }
  if (error) {
    return (
      <ErrorState ref={ref} message={error} onRetry={onRetry} />
    );
  }
  if (!result) {
    return <IdleState ref={ref} />;
  }
  return (
    <SuccessState
      ref={ref}
      result={result}
      onClear={onClear}
    />
  );
});

/* ------------------------------------------------------------
   Idle state
   ------------------------------------------------------------ */
const IdleState = React.forwardRef<HTMLDivElement, object>(
  function IdleState(_, ref) {
    const { t, dir } = useLanguage();
    return (
      <section
        ref={ref}
        aria-label={dir === 'rtl' ? 'حالة الخمول' : 'Idle state'}
        className="mt-10 md:mt-14"
      >
        <div
          className="flex flex-col items-center justify-center rounded-[12px] border border-dashed border-[var(--manara-mist)] bg-[var(--manara-white)]/40 px-6 py-12 text-center"
        >
          <div
            aria-hidden
            className="flex size-12 items-center justify-center rounded-full"
            style={{ background: 'var(--manara-mist)', color: 'var(--manara-ink-muted)' }}
          >
            <Sparkles className="size-5" />
          </div>
          <p className="mt-4 font-serif text-[16px] text-[var(--manara-ink-light)]">
            {dir === 'rtl'
              ? 'اكتب سؤالاً للبدء — سيظهر تقرير تركيب القالب هنا.'
              : 'Type a question to begin — the mold composition report will appear here.'}
          </p>
        </div>
      </section>
    );
  },
);

/* ------------------------------------------------------------
   Loading state
   ------------------------------------------------------------ */
const LoadingState = React.forwardRef<HTMLDivElement, object>(
  function LoadingState(_, ref) {
    const { t, dir } = useLanguage();
    return (
      <section
        ref={ref}
        aria-busy="true"
        aria-live="polite"
        aria-label={t('home.composing')}
        className="mt-10 md:mt-14"
      >
        <div className="rounded-[12px] border border-[var(--manara-mist)] bg-[var(--manara-white)] p-6 md:p-8 manara-shadow-soft-lg">
          <div className="flex items-center gap-4">
            <div
              aria-hidden
              className="relative flex size-12 items-center justify-center rounded-full"
              style={{ background: 'rgba(44, 115, 128, 0.10)' }}
            >
              <BigSpinner />
            </div>
            <div className="flex-1">
              <h3 className="font-serif text-[18px] font-semibold text-[var(--manara-ink)]">
                {t('home.composing')}
              </h3>
              <p className="mt-1 font-ui text-[12.5px] text-[var(--manara-ink-muted)]">
                {t('home.composing.sub')}
              </p>
            </div>
          </div>

          {/* Skeleton lines */}
          <div className="mt-6 space-y-3">
            <SkeletonRow />
            <SkeletonRow width="78%" />
            <SkeletonRow width="62%" />
          </div>

          {/* Skeleton badge row */}
          <div className="mt-5 flex flex-wrap gap-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="manara-shimmer h-6 w-24 rounded-md"
                aria-hidden
              />
            ))}
          </div>
        </div>
      </section>
    );
  },
);

/* ------------------------------------------------------------
   Error state
   ------------------------------------------------------------ */
const ErrorState = React.forwardRef<
  HTMLDivElement,
  { message: string; onRetry: () => void }
>(function ErrorState({ message, onRetry }, ref) {
  const { t } = useLanguage();
  return (
    <section
      ref={ref}
      aria-label={t('error.title')}
      className="mt-10 md:mt-14"
    >
      <div
        role="alert"
        className="rounded-[12px] border p-6 md:p-8"
        style={{
          background: 'var(--coverage-none-bg)',
          borderColor: 'rgba(196, 69, 69, 0.35)',
        }}
      >
        <div className="flex items-start gap-4">
          <div
            aria-hidden
            className="flex size-10 shrink-0 items-center justify-center rounded-full"
            style={{ background: 'rgba(196, 69, 69, 0.15)', color: 'var(--coverage-none)' }}
          >
            <AlertCircle className="size-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-serif text-[18px] font-semibold text-[var(--manara-ink)]">
              {t('error.title')}
            </h3>
            <p className="mt-1 font-ui text-[13px] text-[var(--manara-ink-light)]">
              {t('error.compose')}
            </p>
            <pre
              className="mt-3 max-h-32 overflow-auto manara-scroll rounded-md border border-[var(--coverage-none)]/25 bg-[var(--manara-white)] p-3 font-mono text-[11.5px] leading-relaxed text-[var(--manara-ink)]"
            >
              {message}
            </pre>
            <div className="mt-4">
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex h-10 items-center gap-2 rounded-md border border-[var(--coverage-none)]/40 bg-[var(--manara-white)] px-4 font-ui text-[13px] font-medium text-[var(--manara-ink)] hover:border-[var(--coverage-none)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--coverage-none)]"
              >
                <RotateCw className="size-3.5" />
                {t('error.retry')}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
});

/* ------------------------------------------------------------
   Success state — the full composition display
   ------------------------------------------------------------ */
const SuccessState = React.forwardRef<
  HTMLDivElement,
  { result: ComposeResponse; onClear: () => void }
>(function SuccessState({ result, onClear }, ref) {
  const { t, lang, dir } = useLanguage();
  const isBlocker = result.deliverable_type === 'coverage_blocker_report';
  const isFixture = result._source === 'fixture';
  const isComplete = result.is_complete;

  return (
    <section
      ref={ref}
      aria-label={dir === 'rtl' ? 'نتيجة تركيب القالب' : 'Mold composition result'}
      className="mt-10 md:mt-14"
    >
      {/* Header strip */}
      <div
        className={cn(
          'rounded-t-[12px] border-x border-t px-6 py-5 md:px-8 md:py-6',
          isBlocker
            ? 'border-[rgba(196,69,69,0.25)]'
            : 'border-[var(--manara-mist)]',
        )}
        style={{
          background: isBlocker
            ? 'linear-gradient(180deg, rgba(196,69,69,0.06) 0%, rgba(196,69,69,0.02) 100%)'
            : 'linear-gradient(180deg, rgba(44,115,128,0.06) 0%, rgba(44,115,128,0.02) 100%)',
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              {isComplete ? (
                <Pill variant="success">
                  <CheckCircle2 className="size-3" />
                  {t('home.complete')}
                </Pill>
              ) : (
                <Pill variant="warning">
                  <AlertTriangle className="size-3" />
                  {t('home.partial')}
                </Pill>
              )}
              {result.is_unknown_domain && (
                <Pill variant="brass">
                  <Sparkles className="size-3" />
                  {t('home.newDomain')}
                </Pill>
              )}
              {isFixture && (
                <Pill variant="warning">
                  <Beaker className="size-3" />
                  {t('home.fixtureBadge')}
                </Pill>
              )}
              <span className="font-ui text-[11px] text-[var(--manara-ink-muted)]">
                {t('home.deliverableType')}:
              </span>
              <Pill variant={isBlocker ? 'error' : 'teal'}>
                {t(`home.deliverable.${result.deliverable_type}`)}
              </Pill>
            </div>
            <h2
              className="mt-3 font-serif text-[22px] md:text-[26px] font-semibold leading-tight text-[var(--manara-ink)]"
            >
              {isBlocker ? t('home.blocker.title') : (dir === 'rtl' ? 'تم تركيب قالب التحقيق' : 'Investigation mold composed')}
            </h2>
            <p className="mt-1.5 max-w-[700px] font-ui text-[13px] leading-[1.6] text-[var(--manara-ink-light)]">
              {isBlocker
                ? t('home.blocker.desc')
                : t('home.compositionNotes')}
            </p>
          </div>
        </div>
      </div>

      {/* Body */}
      <div
        className={cn(
          'rounded-b-[12px] border-x border-b bg-[var(--manara-white)] px-6 py-6 md:px-8 md:py-8 manara-shadow-soft-lg',
          isBlocker ? 'border-[rgba(196,69,69,0.25)]' : 'border-[var(--manara-mist)]',
        )}
      >
        {/* Top metadata grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-5">
          <MetaItem label={t('home.investigationId')}>
            <code className="font-mono text-[12.5px] text-[var(--manara-teal)]">
              {result.investigation_id}
            </code>
          </MetaItem>
          <MetaItem label={t('home.moldId')}>
            <code className="font-mono text-[12.5px] text-[var(--manara-teal)]">
              {result.mold_recipe_id}
            </code>
          </MetaItem>
          <MetaItem label={t('home.composedAt')}>
            <span className="font-mono text-[12px] text-[var(--manara-ink-light)]">
              {formatUtc(result.composed_at)}
            </span>
          </MetaItem>
          <MetaItem label={t('home.catalogComplete')}>
            {result.is_catalog_complete ? (
              <span className="inline-flex items-center gap-1.5 font-ui text-[12.5px] text-[var(--coverage-verified)]">
                <CheckCircle2 className="size-3.5" />
                {t('home.catalogComplete.yes')}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 font-ui text-[12.5px] text-[var(--coverage-none)]">
                <AlertCircle className="size-3.5" />
                {t('home.catalogComplete.no')}
              </span>
            )}
          </MetaItem>
        </div>

        {/* Detection reasoning */}
        {result.detection_reasoning && (
          <ReasoningBlock
            label={t('home.detectionReasoning')}
            text={result.detection_reasoning}
            variant={result.is_unknown_domain ? 'brass' : 'mist'}
          />
        )}

        {/* Detected Needs */}
        <Subsection
          title={t('home.detectedNeeds')}
          count={result.detected_needs.length}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {result.detected_needs.map((n: DetectedNeed) => (
              <NeedRow key={n.need} need={n} />
            ))}
          </div>
        </Subsection>

        {/* Coverage */}
        {result.coverage.length > 0 && (
          <Subsection
            title={t('home.coverage')}
            count={result.coverage.length}
          >
            <div className="overflow-hidden rounded-md border border-[var(--manara-mist)]">
              <table className="w-full text-start">
                <thead>
                  <tr
                    className="border-b border-[var(--manara-mist)] bg-[var(--manara-canvas)]/60"
                    style={{ direction: dir }}
                  >
                    <Th className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.10em] text-[var(--manara-ink-muted)]">
                      {t('home.need')}
                    </Th>
                    <Th className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.10em] text-[var(--manara-ink-muted)]">
                      {t('home.capability')}
                    </Th>
                    <Th className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.10em] text-[var(--manara-ink-muted)]">
                      {t('home.connectorIds')}
                    </Th>
                    <Th className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.10em] text-[var(--manara-ink-muted)] text-end">
                      {dir === 'rtl' ? 'المستوى' : 'Level'}
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {result.coverage.map((c: CoverageEntry) => (
                    <CoverageRow key={c.need} entry={c} />
                  ))}
                </tbody>
              </table>
            </div>
          </Subsection>
        )}

        {/* Gaps */}
        {result.gaps.length > 0 && (
          <Subsection
            title={t('home.gaps')}
            count={result.gaps.length}
            variant="error"
          >
            <div className="space-y-2.5">
              {result.gaps.map((g: GapEntry) => (
                <GapRow key={g.need} gap={g} />
              ))}
            </div>
          </Subsection>
        )}

        {/* Composition notes */}
        {result.composition_notes && !isBlocker && (
          <ReasoningBlock
            label={t('home.compositionNotes')}
            text={result.composition_notes}
            variant="mist"
          />
        )}

        {/* Workspace notice */}
        <div
          className="mt-6 flex items-start gap-3 rounded-md border border-[var(--manara-mist)] bg-[var(--manara-canvas)]/60 p-4"
        >
          <Info className="size-4 mt-0.5 shrink-0 text-[var(--manara-teal)]" aria-hidden />
          <div>
            <p className="font-ui text-[12.5px] leading-[1.6] text-[var(--manara-ink-light)]">
              {t('home.workspaceNotice')}
            </p>
          </div>
        </div>

        {/* Fixture notice */}
        {isFixture && (
          <div
            className="mt-3 flex items-start gap-3 rounded-md border p-4"
            style={{
              borderColor: 'rgba(217, 119, 6, 0.30)',
              background: 'var(--coverage-catalog-bg)',
            }}
          >
            <Beaker className="size-4 mt-0.5 shrink-0 text-[var(--coverage-catalog)]" aria-hidden />
            <p className="font-ui text-[12.5px] leading-[1.6] text-[var(--coverage-catalog)]">
              {t('home.fixtureHint')}
            </p>
          </div>
        )}

        {/* Footer actions */}
        <div className="mt-6 flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-[var(--manara-ink)] px-4 font-ui text-[13px] font-medium text-[var(--manara-canvas)] hover:bg-[var(--manara-ink)]/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]"
          >
            <Sparkles className="size-3.5" />
            {t('home.startNew')}
          </button>
          <div className="flex items-center gap-2">
            <Lock className="size-3.5 text-[var(--manara-ink-muted)]" />
            <span className="font-ui text-[11.5px] text-[var(--manara-ink-muted)]">
              {t('nav.workspace')} — {t('nav.comingLater')}
            </span>
          </div>
        </div>

        {/* sr-only status for screen readers */}
        <span className="sr-only" aria-live="polite">
          {isBlocker
            ? `${t('home.blocker')}: ${result.gaps.length} ${t('home.gaps').toLowerCase()}`
            : t('home.complete')}
        </span>
      </div>
    </section>
  );
});

/* ============================================================
   Small building blocks
   ============================================================ */

function MetaItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[var(--manara-ink-muted)]">
        {label}
      </div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function ReasoningBlock({
  label,
  text,
  variant = 'mist',
}: {
  label: string;
  text: string;
  variant?: 'mist' | 'brass';
}) {
  return (
    <div
      className={cn(
        'mt-5 rounded-md border p-4',
      )}
      style={
        variant === 'brass'
          ? {
              borderColor: 'rgba(187, 147, 98, 0.30)',
              background: 'rgba(187, 147, 98, 0.06)',
            }
          : {
              borderColor: 'var(--manara-mist)',
              background: 'var(--manara-canvas)',
            }
      }
    >
      <div className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[var(--manara-ink-muted)]">
        {label}
      </div>
      <p className="mt-1.5 font-ui text-[12.5px] leading-[1.65] text-[var(--manara-ink-light)]">
        {text}
      </p>
    </div>
  );
}

function Subsection({
  title,
  count,
  variant = 'default',
  children,
}: {
  title: string;
  count: number;
  variant?: 'default' | 'error';
  children: React.ReactNode;
}) {
  const { dir } = useLanguage();
  return (
    <div className="mt-7">
      <div className="mb-3 flex items-center gap-2">
        <h3
          className={cn(
            'font-serif text-[15px] font-semibold',
            variant === 'error' ? 'text-[var(--coverage-none)]' : 'text-[var(--manara-ink)]',
          )}
        >
          {title}
        </h3>
        <span
          className={cn(
            'inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 font-mono text-[11px] font-semibold',
            variant === 'error'
              ? 'bg-[var(--coverage-none-bg)] text-[var(--coverage-none)]'
              : 'bg-[var(--manara-mist)] text-[var(--manara-ink-light)]',
          )}
        >
          {count}
        </span>
        <span
          aria-hidden
          className="h-px flex-1"
          style={{ background: 'var(--manara-mist)' }}
        />
      </div>
      {children}
    </div>
  );
}

function NeedRow({ need }: { need: DetectedNeed }) {
  const { lang } = useLanguage();
  const label = lang === 'ar' ? need.label_ar : need.label_en;
  const pct = Math.round((need.relevance ?? 0) * 100);
  return (
    <div className="flex items-center gap-3 rounded-md border border-[var(--manara-mist)] bg-[var(--manara-canvas)]/40 px-3 py-2.5">
      <Circle
        aria-hidden
        className="size-3 shrink-0 text-[var(--manara-teal)]"
        fill="currentColor"
      />
      <div className="min-w-0 flex-1">
        <div className="font-ui text-[12.5px] font-medium text-[var(--manara-ink)] truncate">
          {label}
        </div>
        <div className="font-mono text-[10.5px] text-[var(--manara-ink-muted)] truncate">
          {need.need}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className="hidden sm:block w-16 h-1.5 rounded-full bg-[var(--manara-mist)] overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{
              width: `${pct}%`,
              background: 'var(--manara-teal)',
            }}
          />
        </div>
        <span className="font-mono text-[11px] text-[var(--manara-ink-light)] tabular-nums">
          {pct}%
        </span>
      </div>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn('px-3 py-2 text-start font-medium', className)}>{children}</th>;
}

function CoverageRow({ entry }: { entry: CoverageEntry }) {
  const { dir } = useLanguage();
  return (
    <tr
      className="border-b border-[var(--manara-mist)] last:border-b-0 hover:bg-[var(--manara-canvas)]/50"
      style={{ direction: dir }}
    >
      <td className="px-3 py-3 align-top">
        <div className="font-ui text-[12.5px] font-medium text-[var(--manara-ink)]">
          {entry.need_label}
        </div>
        <div className="font-mono text-[10.5px] text-[var(--manara-ink-muted)]">
          {entry.need}
        </div>
      </td>
      <td className="px-3 py-3 align-top">
        {entry.selected_capability_id ? (
          <code className="font-mono text-[11.5px] text-[var(--manara-teal)]">
            {entry.selected_capability_id}
          </code>
        ) : (
          <span className="font-ui text-[11.5px] text-[var(--manara-ink-muted)]">—</span>
        )}
        {entry.selection_reasoning && (
          <div className="mt-1 font-ui text-[11px] leading-[1.5] text-[var(--manara-ink-muted)] max-w-[280px]">
            {entry.selection_reasoning}
          </div>
        )}
      </td>
      <td className="px-3 py-3 align-top">
        {entry.connector_ids.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {entry.connector_ids.map((cid) => (
              <code
                key={cid}
                className="font-mono text-[10.5px] rounded bg-[var(--manara-mist)] px-1.5 py-0.5 text-[var(--manara-ink-light)]"
              >
                {cid}
              </code>
            ))}
          </div>
        ) : (
          <span className="font-ui text-[11.5px] text-[var(--manara-ink-muted)]">—</span>
        )}
      </td>
      <td className="px-3 py-3 align-top text-end">
        <CoverageBadge level={entry.coverage_level} />
      </td>
    </tr>
  );
}

function GapRow({ gap }: { gap: GapEntry }) {
  const { t, dir } = useLanguage();
  return (
    <div
      className="rounded-md border p-3.5"
      style={{
        borderColor: 'rgba(196, 69, 69, 0.25)',
        background: 'var(--coverage-none-bg)',
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <AlertTriangle className="size-3.5 text-[var(--coverage-none)]" aria-hidden />
        <span className="font-ui text-[12.5px] font-medium text-[var(--manara-ink)]">
          {gap.need_label}
        </span>
        <code className="font-mono text-[10.5px] text-[var(--manara-ink-muted)]">
          {gap.need}
        </code>
        <span className="ml-auto">
          <CoverageBadge level={gap.coverage_level} />
        </span>
      </div>
      <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
        <div>
          <span className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.10em] text-[var(--manara-ink-muted)]">
            {t('home.foundryResolution')}:
          </span>
          <span className="ms-1.5 font-mono text-[11.5px] text-[var(--coverage-none)]">
            {gap.foundry_resolution}
          </span>
        </div>
        {gap.catalog_capability_id && (
          <div>
            <span className="font-ui text-[10.5px] font-semibold uppercase tracking-[0.10em] text-[var(--manara-ink-muted)]">
              {t('home.capability')}:
            </span>
            <code className="ms-1.5 font-mono text-[11px] text-[var(--manara-teal)]">
              {gap.catalog_capability_id}
            </code>
          </div>
        )}
      </div>
      {gap.resolution_notes && (
        <p className="mt-2 flex items-start gap-1.5 font-ui text-[11.5px] leading-[1.55] text-[var(--manara-ink-light)]">
          <CornerDownRight className="size-3 mt-0.5 shrink-0 text-[var(--manara-ink-muted)]" aria-hidden />
          {gap.resolution_notes}
        </p>
      )}
    </div>
  );
}

function SkeletonRow({ width = '100%' }: { width?: string }) {
  return (
    <div
      className="manara-shimmer h-3.5 rounded"
      style={{ width }}
      aria-hidden
    />
  );
}

function BigSpinner() {
  return (
    <svg
      className="size-6 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" stroke="var(--manara-teal)" strokeWidth="2.5" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="var(--manara-teal)" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/* ============================================================
   Utils
   ============================================================ */
function formatUtc(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC');
  } catch {
    return iso;
  }
}
