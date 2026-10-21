'use client';

import { Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage, type Language } from './i18n';

/* ============================================================
   LanguageSwitcher — EN / AR toggle in the header
   ============================================================ */

export function LanguageSwitcher({ className }: { className?: string }) {
  const { lang, setLang, t } = useLanguage();

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-md border bg-[var(--manara-white)] p-0.5',
        'border-[var(--manara-mist)] manara-shadow-soft',
        className,
      )}
      role="group"
      aria-label={t('header.language')}
    >
      <Globe
        className="mx-1 size-3.5 text-[var(--manara-ink-muted)]"
        aria-hidden
      />
      {(['en', 'ar'] as Language[]).map((l) => {
        const active = lang === l;
        return (
          <button
            key={l}
            type="button"
            onClick={() => setLang(l)}
            aria-pressed={active}
            aria-label={l === 'en' ? t('header.languageEn') : t('header.languageAr')}
            className={cn(
              'min-w-[34px] rounded-[5px] px-2 py-1 text-xs font-semibold transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)] focus-visible:ring-offset-1',
              active
                ? 'bg-[var(--manara-ink)] text-[var(--manara-canvas)]'
                : 'text-[var(--manara-ink-light)] hover:bg-[var(--manara-mist)]',
            )}
          >
            {l.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}
