import { useState, useEffect } from "react";
import type { InvestigationContext } from "../hooks/useInvestigationContext";

interface WorkspaceProps {
  ctx: InvestigationContext | null;
  onClear: () => void;
}

export function InvestigationWorkspace({ ctx, onClear }: WorkspaceProps) {
  const [publications, setPublications] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);

  // Load publications when context changes
  useEffect(() => {
    if (!ctx?.moldResult) return;
    setLoading(true);
    // Fetch publications for this investigation
    if (ctx.investigationId) {
      fetch(`/publishing/publications`)
        .then((r) => r.ok ? r.json() : [])
        .then((data: any[]) => {
          setPublications(data.filter((p) => p.investigation_id === ctx.investigationId));
        })
        .catch(() => setPublications([]));
    }
    setLoading(false);
  }, [ctx?.moldResult, ctx?.investigationId]);

  // Actions: create investigation, advance workflow, create publication
  async function doAction(name: string, url: string, body?: any) {
    setAction(name);
    try {
      const r = await fetch(url, {
        method: body ? "POST" : "GET",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail?.message || JSON.stringify(data.detail) || `HTTP ${r.status}`);
      return data;
    } finally {
      setAction(null);
    }
  }

  if (!ctx?.moldResult) {
    return (
      <section className="panel">
        <h3 className="panel__title">مساحة التحقيق · Investigation Workspace</h3>
        <div className="warning-box">
          لا يوجد تحقيق نشط. ابدأ بحثاً جديداً من القسم الرئيسي (الرئيسية).
          <br />
          No active investigation. Start a new one from the Home tab.
        </div>
      </section>
    );
  }

  const result = ctx.moldResult;

  return (
    <section className="panel">
      <h3 className="panel__title">
        مساحة التحقيق · Investigation Workspace
        <button onClick={onClear} className="action-btn" style={{ marginRight: 8, fontSize: 11 }}>
          ✗ إغلاق · Clear
        </button>
      </h3>

      {/* Investigation Summary */}
      <div className="kv">
        <div className="kv__key">السؤال · Query</div>
        <div className="kv__value">{ctx.query}</div>
        <div className="kv__key">القالب · Mold</div>
        <div className="kv__value" style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
          {result.mold_recipe_id}
        </div>
        <div className="kv__key">مكتمل؟ · Complete</div>
        <div className="kv__value">
          {result.is_complete ? "✓ مكتمل (تغطية تشغيلية)" : "✗ غير مكتمل (فجوات تشغيلية)"}
        </div>
        <div className="kv__key">نوع المخرج · Deliverable</div>
        <div className="kv__value">
          <span className="badge" style={{
            background: "transparent",
            border: `1px solid ${result.deliverable_type === "research_deliverable" ? "var(--accent)" : "var(--accent-warm)"}`,
            color: result.deliverable_type === "research_deliverable" ? "var(--accent)" : "var(--accent-warm)",
            fontSize: 10,
          }}>
            {result.deliverable_type}
          </span>
        </div>
      </div>

      {/* Detected Needs */}
      {result.detected_needs?.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", margin: "0 0 6px" }}>
            الاحتياجات المكتشفة · Detected Needs ({result.detected_needs.length})
          </h5>
          <ul className="list" style={{ fontSize: 12 }}>
            {result.detected_needs.map((n: any, i: number) => (
              <li key={i}>
                {n.need} <span style={{ color: "var(--text-muted)" }}>(relevance={n.relevance?.toFixed(2) || "?"})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Coverage */}
      {result.coverage?.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", margin: "0 0 6px" }}>
            التغطية · Coverage ({result.coverage.length})
          </h5>
          <ul className="list" style={{ fontSize: 12 }}>
            {result.coverage.map((c: any, i: number) => (
              <li key={i}>
                {c.need} → {c.selected_capability_id || "—"}
                <span className="badge" style={{
                  fontSize: 9, marginRight: 4, background: "transparent",
                  border: `1px solid ${c.coverage_level === "operational" ? "var(--accent)" : "var(--accent-warm)"}`,
                  color: c.coverage_level === "operational" ? "var(--accent)" : "var(--accent-warm)",
                }}>
                  {c.coverage_level}
                </span>
                {c.operational_gap_recorded && (
                  <span style={{ color: "var(--danger)", fontSize: 11 }}> ⚠ فجوة تشغيلية</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Gaps */}
      {result.gaps?.length > 0 && (
        <div className="warning-box" style={{ marginTop: 12, fontSize: 12 }}>
          <strong>الفجوات المكتشفة · Gaps ({result.gaps.length}):</strong>
          <ul style={{ margin: "6px 0 0", paddingRight: 18 }}>
            {result.gaps.map((g: any, i: number) => (
              <li key={i}>
                {g.need} → <span className="badge badge--danger" style={{ fontSize: 9 }}>{g.foundry_resolution}</span>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>{g.resolution_notes?.slice(0, 120)}...</div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border)", display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          className="action-btn"
          disabled={!!action}
          onClick={async () => {
            try {
              const pub = await doAction(
                "create_dossier",
                "/publishing/publications",
                {
                  investigation_id: ctx.investigationId || "inv-session",
                  output_type: "research_dossier",
                  title: `Research Dossier: ${ctx.query.slice(0, 60)}`,
                  scope: { topic: ctx.query },
                }
              );
              setPublications((prev) => [...prev, pub]);
            } catch (e) {
              alert(e instanceof Error ? e.message : String(e));
            }
          }}
        >
          {action === "create_dossier" ? "..." : "📄 إنشاء تقرير · Create Dossier"}
        </button>
        <button
          className="action-btn"
          disabled={!!action}
          onClick={async () => {
            try {
              const pub = await doAction(
                "create_presenter",
                "/publishing/publications",
                {
                  investigation_id: ctx.investigationId || "inv-session",
                  output_type: "presenter_edition",
                  title: `Presenter Script: ${ctx.query.slice(0, 60)}`,
                  scope: { topic: ctx.query },
                }
              );
              setPublications((prev) => [...prev, pub]);
            } catch (e) {
              alert(e instanceof Error ? e.message : String(e));
            }
          }}
        >
          {action === "create_presenter" ? "..." : "🎤 نص المقدم · Presenter Edition"}
        </button>
        <button
          className="action-btn"
          disabled={!!action}
          onClick={async () => {
            try {
              const pub = await doAction(
                "create_storyboard",
                "/publishing/publications",
                {
                  investigation_id: ctx.investigationId || "inv-session",
                  output_type: "visual_storyboard",
                  title: `Storyboard: ${ctx.query.slice(0, 60)}`,
                  scope: { topic: ctx.query },
                }
              );
              setPublications((prev) => [...prev, pub]);
            } catch (e) {
              alert(e instanceof Error ? e.message : String(e));
            }
          }}
        >
          {action === "create_storyboard" ? "..." : "🎬 مخطط المشاهد · Storyboard"}
        </button>
      </div>

      {/* Publications */}
      {publications.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", margin: "0 0 6px" }}>
            المنشورات · Publications ({publications.length})
          </h5>
          {publications.map((p: any) => (
            <div key={p.publication_id || p.id} className="capability-card">
              <h4 style={{ fontSize: 14 }}>{p.title || p.output_type}</h4>
              <div className="capability-card__id">{p.publication_id || p.id}</div>
              <div className="kv" style={{ marginTop: 8 }}>
                <div className="kv__key">النوع</div>
                <div className="kv__value">{p.output_type}</div>
                <div className="kv__key">بوابة الجودة</div>
                <div className="kv__value">
                  <span className="badge" style={{
                    background: "transparent",
                    border: `1px solid ${p.quality_gate_passed ? "var(--accent)" : "var(--danger)"}`,
                    color: p.quality_gate_passed ? "var(--accent)" : "var(--danger)",
                    fontSize: 10,
                  }}>
                    {p.quality_gate_passed ? "PASSED" : "FAILED"}
                  </span>
                </div>
                <div className="kv__key">قابل للتنزيل</div>
                <div className="kv__value">{p.downloadable ? "✓" : "✗"}</div>
              </div>
              {p.downloadable && p.publication_id && (
                <div style={{ marginTop: 8, display: "flex", gap: 4 }}>
                  <a href={`/publishing/publications/${p.publication_id}/download?format=markdown`} className="action-btn" style={{ textDecoration: "none", fontSize: 11 }}>
                    ↓ Markdown
                  </a>
                  <a href={`/publishing/publications/${p.publication_id}/download?format=json`} className="action-btn" style={{ textDecoration: "none", fontSize: 11 }}>
                    ↓ JSON
                  </a>
                  <a href={`/publishing/publications/${p.publication_id}/download?format=text`} className="action-btn" style={{ textDecoration: "none", fontSize: 11 }}>
                    ↓ Text
                  </a>
                </div>
              )}
              {p.quality_gate_issues?.length > 0 && (
                <div className="warning-box" style={{ marginTop: 8, fontSize: 11 }}>
                  <strong>مشاكل بوابة الجودة:</strong>
                  <ul style={{ margin: "4px 0 0", paddingRight: 18 }}>
                    {p.quality_gate_issues.map((issue: string, i: number) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {loading && <div className="loading" style={{ marginTop: 8 }}>جارٍ التحميل…</div>}
    </section>
  );
}
