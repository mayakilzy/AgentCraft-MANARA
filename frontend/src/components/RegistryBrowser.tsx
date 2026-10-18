import { useEffect, useMemo, useState } from "react";
import {
  manaraApi,
  type RegistrySearchHit,
  type SearchCapability,
} from "../api/client";

interface CapabilityListEntry {
  id: string;
  display_name: string;
  status: string;
  domains: string[];
  tags: string[];
}

const STATUS_COLORS: Record<string, string> = {
  discovered: "#8a94a4",
  assessed: "#8a94a4",
  candidate: "#d19a66",
  sandbox_tested: "#d19a66",
  review_pending: "#d19a66",
  approved: "#4ec9b0",
  rejected: "#d46767",
  quarantined: "#d46767",
  degraded: "#d46767",
  retired: "#8a94a4",
};

const STATUS_LABEL_AR: Record<string, string> = {
  discovered: "مُكتشَف",
  assessed: "مُقيَّم",
  candidate: "مُرشَّح",
  sandbox_tested: "مُختبَر في الصندوق",
  review_pending: "بانتظار المراجعة",
  approved: "مُعتمَد",
  rejected: "مرفوض",
  quarantined: "مُحجَر عليه",
  degraded: "متدهور",
  retired: "متقاعد",
};

export function RegistryBrowser() {
  const [capabilities, setCapabilities] = useState<CapabilityListEntry[]>([]);
  const [selected, setSelected] = useState<SearchCapability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seeded, setSeeded] = useState(false);
  const [domainFilter, setDomainFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Search state
  const [query, setQuery] = useState(
    "Future of intelligent prosthetics and neural interfaces through 2035",
  );
  const [searchResult, setSearchResult] = useState<RegistrySearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [stageTraces, setStageTraces] = useState<
    { stage: string; candidates_in: number; candidates_out: number; notes: string }[]
  >([]);
  const [gaps, setGaps] = useState<string[]>([]);

  const allDomains = useMemo(() => {
    const set = new Set<string>();
    capabilities.forEach((c) => c.domains.forEach((d) => set.add(d)));
    return Array.from(set).sort();
  }, [capabilities]);

  async function loadList() {
    setLoading(true);
    setError(null);
    try {
      const params: Parameters<typeof manaraApi.listCapabilities>[0] = { limit: 50 };
      if (domainFilter) params.domains = [domainFilter];
      if (statusFilter) params.statuses = [statusFilter];
      const r = await manaraApi.listCapabilities(params);
      setCapabilities(
        r.capabilities.map((c) => ({
          id: c.id,
          display_name: c.display_name,
          status: c.status,
          domains: c.domains,
          tags: c.tags,
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleSeed() {
    setLoading(true);
    setError(null);
    try {
      const r = await manaraApi.seedCapabilities();
      setSeeded(true);
      await loadList();
      alert(
        `تم إنشاء ${r.total_created} بطاقة جديدة.\nالمُضافة: ${r.seeded.join(", ")}\nالمتخطاة: ${r.skipped.join(", ")}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(id: string) {
    setLoading(true);
    setError(null);
    try {
      const cap = await manaraApi.getCapability(id);
      setSelected(cap);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch() {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const r = await manaraApi.search(query, { top_k: 10 });
      setSearchResult(r.hits);
      setStageTraces(r.stage_traces);
      setGaps(r.gaps);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSearching(false);
    }
  }

  async function handlePromote(decision: "approved" | "rejected") {
    if (!selected) return;
    const rationale = prompt(
      `${decision === "approved" ? "اعتماد" : "رفض"} البطاقة ${selected.id}\nأدخل السبب (إلزامي):`,
    );
    if (!rationale || rationale.trim().length < 10) {
      alert("السبب إلزامي ويجب أن يكون 10 أحرف على الأقل.");
      return;
    }
    try {
      await manaraApi.promote(selected.id, {
        reviewer: "ayman",
        rationale,
        decision,
      });
      // Refresh the selected capability to reflect the new status
      await handleSelect(selected.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleReindex() {
    if (!selected) return;
    try {
      const r = await manaraApi.reindex(selected.id);
      alert(`تمت إعادة توليد ${r.embeddings_regenerated} متجه.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    loadList();
  }, [domainFilter, statusFilter]);

  return (
    <section className="panel">
      <h3 className="panel__title">
        <span className="badge badge--ok">G01</span>
        متصفح سجل القدرات · Capability Registry Browser
      </h3>

      <div className="warning-box">
        البطاقات في حالة <code>candidate</code> حتى يعتمدها المالك صراحةً.
        محركات البحث الفعلية تُنفَّذ في G02.
      </div>

      {error && <div className="error">{error}</div>}

      {/* ── Seed + Filter bar ────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 16,
          alignItems: "center",
        }}
      >
        <button onClick={handleSeed} disabled={loading} className="action-btn">
          {seeded ? "↻ إعادة تحميل البطاقات الأولية" : "⤓ تحميل 8 بطاقات أولية"}
        </button>
        <label>
          النطاق:
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            style={{ marginRight: 8 }}
          >
            <option value="">(الكل)</option>
            {allDomains.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          الحالة:
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ marginRight: 8 }}
          >
            <option value="">(افتراضي: قابلة للبحث)</option>
            <option value="candidate">candidate</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
          </select>
        </label>
        <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
          {capabilities.length} بطاقة
        </span>
      </div>

      {/* ── Search bar ──────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 16 }}>
        <h4 style={{ margin: "0 0 8px" }}>🔍 البحث الدلالي في السجل</h4>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="مثال: مستقبل الأطراف الصناعية الذكية والواجهات العصبية"
            style={{
              flex: 1,
              padding: "8px 12px",
              background: "var(--panel-2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              color: "var(--text)",
              fontFamily: "inherit",
              fontSize: 14,
            }}
          />
          <button onClick={handleSearch} disabled={searching} className="action-btn">
            {searching ? "...جاري" : "بحث"}
          </button>
        </div>

        {/* ── Search results ────────────────────────────────────────────── */}
        {searchResult !== null && (
          <div style={{ marginTop: 16 }}>
            <h5
              style={{
                margin: "0 0 8px",
                fontSize: 12,
                color: "var(--text-muted)",
                textTransform: "uppercase",
              }}
            >
              نتائج البحث ({searchResult.length})
            </h5>

            {stageTraces.length > 0 && (
              <details style={{ marginBottom: 12 }}>
                <summary
                  style={{ cursor: "pointer", color: "var(--text-muted)", fontSize: 12 }}
                >
                  تتبّع مراحل خط الأنابيب ({stageTraces.length})
                </summary>
                <table
                  style={{
                    width: "100%",
                    marginTop: 8,
                    fontSize: 12,
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <thead>
                    <tr style={{ textAlign: "right", color: "var(--text-muted)" }}>
                      <th>المرحلة</th>
                      <th>داخل</th>
                      <th>خارج</th>
                      <th>ملاحظات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stageTraces.map((t, i) => (
                      <tr key={i}>
                        <td>{t.stage}</td>
                        <td>{t.candidates_in >= 0 ? t.candidates_in : "—"}</td>
                        <td>{t.candidates_out}</td>
                        <td style={{ color: "var(--text-muted)", fontSize: 11 }}>
                          {t.notes}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}

            {gaps.length > 0 && (
              <div className="warning-box" style={{ fontSize: 12 }}>
                <strong>ثغرات التغطية:</strong>
                <ul style={{ margin: "6px 0 0", paddingRight: 18 }}>
                  {gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              </div>
            )}

            {searchResult.length === 0 ? (
              <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
                لا توجد نتائج. جرب الاستعلام الإنجليزي أو عدّل الفلاتر.
              </div>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {searchResult.map((hit) => (
                  <li
                    key={hit.capability_id}
                    className="capability-card"
                    style={{ cursor: "pointer" }}
                    onClick={() => handleSelect(hit.capability_id)}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "baseline",
                      }}
                    >
                      <h4 style={{ margin: 0, fontSize: 14 }}>{hit.display_name}</h4>
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 12,
                          color: "var(--accent)",
                        }}
                      >
                        score: {hit.final_score.toFixed(3)}
                      </span>
                    </div>
                    <div
                      className="capability-card__id"
                      style={{ marginTop: 4, marginBottom: 8 }}
                    >
                      {hit.capability_id}
                    </div>
                    <div style={{ fontSize: 12, marginBottom: 6 }}>
                      <span style={{ color: "var(--text-muted)" }}>أسباب المطابقة: </span>
                      {hit.matched_by.map((m, i) => (
                        <span
                          key={i}
                          className="badge badge--ok"
                          style={{ marginRight: 4, fontSize: 10 }}
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                    {hit.rejected_by_negative.length > 0 && (
                      <div style={{ fontSize: 12 }}>
                        <span style={{ color: "var(--danger)" }}>⚠ مطابقة سلبية: </span>
                        {hit.rejected_by_negative.map((m, i) => (
                          <span
                            key={i}
                            className="badge badge--danger"
                            style={{ marginRight: 4, fontSize: 10 }}
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        marginTop: 8,
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      text={hit.text_similarity.toFixed(3)} · semantic=
                      {hit.semantic_similarity.toFixed(3)} · penalty=
                      {hit.negative_penalty.toFixed(3)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <hr style={{ borderColor: "var(--border)", margin: "24px 0" }} />

      {/* ── List + Detail ─────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16 }}>
        <div>
          <h4 style={{ margin: "0 0 8px" }}>البطاقات ({capabilities.length})</h4>
          <ul className="list" style={{ fontSize: 12 }}>
            {capabilities.map((c) => (
              <li
                key={c.id}
                onClick={() => handleSelect(c.id)}
                style={{ cursor: "pointer", padding: "6px 0" }}
              >
                <span
                  className="badge"
                  style={{
                    background: "transparent",
                    border: `1px solid ${STATUS_COLORS[c.status] ?? "#888"}`,
                    color: STATUS_COLORS[c.status] ?? "#888",
                    fontSize: 9,
                    marginRight: 6,
                  }}
                >
                  {STATUS_LABEL_AR[c.status] ?? c.status}
                </span>
                <span style={{ color: "var(--text)" }}>{c.display_name}</span>
                <div
                  style={{
                    fontSize: 10,
                    color: "var(--text-muted)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {c.id}
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div>
          {selected ? (
            <CapabilityDetail
              cap={selected}
              onPromote={handlePromote}
              onReindex={handleReindex}
            />
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
              اختر بطاقة من القائمة لعرض تفاصيلها الكاملة.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function CapabilityDetail({
  cap,
  onPromote,
  onReindex,
}: {
  cap: SearchCapability;
  onPromote: (decision: "approved" | "rejected") => void;
  onReindex: () => void;
}) {
  const statusColor = STATUS_COLORS[cap.status] ?? "#888";
  return (
    <div className="capability-card">
      <h4 style={{ margin: "0 0 4px" }}>{cap.display_name}</h4>
      <div className="capability-card__id">{cap.id}</div>

      <div className="kv" style={{ marginTop: 12 }}>
        <div className="kv__key">status</div>
        <div className="kv__value">
          <span
            className="badge"
            style={{
              background: "transparent",
              border: `1px solid ${statusColor}`,
              color: statusColor,
              fontSize: 10,
            }}
          >
            {cap.status}
          </span>
        </div>
        <div className="kv__key">version</div>
        <div className="kv__value">{cap.version}</div>
        <div className="kv__key">schema_version</div>
        <div className="kv__value">{cap.schema_version}</div>
        <div className="kv__key">source_license</div>
        <div className="kv__value">{cap.source_license}</div>
        <div className="kv__key">connector_ids</div>
        <div className="kv__value">
          {cap.connector_ids.length === 0
            ? "(فارغ — لا يوجد connector بعد)"
            : cap.connector_ids.join(", ")}
        </div>
        <div className="kv__key">domains</div>
        <div className="kv__value">{cap.domains.join(", ")}</div>
        <div className="kv__key">tags</div>
        <div className="kv__value">{cap.tags.join(", ")}</div>
      </div>

      <p
        style={{
          margin: "16px 0 0",
          color: "var(--text-muted)",
          fontSize: 13,
          lineHeight: 1.7,
        }}
      >
        {cap.description_long}
      </p>

      <div className="examples">
        <div className="pos">
          <h5>أمثلة صحيحة ({cap.positive_examples.length})</h5>
          <ul>
            {cap.positive_examples.slice(0, 8).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
            {cap.positive_examples.length > 8 && (
              <li style={{ color: "var(--text-muted)" }}>
                … و {cap.positive_examples.length - 8} أخرى
              </li>
            )}
          </ul>
        </div>
        <div className="neg">
          <h5>استخدامات خاطئة ({cap.negative_examples.length})</h5>
          <ul>
            {cap.negative_examples.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      </div>

      <div
        style={{
          marginTop: 16,
          paddingTop: 12,
          borderTop: "1px solid var(--border)",
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <button onClick={() => onPromote("approved")} className="action-btn">
          ✓ اعتماد البطاقة
        </button>
        <button onClick={() => onPromote("rejected")} className="action-btn">
          ✗ رفض البطاقة
        </button>
        <button onClick={onReindex} className="action-btn">
          ↻ إعادة توليد المتجهات
        </button>
      </div>
    </div>
  );
}
