'use client';

/* ============================================================
   MANARA Hero — Visual Source Integration
   Mission: MANARA-UI-PAGE01-SOURCE-INTEGRATION-01

   Visual source: AgentCraft-MANARA/IMPLEMENTATION_READY/
     MANARA_PAGE_01_HTML_CSS_SOURCE_v1.zip
     Git blob SHA: 9de2e0bb6995e67d47d56b533ff22ee686f2bbc4

   Integration rules (per owner directive):
   - Preserve structure, geometry, typography, artwork, styles from the
     HTML/CSS reference wherever possible.
   - Port to React components, bind to real POST /mold-factory/compose API.
   - Replace Unicode glyph icons with Lucide icons (the reference used
     generic shapes; per README "preserve the visual hierarchy while using
     approved functional copy and real state").
   - Real states: idle, invalid, composing, success, partial coverage,
     coverage blocker, network/API failure.
   - Per OPEN-04: no user profile / role switcher (reference correctly omits
     "Researcher" avatar).
   - Per OPEN-03: no global dark-mode toggle.
   - Per README: EN/AR only (no FR/DE/ES).
   - Per Decision 05: header search is INERT (no global search endpoint) —
     render but do not wire to a real action.
   ============================================================ */

import * as React from 'react';
import {
  ArrowRight, Eraser, AlertTriangle, Compass, Database, Network,
  BookOpen, TrendingUp, FileText, Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';

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

// Per approved reference verbatim (VLM-transcribed from approved-home.png)
const STEPS = [
  {
    num: '1',
    icon: Compass,
    title_en: 'Analyze the question',
    title_ar: 'حلِّل السؤال',
    desc_en: 'Identify knowledge needs and break down the research problem directly from your question.',
    desc_ar: 'حدِّد الاحتياجات المعرفية وحلِّل مشكلة البحث مباشرةً من سؤالك.',
  },
  {
    num: '2',
    icon: Database,
    title_en: 'Assess source coverage',
    title_ar: 'قيِّم تغطية المصادر',
    desc_en: 'Explore available sources and evaluate what is covered and what is missing.',
    desc_ar: 'استكشف المصادر المتاحة وقيِّم ما هو مُغطَّى وما هو مفقود.',
  },
  {
    num: '3',
    icon: Network,
    title_en: 'Build the investigation path',
    title_ar: 'ابنِ مسار التحقيق',
    desc_en: 'Create a systematic research plan and execute it through specialized agents and tools.',
    desc_ar: 'أنشئ خطة بحث منهجية ونفِّذها عبر وكلاء وأدوات متخصصة.',
  },
] as const;

// Per approved reference verbatim
const CAPABILITY_CARDS = [
  {
    icon: FileText,
    title_en: 'Investigations',
    title_ar: 'التحقيقات',
    desc_en: 'Conduct in-depth research on complex topics.',
    desc_ar: 'أجرِ أبحاثاً متعمقة في مواضيع معقدة.',
  },
  {
    icon: BookOpen,
    title_en: 'Knowledge Memory',
    title_ar: 'ذاكرة المعرفة',
    desc_en: 'Explore evidence and past findings.',
    desc_ar: 'استكشف الأدلة والنتائج السابقة.',
  },
  {
    icon: TrendingUp,
    title_en: 'Foresight',
    title_ar: 'التنبؤ',
    desc_en: 'Analyze trends and future possibilities.',
    desc_ar: 'حلِّل الاتجاهات والاحتمالات المستقبلية.',
  },
  {
    icon: FileText,
    title_en: 'Research Reports',
    title_ar: 'تقارير البحث',
    desc_en: 'Generate and review structured reports with citations.',
    desc_ar: 'أنشئ وراجِع تقارير منظمة مع استشهادات.',
  },
] as const;

export function Hero({
  query,
  onQueryChange,
  onSubmit,
  onClear,
  submitting,
  isValid,
  overLimit,
}: HeroProps) {
  const { dir } = useLanguage();
  const inputRef = React.useRef<HTMLTextAreaElement | null>(null);
  const isAr = dir === 'rtl';

  // Per Point G / approved: Enter submits, Shift+Enter for newline
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  const charCount = query.length;

  return (
    <section aria-labelledby="hero-title" className="manara-hero">
      {/* ── Hero artwork (right side) — owner-provided lighthouse-scene.png ── */}
      <div
        className="manara-hero-art"
        role="img"
        aria-label={isAr
          ? 'عمل فني للمنارة مع تراكب شبكة المعرفة من التصميم المعتمد'
          : 'Photorealistic lighthouse and knowledge graph artwork from the approved MANARA composition'}
      />

      {/* ── Hero copy (left side) ─────────────────────────────────────── */}
      <div className="manara-hero-copy">
        <p className="manara-eyebrow">
          <Sparkles className="manara-eyebrow-icon" aria-hidden />
          {isAr
            ? 'و ر ش ة   ا ل ذ ك ا ء   ا ل ع ل م ي'
            : 'S C I E N T I F I C   I N T E L L I G E N C E   A T E L I E R'}
        </p>
        <h1 id="hero-title" className="manara-hero-title">
          {isAr ? (
            <>
              ماذا تريد أن<br />
              <em className="manara-hero-accent">تكتشف</em> اليوم؟
            </>
          ) : (
            <>
              What do you want<br />
              to <em className="manara-hero-accent">discover</em> today?
            </>
          )}
        </h1>
        <p className="manara-hero-description">
          {isAr
            ? 'حوِّل سؤالك البحثي إلى تحقيق منهجي يستكشف المصادر، يجمع الأدلة، ويكشف ما يمكن إثباته.'
            : 'Turn your research question into a systematic investigation that explores sources, gathers evidence, and reveals what can be proven.'}
        </p>
      </div>

      {/* ── Question card (single-line editorial composer per approved) ── */}
      <div className="manara-question-card">
        <label className="manara-sr-only" htmlFor="manara-query">
          {isAr ? 'سؤال البحث' : 'Research question'}
        </label>
        <textarea
          ref={inputRef}
          id="manara-query"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={onKeyDown}
          maxLength={1000}
          rows={2}
          placeholder={isAr
            ? 'أدخل سؤالك البحثي...'
            : 'Enter your research question...'}
          aria-label={isAr ? 'سؤال البحث' : 'Research question'}
          dir={isAr ? 'rtl' : 'ltr'}
          className={cn('manara-question-input', overLimit && 'manara-question-input--error')}
        />
        <div className="manara-question-actions">
          <span className="manara-question-hint">
            {isAr
              ? 'مثال: ما مستقبل الأطراف الاصطناعية الذكية خلال العقد القادم؟'
              : 'e.g. What is the future of intelligent prosthetics over the next decade?'}
          </span>
          <div className="manara-question-submit">
            <span className="manara-char-counter" style={{ color: overLimit ? 'var(--coverage-none)' : 'var(--manara-ink-muted)' }}>
              {charCount} / 1000
            </span>
            {query.length > 0 && (
              <button
                type="button"
                onClick={onClear}
                aria-label={isAr ? 'مسح' : 'Clear'}
                className="manara-clear-btn"
              >
                <Eraser className="size-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={onSubmit}
              disabled={!isValid || submitting || overLimit}
              className={cn(
                'manara-primary-btn',
                (!isValid || submitting || overLimit) && 'manara-primary-btn--disabled',
              )}
            >
              {submitting ? (
                <span className="manara-spinner" aria-hidden />
              ) : (
                <>
                  <span>{isAr ? 'ابدأ التحقيق' : 'Start Investigation'}</span>
                  <ArrowRight className={cn('size-3.5', isAr && 'rotate-180')} />
                </>
              )}
            </button>
          </div>
        </div>
        <div className="manara-question-chips">
          <span>{isAr ? '◉ 10–1000 حرف' : '◉ 10–1000 characters'}</span>
          <span>{isAr ? '♧ بحث قائم على الأدلة' : '♧ Evidence-based research'}</span>
          <span>{isAr ? '◉ تحليل تغطية المصادر' : '◉ Source coverage analysis'}</span>
          {overLimit && (
            <span className="manara-chip-error">
              <AlertTriangle className="size-3" />
              {isAr ? 'تجاوز الحد' : 'Limit exceeded'}
            </span>
          )}
        </div>
        {/* Status / error message slot — populated by parent via aria-live */}
        <div className="manara-status" role="status" aria-live="polite" />
      </div>

      {/* ── Below the hero: How MANARA works + bottom grid ───────────── */}
      <div className="manara-below">
        <div className="manara-section-title">
          <div>
            <h2>{isAr ? 'كيف يعمل منارة' : 'How MANARA works'}</h2>
            <p>
              {isAr
                ? 'من سؤالك إلى معرفة موثوقة عبر عملية بحث شفافة.'
                : 'From your question to trusted knowledge through a transparent research process.'}
            </p>
          </div>
          <span className="manara-learn-more">
            {isAr ? 'تعلَّم المزيد عن منارة' : 'Learn more about MANARA'}
            <ArrowRight className={cn('size-3 inline', isAr && 'rotate-180')} />
          </span>
        </div>

        {/* 3-step process with arrows between */}
        <div className="manara-steps">
          {STEPS.map((step, idx) => {
            const Icon = step.icon;
            return (
              <React.Fragment key={step.num}>
                <div className="manara-step">
                  <span className="manara-step-number">{step.num}</span>
                  <span className="manara-step-illustration">
                    <Icon className="size-9" strokeWidth={1.4} />
                  </span>
                  <div>
                    <h3>{isAr ? step.title_ar : step.title_en}</h3>
                    <p>{isAr ? step.desc_ar : step.desc_en}</p>
                  </div>
                </div>
                {idx < STEPS.length - 1 && (
                  <span className="manara-step-arrow" aria-hidden>
                    <ArrowRight className={cn('size-5', isAr && 'rotate-180')} />
                  </span>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Bottom grid: mountain promo card + capabilities grid */}
        <div className="manara-bottom-grid">
          <article className="manara-mountain-card">
            <h2>
              {isAr ? (
                <>عملية بحث<br />أكثر شفافية</>
              ) : (
                <>A more transparent<br />research process</>
              )}
            </h2>
            <p>
              {isAr
                ? 'انظر كيف يجمع منارة المصادر والأدلة والتحليل لتقديم رؤى موثوقة.'
                : 'See how MANARA combines sources, evidence, and analysis to deliver trustworthy insights.'}
            </p>
            <span className="manara-mountain-cta">
              ▶ {isAr ? 'استكشف سير العمل' : 'Explore the workflow'}
            </span>
          </article>

          <article className="manara-capabilities">
            <h2>{isAr ? 'استكشف قدرات منارة' : "Explore MANARA's capabilities"}</h2>
            <p>
              {isAr
                ? 'تجاوز البحث الواحد. اكتشف الطرق المختلفة للعمل مع المعرفة.'
                : 'Go beyond a single search. Discover the different ways you can work with knowledge.'}
            </p>
            <div className="manara-cap-grid">
              {CAPABILITY_CARDS.map((card) => {
                const Icon = card.icon;
                return (
                  <div key={card.title_en}>
                    <span className="manara-cap-icon">
                      <Icon className="size-5" strokeWidth={1.5} />
                    </span>
                    <b>{isAr ? card.title_ar : card.title_en}</b>
                    <small>{isAr ? card.desc_ar : card.desc_en}</small>
                  </div>
                );
              })}
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}

/* ============================================================
   Styles — adapted from MANARA_PAGE_01_HTML_CSS_SOURCE_v1/styles.css
   Preserving geometry, typography, colors, layout per owner directive
   ============================================================ */

// The styles are imported via the styles.css global file; here we add
// component-scoped styles via a separate CSS file. To keep this PR focused
// and avoid Tailwind purge issues, all manara-* classes are defined in
// src/styles.css (appended).
