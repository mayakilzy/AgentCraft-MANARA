'use client';

import { Menu, Search, Bell } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';
import { LanguageSwitcher } from './LanguageSwitcher';
import { StatusBadge } from './Badges';

/* ============================================================
   Header — top bar with central search, status, language switcher
   MANARA-UI-PAGE01-RTL-VISUAL-CLOSURE-01: reconciled with approved
   HTML reference.

   Per Decision 05 (Functional Honesty):
   - Global search is INERT — no backend endpoint exists. The search
     bar is rendered for visual fidelity to the approved design but
     is clearly marked as "coming soon" / decorative and does not
     trigger any real action.
   - Bell icon is decorative only (no notifications endpoint).
   - Per OPEN-04: no user profile / role switcher.
   ============================================================ */

interface HeaderProps {
  onOpenMobileNav: () => void;
  status: 'online' | 'offline' | 'checking';
  /** Title + subtitle are no longer rendered in the header per the approved
   *  reference (which uses a central search bar instead). Kept in the props
   *  signature for backwards compatibility with existing call sites. */
  title?: string;
  subtitle?: string;
}

export function Header({
  onOpenMobileNav,
  status,
}: HeaderProps) {
  const { t, dir } = useLanguage();
  const isAr = dir === 'rtl';

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-[var(--manara-mist)]',
        'bg-[var(--manara-canvas)]/85 px-4 backdrop-blur-md md:px-6',
      )}
    >
      {/* Mobile hamburger (visible only on mobile) */}
      <button
        type="button"
        onClick={onOpenMobileNav}
        aria-label={t('header.menu')}
        className={cn(
          'md:hidden inline-flex size-10 items-center justify-center rounded-md',
          'border border-[var(--manara-mist)] bg-[var(--manara-white)] text-[var(--manara-ink)]',
          'hover:bg-[var(--manara-mist)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
        )}
      >
        <Menu className="size-5" />
      </button>

      {/* Central search bar (inert — no global search endpoint; decorative per Decision 05) */}
      {/* Hidden on very small screens to preserve space for status + language */}
      <div
        aria-label={isAr ? 'بحث عام (غير متاح حالياً)' : 'Global search (not available yet)'}
        className={cn(
          'manara-header-search hidden md:flex flex-1 max-w-[420px] items-center gap-2.5 rounded-md border border-[var(--manara-mist)]',
          'bg-[var(--manara-white)] px-3 py-2 text-[var(--manara-ink-muted)]',
          'cursor-not-allowed select-none',
        )}
        title={isAr ? 'البحث العام غير متاح حالياً' : 'Global search not available yet'}
      >
        <Search className="size-4 shrink-0" aria-hidden />
        <span className="flex-1 text-[12px] truncate">
          {isAr ? 'ابحث في التحقيقات أو المصادر أو الموضوعات...' : 'Search investigations, sources, or topics...'}
        </span>
        <kbd
          aria-hidden
          className="hidden lg:inline rounded border border-[var(--manara-mist)] bg-[var(--manara-mist)]/40 px-1.5 py-0.5 font-mono text-[9.5px] text-[var(--manara-ink-muted)]"
        >
          Ctrl + K
        </kbd>
      </div>

      {/* Spacer on mobile (where search is hidden) */}
      <div className="md:hidden flex-1" />

      {/* Right-side cluster: status + bell + language */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Status pill (hidden on very small screens) */}
        <div className="hidden sm:block">
          <StatusBadge status={status} />
        </div>

        {/* Bell icon — decorative (no notifications endpoint) */}
        <button
          type="button"
          aria-label={isAr ? 'الإشعارات (غير متاحة)' : 'Notifications (not available)'}
          title={isAr ? 'الإشعارات غير متاحة حالياً' : 'Notifications not available yet'}
          className={cn(
            'hidden md:inline-flex size-9 items-center justify-center rounded-md',
            'border border-[var(--manara-mist)] bg-[var(--manara-white)] text-[var(--manara-ink-muted)]',
            'cursor-not-allowed hover:bg-[var(--manara-mist)] transition-colors',
          )}
        >
          <Bell className="size-4" />
        </button>

        {/* Language switcher */}
        <LanguageSwitcher />
      </div>
    </header>
  );
}
