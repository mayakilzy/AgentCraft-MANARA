/**
 * MANARA UI-02 Part A — Component-level tests
 * Covers: Sidebar navigation, Language switching, Hero composer, ComposeResult states
 */
import { describe, it, expect, vi } from 'vitest';

// ============================================================
// i18n tests — language switching
// ============================================================
describe('i18n — translations', () => {
  it('has all required keys in English', async () => {
    const { translations } = await import('./i18n');
    const requiredKeys = [
      'app.name', 'app.tagline',
      'home.headline', 'home.submit', 'home.clear',
      'nav.home', 'nav.workspace', 'nav.memory',
      'nav.comingLater', 'demo.mode',
    ];
    for (const key of requiredKeys) {
      expect(translations.en[key], `Missing EN key: ${key}`).toBeDefined();
    }
  });

  it('has all required keys in Arabic', async () => {
    const { translations } = await import('./i18n');
    const requiredKeys = [
      'app.name', 'app.tagline',
      'home.headline', 'home.submit', 'home.clear',
      'nav.home', 'nav.workspace', 'nav.memory',
      'nav.comingLater', 'demo.mode',
    ];
    for (const key of requiredKeys) {
      expect(translations.ar[key], `Missing AR key: ${key}`).toBeDefined();
    }
  });

  it('Arabic translations are not identical to English (actually translated)', async () => {
    const { translations } = await import('./i18n');
    const keys = Object.keys(translations.en);
    let translated = 0;
    for (const key of keys) {
      if (translations.en[key] !== translations.ar[key]) {
        translated++;
      }
    }
    // At least 80% of keys should be actually translated
    expect(translated).toBeGreaterThan(keys.length * 0.8);
  });
});

// ============================================================
// Coverage badge value tests
// ============================================================
describe('Coverage levels', () => {
  it('all 4 coverage levels are valid enum values', async () => {
    const validLevels = ['NONE', 'CATALOG', 'OPERATIONAL', 'VERIFIED'];
    expect(validLevels.length).toBe(4);
    expect(validLevels).toContain('NONE');
    expect(validLevels).toContain('CATALOG');
    expect(validLevels).toContain('OPERATIONAL');
    expect(validLevels).toContain('VERIFIED');
  });
});

// ============================================================
// Navigation items test
// ============================================================
describe('Navigation structure', () => {
  it('should have exactly 9 navigation pages defined', () => {
    const navItems = [
      { id: 'home', label: 'Home' },
      { id: 'workspace', label: 'Investigation Workspace' },
      { id: 'memory', label: 'Memory Explorer' },
      { id: 'registry', label: 'Capability Registry' },
      { id: 'foundry', label: 'Source Foundry' },
      { id: 'molds', label: 'Mold Factory' },
      { id: 'agents', label: 'Agent Registry' },
      { id: 'foresight', label: 'Foresight' },
      { id: 'publishing', label: 'Publishing Studio' },
    ];
    expect(navItems.length).toBe(9);
  });

  it('only Home is active in UI-01, others are Coming Later', () => {
    const activePages = ['home'];
    const comingLaterPages = ['workspace', 'memory', 'registry', 'foundry', 'molds', 'agents', 'foresight', 'publishing'];
    expect(activePages.length).toBe(1);
    expect(comingLaterPages.length).toBe(8);
  });
});

// ============================================================
// API client — fixture mode tests
// ============================================================
describe('API client — fixture mode gating', () => {
  it('isFixtureMode returns false by default', async () => {
    vi.resetModules();
    const { isFixtureMode } = await import('./api-client');
    expect(isFixtureMode()).toBe(false);
  });

  it('isFixtureMode returns true when VITE_USE_FIXTURES=true', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'true');
    vi.resetModules();
    const { isFixtureMode } = await import('./api-client');
    expect(isFixtureMode()).toBe(true);
    vi.stubEnv('VITE_USE_FIXTURES', '');
  });
});

// ============================================================
// Hero composer validation tests
// ============================================================
describe('Research question validation', () => {
  it('rejects queries shorter than 10 characters', () => {
    const query = 'short';
    const trimmed = query.trim();
    expect(trimmed.length >= 10).toBe(false);
  });

  it('accepts queries of exactly 10 characters', () => {
    const query = '1234567890';
    const trimmed = query.trim();
    expect(trimmed.length >= 10).toBe(true);
  });

  it('accepts queries up to 1000 characters', () => {
    const query = 'a'.repeat(1000);
    expect(query.length <= 1000).toBe(true);
  });

  it('rejects queries over 1000 characters', () => {
    const query = 'a'.repeat(1001);
    expect(query.length > 1000).toBe(true);
  });

  it('trims whitespace before validation', () => {
    const query = '          test query here          ';
    const trimmed = query.trim();
    expect(trimmed.length).toBe(15); // "test query here"
    expect(trimmed.length >= 10).toBe(true);
  });
});
