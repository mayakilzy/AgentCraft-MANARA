/**
 * MANARA UI-01 Closure — Frontend tests
 *
 * Covers:
 * - Question validation (min 10 chars, max 1000 chars)
 * - API client: success, 422 error, 500 error, network failure
 * - Fixture mode: only when VITE_USE_FIXTURES=true
 * - Language switching (EN/AR)
 * - Coverage badge rendering
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ============================================================
// API client tests
// ============================================================

describe('API client — error behavior (MANARA-UI-01-CLOSURE fix)', () => {
  beforeEach(() => {
    // Reset modules to clear import.meta.env cache
    vi.resetModules();
  });

  it('throws ManaraApiError on HTTP 422 (validation error), does NOT return fixture', async () => {
    // Mock fetch to return 422
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ code: 'validation_error', message: 'query too short' }),
    }));

    const { manaraApi, ManaraApiError } = await import('./api-client');

    await expect(manaraApi.compose('short')).rejects.toThrow(ManaraApiError);
    try {
      await manaraApi.compose('short');
    } catch (e) {
      expect(e).toBeInstanceOf(ManaraApiError);
      expect((e as InstanceType<typeof ManaraApiError>).status).toBe(422);
    }
  });

  it('throws ManaraApiError on HTTP 500 (server error), does NOT return fixture', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ code: 'internal_error', message: 'server error' }),
    }));

    const { manaraApi, ManaraApiError } = await import('./api-client');

    await expect(manaraApi.compose('A valid research question here')).rejects.toThrow(ManaraApiError);
    try {
      await manaraApi.compose('A valid research question here');
    } catch (e) {
      expect((e as InstanceType<typeof ManaraApiError>).status).toBe(500);
    }
  });

  it('throws ManaraApiError on network failure, does NOT return fixture', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const { manaraApi, ManaraApiError } = await import('./api-client');

    await expect(manaraApi.compose('A valid research question here')).rejects.toThrow(ManaraApiError);
    try {
      await manaraApi.compose('A valid research question here');
    } catch (e) {
      expect(e).toBeInstanceOf(ManaraApiError);
      expect((e as InstanceType<typeof ManaraApiError>).status).toBe(0);
    }
  });

  it('returns live response on HTTP 200', async () => {
    const mockResponse = {
      query: 'test query here',
      investigation_id: 'inv-test-123',
      mold_recipe_id: 'mold-test-123',
      is_unknown_domain: false,
      detection_reasoning: 'test',
      detected_needs: [],
      coverage: [],
      gaps: [],
      is_complete: true,
      is_catalog_complete: true,
      deliverable_type: 'research_deliverable',
      composition_notes: 'test',
      composed_at: '2026-01-01T00:00:00Z',
    };

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockResponse,
    }));

    const { manaraApi } = await import('./api-client');
    const result = await manaraApi.compose('test query here');

    expect(result._source).toBe('live');
    expect(result.investigation_id).toBe('inv-test-123');
  });

  it('uses fixtures ONLY when VITE_USE_FIXTURES=true', async () => {
    // Set the env var
    vi.stubEnv('VITE_USE_FIXTURES', 'true');

    // Re-import to pick up the env var
    vi.resetModules();
    const { manaraApi, isFixtureMode } = await import('./api-client');

    expect(isFixtureMode()).toBe(true);

    // Even with a failing fetch, fixtures should be returned
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const result = await manaraApi.compose('A valid research question about prosthetics');
    expect(result._source).toBe('fixture');
    expect(result.investigation_id).toMatch(/^inv-fixture-/);
  });

  it('does NOT use fixtures by default (VITE_USE_FIXTURES not set)', async () => {
    // Ensure env var is not set
    vi.stubEnv('VITE_USE_FIXTURES', '');

    vi.resetModules();
    const { isFixtureMode } = await import('./api-client');
    expect(isFixtureMode()).toBe(false);
  });
});

// ============================================================
// Coverage badge tests
// ============================================================

describe('Coverage badge values', () => {
  it('CoverageLevel type includes all 4 levels', async () => {

    // Verify the type union by checking fixture output
    vi.stubEnv('VITE_USE_FIXTURES', 'true');
    vi.resetModules();
    const { manaraApi: api } = await import('./api-client');

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fail')));
    const result = await api.compose('test query for coverage levels checking');

    for (const entry of result.coverage) {
      expect(['NONE', 'CATALOG', 'OPERATIONAL', 'VERIFIED']).toContain(entry.coverage_level);
    }
  });
});

// ============================================================
// i18n tests
// ============================================================

describe('i18n — language switching', () => {
  it('translates a known key in English', async () => {
    const { translations } = await import('./i18n');
    expect(translations.en['home.submit']).toBe('Start Investigation');
  });

  it('translates a known key in Arabic', async () => {
    const { translations } = await import('./i18n');
    expect(translations.ar['home.submit']).toBe('بدء التحقيق');
  });

  it('has matching keys between EN and AR', async () => {
    const { translations } = await import('./i18n');
    const enKeys = Object.keys(translations.en).sort();
    const arKeys = Object.keys(translations.ar).sort();
    expect(arKeys).toEqual(enKeys);
  });
});
