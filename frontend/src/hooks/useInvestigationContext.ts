import { useState, useEffect, useCallback } from "react";

export interface InvestigationContext {
  query: string;
  moldResult: any | null;
  investigationId: string | null;
  moldId: string | null;
}

const STORAGE_KEY = "manara_investigation_context";

export function useInvestigationContext() {
  const [ctx, setCtx] = useState<InvestigationContext | null>(null);

  // Load from localStorage on mount (resume after refresh)
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setCtx(JSON.parse(stored));
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  // Persist to localStorage whenever ctx changes
  const updateCtx = useCallback((newCtx: InvestigationContext | null) => {
    setCtx(newCtx);
    if (newCtx) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newCtx));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const clearCtx = useCallback(() => {
    setCtx(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { ctx, updateCtx, clearCtx };
}
