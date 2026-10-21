'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import type { CoverageLevel } from './api-client';
import { useLanguage } from './i18n';

/* ============================================================
   CoverageBadge — the four-tier coverage model:
   NONE (red) / CATALOG (orange) / OPERATIONAL (yellow) / VERIFIED (green)
   ============================================================ */

const COVERAGE_STYLES: Record<
  CoverageLevel,
  { bg: string; fg: string; border: string; label_en: string; label_ar: string; dot: string }
> = {
  NONE: {
    bg: 'var(--coverage-none-bg)',
    fg: 'var(--coverage-none)',
    border: 'rgba(196, 69, 69, 0.35)',
    label_en: 'NONE',
    label_ar: 'لا توجد',
    dot: 'var(--coverage-none)',
  },
  CATALOG: {
    bg: 'var(--coverage-catalog-bg)',
    fg: 'var(--coverage-catalog)',
    border: 'rgba(217, 119, 6, 0.35)',
    label_en: 'CATALOG',
    label_ar: 'كتالوج',
    dot: 'var(--coverage-catalog)',
  },
  OPERATIONAL: {
    bg: 'var(--coverage-operational-bg)',
    fg: 'var(--coverage-operational)',
    border: 'rgba(185, 131, 26, 0.35)',
    label_en: 'OPERATIONAL',
    label_ar: 'تشغيلي',
    dot: 'var(--coverage-operational)',
  },
  VERIFIED: {
    bg: 'var(--coverage-verified-bg)',
    fg: 'var(--coverage-verified)',
    border: 'rgba(58, 138, 92, 0.35)',
    label_en: 'VERIFIED',
    label_ar: 'مُتحقق',
    dot: 'var(--coverage-verified)',
  },
};

export function CoverageBadge({
  level,
  className,
  withDot = true,
}: {
  level: CoverageLevel;
  className?: string;
  withDot?: boolean;
}) {
  const { lang } = useLanguage();
  // MANARA-UI-02-LUCIDE-RECOVERY-01 — defensive: if the backend ships an
  // unexpected coverage_level (e.g. lowercase, typo, missing), fall back to
  // NONE rather than throwing "Cannot read properties of undefined (reading
  // 'bg')" — which previously took down the entire ComposeResult subtree.
  const s = COVERAGE_STYLES[level] ?? COVERAGE_STYLES.NONE;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5',
        'font-mono text-[10.5px] font-semibold uppercase tracking-[0.06em]',
        className,
      )}
      style={{
        backgroundColor: s.bg,
        color: s.fg,
        borderColor: s.border,
      }}
      title={lang === 'ar' ? s.label_ar : s.label_en}
    >
      {withDot && (
        <span
          aria-hidden
          className="inline-block size-1.5 rounded-full"
          style={{ backgroundColor: s.dot }}
        />
      )}
      {lang === 'ar' ? s.label_ar : s.label_en}
    </span>
  );
}

/* ============================================================
   StatusBadge — service status indicator
   ============================================================ */

export function StatusBadge({
  status,
  className,
}: {
  status: 'online' | 'offline' | 'checking';
  className?: string;
}) {
  const { t } = useLanguage();
  const styles = {
    online: {
      bg: 'var(--coverage-verified-bg)',
      fg: 'var(--coverage-verified)',
      border: 'rgba(58, 138, 92, 0.35)',
      dot: 'var(--coverage-verified)',
      label: t('status.online'),
    },
    offline: {
      bg: 'var(--coverage-catalog-bg)',
      fg: 'var(--coverage-catalog)',
      border: 'rgba(217, 119, 6, 0.35)',
      dot: 'var(--coverage-catalog)',
      label: t('status.offline'),
    },
    checking: {
      bg: 'var(--manara-mist)',
      fg: 'var(--manara-ink-muted)',
      border: 'rgba(138, 155, 168, 0.35)',
      dot: 'var(--manara-ink-muted)',
      label: t('status.checking'),
    },
  } as const;
  const s = styles[status];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5',
        'font-ui text-[11px] font-medium',
        className,
      )}
      style={{ backgroundColor: s.bg, color: s.fg, borderColor: s.border }}
    >
      <span
        aria-hidden
        className={cn(
          'inline-block size-1.5 rounded-full',
          status === 'checking' && 'animate-pulse',
        )}
        style={{ backgroundColor: s.dot }}
      />
      {s.label}
    </span>
  );
}

/* ============================================================
   Pill — generic label pill
   ============================================================ */

export function Pill({
  children,
  variant = 'mist',
  className,
}: {
  children: React.ReactNode;
  variant?: 'mist' | 'teal' | 'brass' | 'ink' | 'error' | 'success' | 'warning';
  className?: string;
}) {
  const styles = {
    mist: { bg: 'var(--manara-mist)', fg: 'var(--manara-ink-light)', border: 'rgba(138, 155, 168, 0.25)' },
    teal: { bg: 'rgba(44, 115, 128, 0.10)', fg: 'var(--manara-teal)', border: 'rgba(44, 115, 128, 0.30)' },
    brass: { bg: 'rgba(187, 147, 98, 0.12)', fg: 'var(--manara-brass)', border: 'rgba(187, 147, 98, 0.35)' },
    ink: { bg: 'rgba(25, 51, 74, 0.08)', fg: 'var(--manara-ink)', border: 'rgba(25, 51, 74, 0.25)' },
    error: { bg: 'var(--coverage-none-bg)', fg: 'var(--coverage-none)', border: 'rgba(196, 69, 69, 0.35)' },
    success: { bg: 'var(--coverage-verified-bg)', fg: 'var(--coverage-verified)', border: 'rgba(58, 138, 92, 0.35)' },
    warning: { bg: 'var(--coverage-operational-bg)', fg: 'var(--coverage-operational)', border: 'rgba(185, 131, 26, 0.35)' },
  } as const;
  const s = styles[variant];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-ui text-[11px] font-medium',
        className,
      )}
      style={{ backgroundColor: s.bg, color: s.fg, borderColor: s.border }}
    >
      {children}
    </span>
  );
}
