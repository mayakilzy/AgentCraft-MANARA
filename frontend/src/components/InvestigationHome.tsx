import { useState } from "react";

export function InvestigationHome({ onSubmitted }: { onSubmitted: (query: string) => void }) {
  const [query, setQuery] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!query.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      // 1. Compose a mold for the query
      const r = await fetch("/mold-factory/compose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail?.message || body.detail || "Composition failed");
      setResult(body);
      onSubmitted(query);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <h3 className="panel__title">
        <span className="badge badge--ok">G08</span>
        طرح سؤال بحثي جديد · Submit New Investigation
      </h3>
      <div className="warning-box">
        أدخل سؤالك بلغة طبيعية (عربية أو إنجليزية). سيقوم منارة بتحليل احتياجاتك
        واكتشاف القدرات المتاحة والفجوات.
      </div>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="مثال: مستقبل تقنيات إعادة تدوير النفايات خلال السنوات العشر القادمة"
        style={{
          width: "100%",
          minHeight: 80,
          padding: "12px",
          background: "var(--panel-2)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: 14,
          resize: "vertical",
        }}
      />
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button onClick={handleSubmit} disabled={submitting} className="action-btn">
          {submitting ? "...جارٍ التحليل" : "حلّل وابني القالب · Compose Mold"}
        </button>
      </div>
      {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      {result && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ margin: "0 0 8px" }}>نتيجة التحليل · Analysis Result</h4>
          <div className="kv">
            <div className="kv__key">مجال جديد؟</div>
            <div className="kv__value">{result.is_unknown_domain ? "نعم ✓" : "لا (قالب موجود)"}</div>
            <div className="kv__key">القالب</div>
            <div className="kv__value" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
              {result.mold_recipe_id}
            </div>
            <div className="kv__key">مكتمل؟</div>
            <div className="kv__value">
              {result.is_complete ? "✓ مكتمل (تغطية تشغيلية)" : "✗ غير مكتمل (فجوات تشغيلية)"}
            </div>
            <div className="kv__key">نوع المخرج</div>
            <div className="kv__value">{result.deliverable_type}</div>
          </div>
          {result.detected_needs?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase" }}>
                الاحتياجات المكتشفة ({result.detected_needs.length})
              </h5>
              <ul className="list" style={{ fontSize: 12 }}>
                {result.detected_needs.map((n: any, i: number) => (
                  <li key={i}>
                    {n.need} (relevance={n.relevance?.toFixed(2) || "?"})
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.coverage?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase" }}>
                التغطية ({result.coverage.length})
              </h5>
              <ul className="list" style={{ fontSize: 12 }}>
                {result.coverage.map((c: any, i: number) => (
                  <li key={i}>
                    {c.need} → {c.selected_capability_id || "—"}
                    <span className="badge" style={{ fontSize: 9, marginRight: 4, background: "transparent", border: `1px solid ${c.coverage_level === "operational" ? "var(--accent)" : "var(--accent-warm)"}`, color: c.coverage_level === "operational" ? "var(--accent)" : "var(--accent-warm)" }}>
                      {c.coverage_level}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.gaps?.length > 0 && (
            <div className="warning-box" style={{ marginTop: 12, fontSize: 12 }}>
              <strong>الفجوات المكتشفة ({result.gaps.length}):</strong>
              <ul style={{ margin: "6px 0 0", paddingRight: 18 }}>
                {result.gaps.map((g: any, i: number) => (
                  <li key={i}>
                    {g.need} → <span className="badge badge--danger" style={{ fontSize: 9 }}>{g.foundry_resolution}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
