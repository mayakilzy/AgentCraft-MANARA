'use client';

import * as React from 'react';
import {
  Home,
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

interface NavItem {
  key: NavKey;
  icon: React.ComponentType<{ className?: string }>;
  section: 'intelligence' | 'factory' | 'studio';
  active?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { key: 'home', icon: Home, section: 'intelligence', active: true },
  { key: 'workspace', icon: FlaskConical, section: 'intelligence' },
  { key: 'memory', icon: Database, section: 'intelligence' },
  { key: 'registry', icon: Layers, section: 'factory' },
  { key: 'foundry', icon: Factory, section: 'factory' },
  { key: 'molds', icon: Boxes, section: 'factory' },
  { key: 'agents', icon: Bot, section: 'factory' },
  { key: 'foresight', icon: TrendingUp, section: 'studio' },
  { key: 'publishing', icon: BookOpenText, section: 'studio' },
];

const SECTION_ORDER: Array<'intelligence' | 'factory' | 'studio'> = [
  'intelligence',
  'factory',
  'studio',
];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  /** Mobile drawer open state */
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  collapsed,
  onToggleCollapsed,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const { t, dir } = useLanguage();

  const content = (
    <div
      className={cn(
        'flex h-full flex-col bg-[var(--manara-ink)] text-[var(--manara-canvas)]',
        'transition-[width] duration-200 ease-out',
      )}
      style={{ width: collapsed ? 64 : 240 }}
    >
      {/* Logo + wordmark */}
      <div
        className={cn(
          'flex h-16 items-center gap-3 border-b border-white/5 px-4',
          collapsed && 'justify-center px-0',
        )}
      >
        <LighthouseLogo size={28} variant="canvas" withBeam />
        {!collapsed && (
          <div className="flex flex-col leading-tight">
            <span className="font-serif text-[15px] font-semibold tracking-[0.04em] text-[var(--manara-canvas)]">
              {t('app.name')}
            </span>
            <span className="font-ui text-[10px] uppercase tracking-[0.16em] text-[var(--manara-canvas)]/55">
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
            <div key={section} className={cn(idx > 0 && 'mt-5')}>
              {!collapsed && (
                <div className="mb-1.5 px-3 font-ui text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--manara-canvas)]/40">
                  {t(`nav.section.${section}`)}
                </div>
              )}
              <ul className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const isActive = !!item.active;
                  const isLocked = !isActive;
                  return (
                    <li key={item.key}>
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          if (isActive) {
                            onCloseMobile();
                          }
                        }}
                        aria-current={isActive ? 'page' : undefined}
                        title={collapsed ? t(`nav.${item.key}`) : undefined}
                        className={cn(
                          'group relative flex items-center gap-3 rounded-md px-3 py-2 font-ui text-[13px] transition-colors',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--manara-teal)]',
                          collapsed && 'justify-center px-0',
                          isActive
                            ? 'bg-[var(--manara-teal)]/20 text-[var(--manara-canvas)]'
                            : 'text-[var(--manara-canvas)]/65 hover:bg-white/5 hover:text-[var(--manara-canvas)]/90',
                        )}
                      >
                        {isActive && (
                          <span
                            aria-hidden
                            className="absolute top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-full bg-[var(--manara-brass)]"
                            style={dir === 'rtl' ? { right: 0 } : { left: 0 }}
                          />
                        )}
                        <Icon className="size-[18px] shrink-0" />
                        {!collapsed && (
                          <span className="flex-1 truncate">{t(`nav.${item.key}`)}</span>
                        )}
                        {!collapsed && isLocked && (
                          <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-ui text-[9.5px] font-medium uppercase tracking-[0.08em] text-[var(--manara-canvas)]/40 border border-white/10">
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

      {/* Footer — demo mode */}
      <div
        className={cn(
          'border-t border-white/5 px-4 py-3',
          collapsed && 'px-2',
        )}
      >
        {collapsed ? (
          <div className="flex justify-center" title={t('demo.mode')}>
            <span className="size-1.5 rounded-full bg-[var(--manara-brass)]" />
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            <Pill
              variant="brass"
              className="w-fit border-white/15 bg-white/5 text-[var(--manara-brass)]"
            >
              <span className="size-1.5 rounded-full bg-[var(--manara-brass)]" />
              {t('demo.mode')}
            </Pill>
            <span className="font-mono text-[10px] text-[var(--manara-canvas)]/40">
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
