'use client';

import { Menu } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';
import { LanguageSwitcher } from './LanguageSwitcher';
import { StatusBadge } from './Badges';

/* ============================================================
   Header — top bar with page title, status, language switcher
   ============================================================ */

interface HeaderProps {
  onOpenMobileNav: () => void;
  status: 'online' | 'offline' | 'checking';
  title: string;
  subtitle?: string;
}

export function Header({
  onOpenMobileNav,
  status,
  title,
  subtitle,
}: HeaderProps) {
  const { t } = useLanguage();
  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-[var(--manara-mist)]',
        'bg-[var(--manara-canvas)]/85 px-4 backdrop-blur-md md:px-8',
      )}
    >
      {/* Mobile hamburger */}
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

      {/* Page title */}
      <div className="flex-1 min-w-0">
        <h1 className="font-serif text-[18px] font-semibold leading-tight text-[var(--manara-ink)] truncate">
          {title}
        </h1>
        {subtitle && (
          <p className="font-ui text-[11.5px] text-[var(--manara-ink-muted)] truncate">
            {subtitle}
          </p>
        )}
      </div>

      {/* Status (hidden on very small screens) */}
      <div className="hidden sm:block">
        <StatusBadge status={status} />
      </div>

      {/* Language switcher */}
      <LanguageSwitcher />
    </header>
  );
}
