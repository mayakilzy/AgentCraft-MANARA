'use client';

import * as React from 'react';
import {
  Home as HomeIcon,
  FlaskConical,
  Database,
  Layers,
  Factory,
  Boxes,
  Bot,
  TrendingUp,
  BookOpenText,
  Lock,
  ChevronLeft,
  ChevronRight,
  X,
  Telescope,
  HelpCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLanguage } from './i18n';
import { LighthouseLogo } from './Lighthouse';
import { Pill } from './Badges';

/* ============================================================
   Sidebar — fixed left (LTR) / right (RTL) navigation
   - Desktop ≥1024px : expanded 240px, collapsible to 64px
   - Tablet 768-1023 : collapsed 64px, expandable
   - Mobile  <768    : hidden, opens as slide-out drawer

   MANARA-UI-PAGE01-RTL-VISUAL-CLOSURE-01: reconciled with approved
   HTML reference. Section names + per-nav-item subtitles + Intelligence
   Observatory teaser + Help link match the approved composition.
   ============================================================ */

type NavKey =
  | 'home'
  | 'workspace'
  | 'memory'
  | 'registry'
  | 'foundry'
  | 'molds'
  | 'agents'
  | 'foresight'
  | 'publishing';

// Per approved reference: 3 sections (Exploration / Knowledge & Analysis / Factory Management)
// Per approved reference: each nav item has a subtitle
type NavSection = 'exploration' | 'knowledge' | 'factory';

interface NavItem {
  key: NavKey;
  icon: React.ComponentType<{ className?: string }>;
  section: NavSection;
  // Subtitle shown under the nav item label (per approved reference)
  subtitle_en: string;
  subtitle_ar: string;
  active?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  // EXPLORATION
  { key: 'home', icon: HomeIcon, section: 'exploration', active: true,
    subtitle_en: 'Start a new investigation', subtitle_ar: 'ابدأ تحقيقاً جديداً' },
  { key: 'workspace', icon: FlaskConical, section: 'exploration',
    subtitle_en: 'Live research workspace', subtitle_ar: 'مساحة بحث حية' },
  // KNOWLEDGE & ANALYSIS
  { key: 'memory', icon: Database, section: 'knowledge',
    subtitle_en: 'Evidence & knowledge', subtitle_ar: 'أدلة ومعرفة' },
  { key: 'foresight', icon: TrendingUp, section: 'knowledge',
    subtitle_en: 'Trends & future outlooks', subtitle_ar: 'اتجاهات وتوقعات مستقبلية' },
  { key: 'publishing', icon: BookOpenText, section: 'knowledge',
    subtitle_en: 'Research reports', subtitle_ar: 'تقارير بحثية' },
  // FACTORY MANAGEMENT
  { key: 'registry', icon: Layers, section: 'factory',
    subtitle_en: 'Available tools & skills', subtitle_ar: 'أدوات ومهارات متاحة' },
  { key: 'foundry', icon: Factory, section: 'factory',
    subtitle_en: 'Research data sources', subtitle_ar: 'مصادر بيانات البحث' },
  { key: 'molds', icon: Boxes, section: 'factory',
    subtitle_en: 'Research templates', subtitle_ar: 'قوالب بحثية' },
  { key: 'agents', icon: Bot, section: 'factory',
    subtitle_en: 'Agents & execution logs', subtitle_ar: 'وكلاء وسجلات التنفيذ' },
];

const SECTION_ORDER: Array<NavSection> = ['exploration', 'knowledge', 'factory'];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  /** Mobile drawer open state */
  mobileOpen: boolean;
  onCloseMobile: () => void;
  activePage?: string;
  onNavigate?: (page: 'home' | 'workspace' | 'memory') => void;
  workspaceEnabled?: boolean;
}

export function Sidebar({
  collapsed,
  onToggleCollapsed,
  mobileOpen,
  onCloseMobile,
  activePage,
  onNavigate,
  workspaceEnabled,
}: SidebarProps) {
  const { t, dir } = useLanguage();
  const isAr = dir === 'rtl';

  const content = (
    <div
      className={cn(
        // MANARA-UI-VISUAL-FIDELITY-01 Decision 04: LIGHT sidebar per approved designs
        // + OPEN-03: Modern Knowledge Studio (light) default
        'flex h-full flex-col bg-[var(--manara-white)] text-[var(--manara-ink)]',
        'border-e border-[var(--manara-mist)]',
        'transition-[width] duration-200 ease-out',
      )}
      style={{ width: collapsed ? 64 : 260 }}
    >
      {/* Logo + wordmark */}
      <div
        className={cn(
          'flex h-16 items-center gap-3 border-b border-[var(--manara-mist)] px-4',
          collapsed && 'justify-center px-0',
        )}
      >
        <LighthouseLogo size={28} variant="ink" withBeam />
        {!collapsed && (
          <div className="flex flex-col leading-tight">
            <span className="font-serif text-[16px] font-semibold tracking-[0.04em] text-[var(--manara-ink)]">
              {t('app.name')}
            </span>
            <span className="font-ui text-[10px] uppercase tracking-[0.18em] text-[var(--manara-ink-muted)]">
              {t('app.shortTagline')}
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav
        aria-label="Primary"
        className={cn(
          'manara-scroll flex-1 overflow-y-auto px-3 py-4',
          collapsed && 'px-2',
        )}
      >
        {SECTION_ORDER.map((section, idx) => {
          const items = NAV_ITEMS.filter((n) => n.section === section);
          return (
            <div key={section} className={cn(idx > 0 && 'mt-6')}>
              {!collapsed && (
                <div className="mb-2 px-3 font-ui text-[10px] font-semibold uppercase tracking-[0.20em] text-[var(--manara-ink-muted)]">
                  {t(`nav.section.${section}`)}
                </div>
              )}
              <ul className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const isClickable = item.key === 'home' || (workspaceEnabled && (item.key === 'workspace' || item.key === 'memory'));
                  const isActive = activePage === item.key;
                  const isLocked = !isClickable;
                  return (
                    <li key={item.key}>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (isClickable && onNavigate && (item.key === 'home' || item.key === 'workspace' || item.key === 'memory')) {
                            onNavigate(item.key);
                          }
                          onCloseMobile();
                        }}
                        aria-current={isActive ? 'page' : undefined}
                        title={collapsed ? t(`nav.${item.key}`) : undefined}
                        className={cn(
                          'group relative flex items-center gap-3 rounded-md px-3 py-2 transition-colors',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
                          collapsed && 'justify-center px-0',
                          isActive
                            ? 'bg-[var(--manara-teal)]/10 text-[var(--manara-ink)]'
                            : 'text-[var(--manara-ink-light)] hover:bg-[var(--manara-mist)] hover:text-[var(--manara-ink)]',
                        )}
                      >
                        {isActive && (
                          <span
                            aria-hidden
                            className="absolute top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-full bg-[var(--manara-teal)]"
                            style={dir === 'rtl' ? { right: 0 } : { left: 0 }}
                          />
                        )}
                        <Icon className={cn('size-[18px] shrink-0', isActive && 'text-[var(--manara-teal)]')} />
                        {!collapsed && (
                          <span className="flex-1 min-w-0 flex flex-col leading-tight">
                            <span className="font-ui text-[13px] font-medium truncate">{t(`nav.${item.key}`)}</span>
                            <span className="font-ui text-[10px] text-[var(--manara-ink-muted)] truncate">
                              {isAr ? item.subtitle_ar : item.subtitle_en}
                            </span>
                          </span>
                        )}
                        {!collapsed && isLocked && (
                          <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-ui text-[9.5px] font-medium uppercase tracking-[0.08em] text-[var(--manara-ink-muted)] border border-[var(--manara-mist)] bg-[var(--manara-mist)]/40">
                            <Lock className="size-2.5" />
                            {t('nav.comingLater')}
                          </span>
                        )}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* Footer — Intelligence Observatory teaser + Help link (per approved reference) */}
      <div
        className={cn(
          'border-t border-[var(--manara-mist)] px-3 py-3',
          collapsed && 'px-2',
        )}
      >
        {collapsed ? (
          <div className="flex flex-col items-center gap-2">
            <div title="Intelligence Observatory" className="flex size-8 items-center justify-center rounded-md"
              style={{ background: 'radial-gradient(circle at 50% 52%, #44abb6, #053049 36%, #061a2b 70%)', color: '#ade7f2' }}>
              <Telescope className="size-4" />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Observatory teaser card */}
            <div className="flex items-center gap-2.5 rounded-md border border-[var(--manara-mist)] bg-white p-2">
              <div
                aria-hidden
                className="flex size-9 items-center justify-center rounded-md shrink-0"
                style={{ background: 'radial-gradient(circle at 50% 52%, #44abb6, #053049 36%, #061a2b 70%)', color: '#ade7f2' }}
              >
                <Telescope className="size-4" />
              </div>
              <div className="flex flex-col leading-tight min-w-0">
                <span className="font-serif text-[12px] font-semibold text-[var(--manara-ink)] truncate">
                  {isAr ? 'مرصد المعلومات' : 'Intelligence Observatory'}
                </span>
                <span className="font-ui text-[10px] text-[var(--manara-ink-muted)] truncate">
                  {isAr ? 'عروض تحليلية معمقة' : 'Deep analytical views'}
                </span>
              </div>
            </div>
            {/* Help link */}
            <a href="#" onClick={(e) => e.preventDefault()} className="flex items-center gap-1.5 font-ui text-[11px] text-[var(--manara-ink-light)] hover:text-[var(--manara-teal)] transition-colors">
              <HelpCircle className="size-3" />
              {isAr ? 'المساعدة والتوثيق' : 'Help & Documentation'}
            </a>
            {/* Demo mode pill (preserved per OPEN-04) */}
            <Pill
              variant="brass"
              className="w-fit border-[var(--manara-mist)] bg-[var(--manara-mist)]/40 text-[var(--manara-brass)]"
            >
              <span className="size-1.5 rounded-full bg-[var(--manara-brass)]" />
              {t('demo.mode')}
            </Pill>
            <span className="font-mono text-[10px] text-[var(--manara-ink-muted)]">
              {t('demo.version')}
            </span>
          </div>
        )}
      </div>

      {/* Collapse toggle (desktop only — hidden on tablet/mobile) */}
      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? t('header.expandSidebar') : t('header.collapseSidebar')}
        className={cn(
          'absolute top-20 z-30 hidden lg:flex size-6 items-center justify-center rounded-full',
          'border border-[var(--manara-mist)] bg-[var(--manara-white)] text-[var(--manara-ink-light)]',
          'manara-shadow-soft hover:text-[var(--manara-ink)] hover:border-[var(--manara-teal)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
        )}
        style={
          dir === 'rtl'
            ? { left: collapsed ? 6 : -12 }
            : { right: collapsed ? 6 : -12 }
        }
      >
        {dir === 'rtl' ? (
          collapsed ? <ChevronLeft className="size-3.5" /> : <ChevronRight className="size-3.5" />
        ) : (
          collapsed ? <ChevronRight className="size-3.5" /> : <ChevronLeft className="size-3.5" />
        )}
      </button>
    </div>
  );

  return (
    <>
      {/* Desktop / Tablet persistent sidebar */}
      <aside
        className={cn(
          'relative hidden md:block shrink-0 z-20',
        )}
        aria-label="Sidebar"
      >
        {content}
      </aside>

      {/* Mobile drawer */}
      <div
        className={cn(
          'md:hidden fixed inset-0 z-50 transition-opacity',
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden={!mobileOpen}
      >
        {/* Backdrop */}
        <div
          className={cn(
            'absolute inset-0 bg-[var(--manara-ink)]/40 backdrop-blur-[2px] transition-opacity',
            mobileOpen ? 'opacity-100' : 'opacity-0',
          )}
          onClick={onCloseMobile}
        />
        {/* Drawer — slides in from inline-start */}
        <div
          className={cn(
            'absolute top-0 h-full transition-transform duration-200 ease-out',
            dir === 'rtl' ? 'right-0' : 'left-0',
          )}
          style={{
            transform: mobileOpen
              ? 'translateX(0)'
              : dir === 'rtl'
                ? 'translateX(100%)'
                : 'translateX(-100%)',
          }}
        >
          <div className="relative h-full">
            {content}
            <button
              type="button"
              onClick={onCloseMobile}
              aria-label={t('header.closeMenu')}
              className="absolute top-4 z-10 size-8 flex items-center justify-center rounded-md border border-white/10 bg-white/5 text-[var(--manara-canvas)] hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]"
              style={dir === 'rtl' ? { left: 8 } : { right: 8 }}
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
