'use client';

/* ============================================================
   MANARA Hero — Visual Fidelity Reconstruction
   Mission: MANARA-UI-VISUAL-FIDELITY-01
   Decision 01: Preserve original photorealistic lighthouse
   Decision 04: LIGHT sidebar (handled in Sidebar.tsx)
   Decision 05: Functional honesty (no Pause/Edit/Global Search)

   Layout per approved 01_Home/a_wide_high_resolution_ui_website_app_dashboard_s.png:
   - Editorial headline (serif) with teal accent
   - Single-line research question bar (not a big textarea)
   - Submit button with arrow
   - 3-step workflow as horizontal cards with circular icons + arrows
   - Lighthouse hero on right side with knowledge-graph overlay
   - "A more transparent research process" promo card
   - "Explore MANARA's capabilities" grid (4 items)
   ============================================================ */

import * as React from 'react';
import {
  Search, Sparkles, ArrowRight, Eraser, AlertTriangle,
  Compass, Microscope, Network, BookOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';
import { Pill } from './Badges';

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
  {
    key: 'step1',
    icon: Compass,
    fallback_en: 'Analyze needs',
    fallback_ar: 'تحليل الاحتياجات',
    desc_en: 'We decompose your question into specific research needs and identify the capabilities required to address them.',
    desc_ar: 'نحلل سؤالك إلى احتياجات بحثية محددة ونحدد القدرات اللازمة لمعالجتها.',
  },
  {
    key: 'step2',
    icon: Microscope,
    fallback_en: 'Check coverage',
    fallback_ar: 'فحص التغطية',
    desc_en: 'We verify which needs have operational source connectors and which are gaps that must be reported honestly.',
    desc_ar: 'نتحقق من احتياجات المصادر التشغيلية والفجوات التي يجب الإبلاغ عنها بصدق.',
  },
  {
    key: 'step3',
    icon: Network,
    fallback_en: 'Build investigation',
    fallback_ar: 'بناء التحقيق',
    desc_en: 'We construct a systematic investigation plan with traceable evidence, claims, and forecast scenarios.',
    desc_ar: 'نبني خطة تحقيق منهجية بأدلة وادعاءات وسيناريوهات تنبؤية قابلة للتتبع.',
  },
] as const;

const EXAMPLES = ['home.examples.1', 'home.examples.2', 'home.examples.3'] as const;

const EXPLORE_CARDS = [
  {
    icon: Search,
    title_en: 'Investigations',
    title_ar: 'التحقيقات',
    desc_en: 'Systematic research paths with traceable evidence and bitemporal memory.',
    desc_ar: 'مسارات بحث منهجية بأدلة قابلة للتتبع وذاكرة ثنائية الزمن.',
    accent: 'var(--manara-teal)',
  },
  {
    icon: BookOpen,
    title_en: 'Knowledge Memory',
    title_ar: 'ذاكرة المعرفة',
    desc_en: 'Evidence, claims, and relationships preserved with provenance and audit trail.',
    desc_ar: 'أدلة وادعاءات وعلاقات محفوظة بالمصدر وسجل التدقيق.',
    accent: 'var(--manara-brass)',
  },
  {
    icon: Sparkles,
    title_en: 'Capability Registry',
    title_ar: 'سجل القدرات',
    desc_en: 'Reusable research capabilities with semantic search and coverage tiers.',
    desc_ar: 'قدرات بحثية قابلة لإعادة الاستخدام مع بحث دلالي ومستويات تغطية.',
    accent: 'var(--manara-ink-light)',
  },
  {
    icon: Network,
    title_en: 'Foresight',
    title_ar: 'التنبؤ',
    desc_en: 'Forecast scenarios, probability distributions, and backtests with leakage detection.',
    desc_ar: 'سيناريوهات التنبؤ والتوزيعات الاحتمالية والاختبارات الرجعية مع كشف التسرب.',
    accent: 'var(--manara-success)',
  },
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
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const isAr = dir === 'rtl';

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  const charCount = query.length;

  return (
    <section aria-labelledby="home-headline" className="relative">
      {/* ── Hero top: headline + lighthouse artwork ─────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-8 lg:gap-12 items-start">
        {/* Left: copy + composer */}
        <div className="flex flex-col pt-4">
          {/* Eyebrow */}
          <div className="mb-5 flex items-center gap-3">
            <span
              aria-hidden
              className="inline-block h-px w-10"
              style={{ background: 'var(--manara-brass)' }}
            />
            <span className="font-ui text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--manara-brass)]">
              {isAr ? 'منارة · منصة البحث العلمي' : 'MANARA · Scientific Research Platform'}
            </span>
          </div>

          {/* Headline — editorial serif */}
          <h1
            id="home-headline"
            className="font-serif text-[40px] leading-[1.08] sm:text-[48px] md:text-[56px] md:leading-[1.05] font-semibold text-[var(--manara-ink)] tracking-[-0.02em]"
            style={{ fontFamily: 'var(--font-source-serif), Georgia, serif' }}
          >
            {t('home.headline.prefix')}{' '}
            <span className="relative inline-block">
              <span className="text-[var(--manara-teal)] italic">{t('home.headline.accent')}</span>
              <span
                aria-hidden
                className="absolute -bottom-1 inset-x-0 h-[3px] rounded-full"
                style={{
                  background: 'linear-gradient(90deg, var(--manara-teal) 0%, transparent 90%)',
                  opacity: 0.6,
                }}
              />
            </span>{' '}
            {t('home.headline.suffix')}
          </h1>

          <p className="mt-6 max-w-[560px] font-serif text-[17px] md:text-[18px] leading-[1.65] text-[var(--manara-ink-light)] italic">
            {isAr
              ? 'منصة بحثية متكاملة تحوّل سؤالك العلمي إلى تحقيق منهجي بأدلة قابلة للتتبع، تغطية موثقة، وتنبؤات صريحة.'
              : 'Turn your research question into a systematic investigation with traceable evidence, documented coverage, and honest forecasts.'}
          </p>

          {/* Composer — single-line editorial bar (per approved design) */}
          <div className="mt-8">
            <ComposerBar
              ref={inputRef}
              query={query}
              onQueryChange={onQueryChange}
              onSubmit={onSubmit}
              onClear={onClear}
              onKeyDown={onKeyDown}
              submitting={submitting}
              isValid={isValid}
              overLimit={overLimit}
              charCount={charCount}
              isAr={isAr}
            />

            {/* Examples — subtle chips below the bar */}
            <div className="mt-4">
              <div className="mb-2 font-ui text-[10.5px] font-semibold uppercase tracking-[0.16em] text-[var(--manara-ink-muted)]">
                {isAr ? 'جرّب مثالاً' : 'Try an example'}
              </div>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => onExample(t(k))}
                    className={cn(
                      'group inline-flex max-w-full items-center gap-1.5 rounded-md px-2.5 py-1',
                      'text-start font-ui text-[11.5px] leading-snug text-[var(--manara-ink-light)]',
                      'transition-colors hover:text-[var(--manara-teal)]',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
                    )}
                  >
                    <span className="size-1 rounded-full bg-[var(--manara-brass)] opacity-60 group-hover:opacity-100 transition-opacity" />
                    <span className="line-clamp-1">{t(k)}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right: lighthouse hero artwork with knowledge-graph overlay */}
        <div className="relative order-first lg:order-last">
          <LighthouseHeroPanel isAr={isAr} />
        </div>
      </div>

      {/* ── 3-step workflow (horizontal cards with circular icons + arrows) ── */}
      <div className="mt-16 md:mt-24">
        <div className="mb-7 flex items-center gap-3">
          <span
            aria-hidden
            className="inline-block h-px w-10"
            style={{ background: 'var(--manara-teal)' }}
          />
          <span className="font-ui text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--manara-teal)]">
            {isAr ? 'كيف يعمل منارة' : 'How MANARA works'}
          </span>
        </div>
        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-5 md:gap-8">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            return (
              <div key={step.key} className="relative">
                <div className="flex flex-col gap-4 rounded-[12px] border border-[var(--manara-mist)] bg-[var(--manara-white)] p-6 manara-shadow-soft">
                  {/* Circular icon */}
                  <div className="flex items-center justify-between">
                    <div
                      className="flex size-12 items-center justify-center rounded-full"
                      style={{
                        background: 'linear-gradient(135deg, rgba(44, 115, 128, 0.12) 0%, rgba(187, 147, 98, 0.08) 100%)',
                        border: '1px solid rgba(44, 115, 128, 0.25)',
                        color: 'var(--manara-teal)',
                      }}
                    >
                      <Icon className="size-5" strokeWidth={1.6} />
                    </div>
                    <span className="font-serif text-[36px] font-light leading-none text-[var(--manara-mist)]">
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                  </div>
                  <div>
                    <h3 className="font-serif text-[19px] font-semibold text-[var(--manara-ink)] tracking-[-0.01em]">
                      {isAr ? step.fallback_ar : step.fallback_en}
                    </h3>
                    <p className="mt-2 font-ui text-[13px] leading-[1.65] text-[var(--manara-ink-light)]">
                      {isAr ? step.desc_ar : step.desc_en}
                    </p>
                  </div>
                </div>
                {/* Connector arrow between cards (desktop only) */}
                {idx < STEPS.length - 1 && (
                  <div
                    aria-hidden
                    className={cn(
                      'hidden md:flex absolute top-1/2 -translate-y-1/2 z-10',
                      'size-8 items-center justify-center rounded-full',
                      'bg-[var(--manara-white)] border border-[var(--manara-mist)] manara-shadow-soft',
                    )}
                    style={
                      isAr
                        ? { left: -22 }
                        : { right: -22 }
                    }
                  >
                    {isAr ? (
                      <ArrowRight className="size-3.5 text-[var(--manara-teal)] rotate-180" />
                    ) : (
                      <ArrowRight className="size-3.5 text-[var(--manara-teal)]" />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Explore MANARA's capabilities (4-card grid) ───────────── */}
      <div className="mt-16 md:mt-20">
        <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-serif text-[24px] md:text-[28px] font-semibold text-[var(--manara-ink)] tracking-[-0.015em]">
              {isAr ? 'استكشف قدرات منارة' : "Explore MANARA's capabilities"}
            </h2>
            <p className="mt-1.5 font-ui text-[13px] text-[var(--manara-ink-muted)]">
              {isAr
                ? 'منصة بحثية متكاملة — من السؤال إلى التسليم.'
                : 'A complete research platform — from question to deliverable.'}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {EXPLORE_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.title_en}
                className={cn(
                  'group relative flex flex-col gap-3 rounded-[10px] border border-[var(--manara-mist)]',
                  'bg-[var(--manara-white)] p-5 manara-shadow-soft',
                  'transition-all hover:shadow-lg hover:border-[var(--manara-teal)]/40',
                )}
              >
                <div
                  className="flex size-9 items-center justify-center rounded-md"
                  style={{ background: 'rgba(44, 115, 128, 0.08)', color: card.accent }}
                >
                  <Icon className="size-[18px]" strokeWidth={1.6} />
                </div>
                <div>
                  <h3 className="font-serif text-[15px] font-semibold text-[var(--manara-ink)]">
                    {isAr ? card.title_ar : card.title_en}
                  </h3>
                  <p className="mt-1.5 font-ui text-[12px] leading-[1.6] text-[var(--manara-ink-light)]">
                    {isAr ? card.desc_ar : card.desc_en}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── "A more transparent research process" promo card ────────── */}
      <div className="mt-12 md:mt-16">
        <PromoCard isAr={isAr} />
      </div>
    </section>
  );
}

/* ============================================================
   ComposerBar — single-line editorial input (per approved design)
   ============================================================ */

const ComposerBar = React.forwardRef<
  HTMLInputElement,
  {
    query: string;
    onQueryChange: (v: string) => void;
    onSubmit: () => void;
    onClear: () => void;
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
    submitting: boolean;
    isValid: boolean;
    overLimit: boolean;
    charCount: number;
    isAr: boolean;
  }
>(function ComposerBar(
  { query, onQueryChange, onSubmit, onClear, onKeyDown, submitting, isValid, overLimit, charCount, isAr },
  ref,
) {
  const { t } = useLanguage();
  const remaining = 1000 - charCount;
  const counterColor = overLimit
    ? 'var(--coverage-none)'
    : remaining < 100
      ? 'var(--coverage-operational)'
      : 'var(--manara-ink-muted)';

  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          'group relative flex items-center gap-2 rounded-[12px] border bg-[var(--manara-white)] px-4 py-3.5 manara-shadow-soft-lg',
          'transition-all focus-within:border-[var(--manara-teal)] focus-within:shadow-lg',
          overLimit ? 'border-[var(--coverage-none)]/40' : 'border-[var(--manara-mist)]',
        )}
      >
        <Search
          className="size-5 shrink-0 text-[var(--manara-ink-muted)] group-focus-within:text-[var(--manara-teal)] transition-colors"
          strokeWidth={1.6}
        />
        <input
          ref={ref}
          id="manara-query"
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={isAr
            ? 'ما الذي تريد اكتشافه اليوم؟'
            : 'What do you want to discover today?'}
          aria-label={t('home.composerLabel')}
          className={cn(
            'flex-1 min-w-0 bg-transparent font-serif text-[15px] md:text-[16px]',
            'text-[var(--manara-ink)] placeholder:text-[var(--manara-ink-muted)]/70 placeholder:italic',
            'focus:outline-none',
          )}
          style={{ fontFamily: 'var(--font-source-serif), Georgia, serif' }}
        />
        {/* Char counter */}
        <span
          className="font-mono text-[10.5px] tabular-nums shrink-0"
          style={{ color: counterColor }}
        >
          {charCount}/1000
        </span>
        {/* Clear button (only when text exists) */}
        {query.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            aria-label={t('home.clear')}
            className="shrink-0 size-7 inline-flex items-center justify-center rounded-md text-[var(--manara-ink-muted)] hover:bg-[var(--manara-mist)] hover:text-[var(--manara-ink)] transition-colors"
          >
            <Eraser className="size-3.5" />
          </button>
        )}
        {/* Submit button with arrow */}
        <button
          type="button"
          onClick={onSubmit}
          disabled={!isValid || submitting || overLimit}
          aria-label={t('home.submit')}
          className={cn(
            'shrink-0 inline-flex items-center gap-2 rounded-md px-4 py-2 font-ui text-[12.5px] font-medium',
            'transition-all',
            (!isValid || submitting || overLimit)
              ? 'bg-[var(--manara-mist)] text-[var(--manara-ink-muted)] cursor-not-allowed'
              : 'bg-[var(--manara-teal)] text-white hover:bg-[var(--manara-teal-dark)] manara-shadow-soft',
          )}
        >
          {submitting ? (
            <span className="size-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
          ) : (
            <>
              <span>{isAr ? 'ابدأ التحقيق' : t('home.submit')}</span>
              <ArrowRight className={cn('size-3.5', isAr && 'rotate-180')} />
            </>
          )}
        </button>
      </div>
      {/* Helper line */}
      <div className="flex items-center justify-between gap-3 px-2">
        <div className="flex items-center gap-2 font-ui text-[10.5px] text-[var(--manara-ink-muted)]">
          {overLimit ? (
            <>
              <AlertTriangle className="size-3 text-[var(--coverage-none)]" />
              <span className="text-[var(--coverage-none)]">
                {isAr ? 'تجاوز الحد (1000 حرف)' : 'Character limit exceeded (1000 max)'}
              </span>
            </>
          ) : !isValid && query.length > 0 ? (
            <span>{isAr ? 'الحد الأدنى 10 أحرف' : 'Minimum 10 characters'}</span>
          ) : (
            <span>{isAr ? '10–1000 حرف · Enter للإرسال' : '10–1000 characters · Enter to submit'}</span>
          )}
        </div>
        <span className="font-mono text-[10px] text-[var(--manara-ink-muted)]/70">
          {isAr ? 'تجريبي · مستأجر واحد' : 'Demo · Single-tenant'}
        </span>
      </div>
    </div>
  );
});

/* ============================================================
   LighthouseHeroPanel — photorealistic artwork + knowledge-graph overlay
   Per Decision 01: preserve original lighthouse, build KG overlay in HTML/SVG
   ============================================================ */

function LighthouseHeroPanel({ isAr }: { isAr: boolean }) {
  return (
    <div
      className="relative w-full aspect-[4/3] rounded-[16px] overflow-hidden manara-shadow-elevated"
      style={{
        background: 'linear-gradient(160deg, #F7F8F6 0%, #E8EFF1 50%, #DDE7EB 100%)',
        border: '1px solid var(--manara-mist)',
      }}
    >
      {/* Photorealistic lighthouse artwork (extracted from approved image) */}
      <img
        src="/hero/lighthouse-hero-base.png"
        alt={isAr ? 'منارة على صخرة' : 'Lighthouse on rocky cliff'}
        className="absolute inset-0 w-full h-full object-cover"
        style={{ objectPosition: 'center' }}
        loading="eager"
      />

      {/* Subtle radial gradient overlay for atmospheric depth */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(circle at 30% 50%, transparent 0%, rgba(247, 248, 246, 0.15) 80%)',
        }}
      />

      {/* Knowledge-graph overlay — positioned nodes + curved edges */}
      <KnowledgeGraphOverlay isAr={isAr} />

      {/* Bottom badge */}
      <div className="absolute bottom-4 inset-x-4 flex justify-center">
        <Pill
          variant="brass"
          className="backdrop-blur-md whitespace-nowrap overflow-hidden text-ellipsis max-w-full bg-white/80"
        >
          <span className="size-1.5 rounded-full bg-[var(--manara-brass)] shrink-0 manara-beam" />
          <span className="truncate font-ui text-[11px]">
            {isAr ? 'منارة · ضوء يهدي البحث' : 'MANARA · Guiding light for research'}
          </span>
        </Pill>
      </div>
    </div>
  );
}

/* ============================================================
   KnowledgeGraphOverlay — HTML/SVG nodes + curved edges
   Real data only — nodes represent the 6 phases of investigation
   ============================================================ */

function KnowledgeGraphOverlay({ isAr }: { isAr: boolean }) {
  // Node positions are percentages within the hero panel
  // Designed to overlay the lighthouse artwork without obscuring the tower (center)
  const nodes = [
    { id: 'question', label_en: 'Research Question', label_ar: 'سؤال البحث', x: 12, y: 22, accent: 'var(--manara-teal)' },
    { id: 'needs', label_en: 'Knowledge Needs', label_ar: 'الاحتياجات', x: 8, y: 65, accent: 'var(--manara-brass)' },
    { id: 'sources', label_en: 'Reliable Sources', label_ar: 'المصادر', x: 22, y: 88, accent: 'var(--manara-teal)' },
    { id: 'evidence', label_en: 'Answers with Evidence', label_ar: 'إجابات بأدلة', x: 75, y: 15, accent: 'var(--manara-success)' },
    { id: 'synthesis', label_en: 'Analysis & Synthesis', label_ar: 'تحليل وتركيب', x: 78, y: 48, accent: 'var(--manara-teal)' },
    { id: 'future', label_en: 'Future Outlooks', label_ar: 'آفاق مستقبلية', x: 80, y: 78, accent: 'var(--manara-brass)' },
  ];

  // Edges connect nodes around the central lighthouse area
  const edges = [
    ['question', 'needs'],
    ['needs', 'sources'],
    ['question', 'evidence'],
    ['sources', 'synthesis'],
    ['evidence', 'synthesis'],
    ['synthesis', 'future'],
  ];

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  return (
    <div className="absolute inset-0 pointer-events-none">
      {/* SVG edges layer */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden
      >
        <defs>
          <linearGradient id="kgEdgeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--manara-teal)" stopOpacity="0.4" />
            <stop offset="50%" stopColor="var(--manara-brass)" stopOpacity="0.6" />
            <stop offset="100%" stopColor="var(--manara-teal)" stopOpacity="0.4" />
          </linearGradient>
          <filter id="kgGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="0.6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {edges.map(([from, to], i) => {
          const a = nodeMap[from];
          const b = nodeMap[to];
          // Curved bezier between nodes
          const midX = (a.x + b.x) / 2;
          const midY = (a.y + b.y) / 2 - 8; // arc upward
          return (
            <path
              key={i}
              d={`M ${a.x} ${a.y} Q ${midX} ${midY} ${b.x} ${b.y}`}
              stroke="url(#kgEdgeGradient)"
              strokeWidth="0.4"
              fill="none"
              filter="url(#kgGlow)"
              opacity="0.7"
            />
          );
        })}
      </svg>

      {/* Nodes layer */}
      {nodes.map((node) => (
        <div
          key={node.id}
          className="absolute flex flex-col items-center gap-1.5"
          style={{
            left: `${node.x}%`,
            top: `${node.y}%`,
            transform: 'translate(-50%, -50%)',
          }}
        >
          {/* Glowing node dot */}
          <div className="relative">
            <div
              className="size-3 rounded-full"
              style={{
                background: node.accent,
                boxShadow: `0 0 8px ${node.accent}, 0 0 16px ${node.accent}40`,
              }}
            />
            <div
              className="absolute inset-0 rounded-full animate-ping"
              style={{ background: node.accent, opacity: 0.3, animationDuration: '3s' }}
            />
          </div>
          {/* Label */}
          <div
            className="px-2 py-0.5 rounded font-ui text-[9.5px] font-medium text-[var(--manara-ink)] whitespace-nowrap"
            style={{
              background: 'rgba(255, 255, 255, 0.85)',
              backdropFilter: 'blur(4px)',
              border: `1px solid ${node.accent}40`,
            }}
          >
            {isAr ? node.label_ar : node.label_en}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   PromoCard — "A more transparent research process"
   ============================================================ */

function PromoCard({ isAr }: { isAr: boolean }) {
  return (
    <div
      className="relative overflow-hidden rounded-[14px] border border-[var(--manara-mist)] manara-shadow-soft-lg"
      style={{
        background: 'linear-gradient(135deg, var(--manara-ink) 0%, #1F4055 60%, #2C7380 100%)',
      }}
    >
      {/* Decorative background pattern (subtle stars) */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: `
            radial-gradient(circle at 15% 25%, white 1px, transparent 1.5px),
            radial-gradient(circle at 75% 15%, white 0.8px, transparent 1.2px),
            radial-gradient(circle at 35% 75%, white 1px, transparent 1.5px),
            radial-gradient(circle at 85% 65%, white 0.7px, transparent 1.2px),
            radial-gradient(circle at 50% 40%, white 0.6px, transparent 1px)
          `,
          backgroundSize: '120px 120px, 90px 90px, 150px 150px, 80px 80px, 100px 100px',
        }}
      />

      {/* Lighthouse beam accent */}
      <div
        aria-hidden
        className="absolute top-0 right-0 w-1/3 h-full manara-beam"
        style={{
          background: 'radial-gradient(circle at 100% 50%, rgba(242, 200, 121, 0.25) 0%, transparent 60%)',
        }}
      />

      <div className="relative p-8 md:p-10 grid grid-cols-1 md:grid-cols-[2fr_1fr] gap-6 items-center">
        <div>
          <div className="mb-3 font-ui text-[10.5px] font-semibold uppercase tracking-[0.22em] text-[var(--manara-brass)]">
            {isAr ? 'منهجية شفافة' : 'A transparent methodology'}
          </div>
          <h3 className="font-serif text-[24px] md:text-[28px] font-semibold text-white leading-[1.15] tracking-[-0.01em]">
            {isAr
              ? 'عملية بحث أكثر شفافية — كل خطوة موثقة'
              : 'A more transparent research process — every step documented'}
          </h3>
          <p className="mt-3 font-ui text-[13px] leading-[1.7] text-white/75 max-w-[480px]">
            {isAr
              ? 'منارة لا تخترع نتائج. كل ادعاء مدعوم بأدلة قابلة للتتبع، كل فجوة مُبلَّغ عنها بصدق، وكل تنبؤ مُختبَر ضد البيانات التاريخية.'
              : 'MANARA does not fabricate results. Every claim is backed by traceable evidence, every gap is honestly reported, and every forecast is backtested against historical data.'}
          </p>
        </div>
        <div className="flex md:justify-end">
          <Pill variant="brass" className="bg-white/10 border-white/20 text-[var(--manara-brass)] backdrop-blur-sm">
            <span className="size-1.5 rounded-full bg-[var(--manara-brass)] manara-beam" />
            <span className="font-ui text-[11px]">{isAr ? 'منهجية المنارة' : 'The MANARA Method'}</span>
          </Pill>
        </div>
      </div>
    </div>
  );
}
