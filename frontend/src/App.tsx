import { useState } from "react";
import { Navigation } from "./components/Navigation";
import type { Tab } from "./components/Navigation";
import { StatusBanner } from "./components/StatusBanner";
import { DiscoveryView } from "./components/DiscoveryView";
import { RegistryBrowser } from "./components/RegistryBrowser";
import { InvestigationHome } from "./components/InvestigationHome";
import { InvestigationWorkspace } from "./components/InvestigationWorkspace";
import { SimpleSection, StatusBadge } from "./components/SimpleSection";
import { useInvestigationContext } from "./hooks/useInvestigationContext";

export default function App() {
  const [tab, setTab] = useState<Tab>("home");
  const { ctx, updateCtx, clearCtx } = useInvestigationContext();

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">
          MANARA · <span className="accent">منارة</span>
        </h1>
        <p className="app__subtitle">
          Adaptive Intelligence Factory · G09 Final Integration
        </p>
      </header>

      {/* Investigation context banner — visible across all tabs */}
      {ctx && (
        <div style={{
          background: "rgba(78, 201, 176, 0.08)",
          border: "1px solid rgba(78, 201, 176, 0.3)",
          borderRadius: 6,
          padding: "8px 12px",
          marginBottom: 12,
          fontSize: 12,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}>
          <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
            ● تحقيق نشط · Active Investigation
          </span>
          <span style={{ color: "var(--text)" }}>{ctx.query.slice(0, 60)}</span>
          <span style={{ color: "var(--text-muted)", fontSize: 10 }}>
            ({ctx.moldResult?.is_complete ? "✓ complete" : "✗ incomplete"})
          </span>
          <button onClick={() => { clearCtx(); setTab("home"); }} className="action-btn" style={{ fontSize: 10, padding: "2px 8px" }}>
            ✗ إغلاق
          </button>
        </div>
      )}

      <Navigation active={tab} onChange={setTab} />

      {tab === "home" && (
        <>
          <StatusBanner />
          <InvestigationHome
            onSubmitted={(query, moldResult, investigationId) => {
              updateCtx({ query, moldResult, investigationId, moldId: moldResult?.mold_recipe_id || null });
              setTab("workspace");
            }}
          />
          <DiscoveryView />
        </>
      )}

      {tab === "workspace" && (
        <InvestigationWorkspace ctx={ctx} onClear={() => { clearCtx(); setTab("home"); }} />
      )}

      {tab === "registry" && (
        <>
          <RegistryBrowser />
        </>
      )}

      {tab === "foundry" && (
        <SimpleSection
          title="مصنع البحث"
          titleEn="Search Foundry"
          fetchUrl="/foundry/candidates"
          render={(data: any) => (
            <div>
              {data.map((c: any) => (
                <div key={c.id} className="capability-card">
                  <h4>{c.display_name}</h4>
                  <div className="capability-card__id">{c.id}</div>
                  <div className="kv" style={{ marginTop: 8 }}>
                    <div className="kv__key">الترخيص · License</div>
                    <div className="kv__value">{c.license}</div>
                    <div className="kv__key">API Key</div>
                    <div className="kv__value">{c.auth_required ? "مطلوب" : "غير مطلوب"}</div>
                    <div className="kv__key">المضيفون · Hosts</div>
                    <div className="kv__value">{c.allowed_hosts.join(", ")}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        />
      )}

      {tab === "molds" && (
        <SimpleSection
          title="القوالب"
          titleEn="Mold Factory"
          fetchUrl="/mold-factory/molds?limit=20"
          render={(data: any) => (
            <div>
              {data.length === 0 ? (
                <div className="warning-box">
                  لا توجد قوالب محفوظة بعد. ابدأ بحثاً جديداً من القسم الرئيسي.
                </div>
              ) : (
                data.map((m: any) => (
                  <div key={m.id} className="capability-card">
                    <h4>{m.display_name}</h4>
                    <div className="capability-card__id">{m.id}</div>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div className="kv__key">الحالة · State</div>
                      <div className="kv__value"><StatusBadge status={m.state} /></div>
                      <div className="kv__key">المجال · Domain</div>
                      <div className="kv__value">{m.domain}</div>
                      <div className="kv__key">القدرات · Capabilities</div>
                      <div className="kv__value">{m.capability_ids?.length || 0}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        />
      )}

      {tab === "agents" && (
        <SimpleSection
          title="الخبراء"
          titleEn="Agent Phone Book"
          fetchUrl="/agents/recipes?limit=20"
          render={(data: any) => (
            <div>
              <div style={{ marginBottom: 12 }}>
                <button
                  className="action-btn"
                  onClick={async () => {
                    await fetch("/agents/recipes/seed-generalist", { method: "POST" });
                    window.location.reload();
                  }}
                >
                  ⤓ تحميل المحلل العام · Seed Generalist
                </button>
                {" "}
                <button
                  className="action-btn"
                  onClick={async () => {
                    await fetch("/agents/recipes/seed-clinical", { method: "POST" });
                    window.location.reload();
                  }}
                >
                  ⤓ تحميل الخبير السريري · Seed Clinical Reviewer
                </button>
              </div>
              {data.length === 0 ? (
                <div className="warning-box">
                  لا توجد وصفات خبراء محفوظة. استخدم الأزرار أعلاه لتحميل الوصفات الأولية.
                </div>
              ) : (
                data.map((a: any) => (
                  <div key={a.id} className="capability-card">
                    <h4>{a.display_name}</h4>
                    <div className="capability-card__id">{a.id}</div>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div className="kv__key">الحالة · State</div>
                      <div className="kv__value"><StatusBadge status={a.state} /></div>
                      <div className="kv__key">الدور · Role</div>
                      <div className="kv__value">{a.role}</div>
                      <div className="kv__key">الأدوات · Tools</div>
                      <div className="kv__value">{a.allowed_tools?.length || 0}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        />
      )}

      {tab === "foresight" && (
        <SimpleSection
          title="الاستشراف"
          titleEn="Foresight Studio"
          fetchUrl="/foresight/forecasts?limit=10"
          render={(data: any) => (
            <div>
              {(!data || data.length === 0) ? (
                <div className="warning-box">
                  لا توجد توقعات منشورة بعد. الاستشراف يتطلب أدلة كافية من G03
                  وتوقعات منشورة من G06.
                </div>
              ) : (
                data.map((f: any) => (
                  <div key={f.id} className="capability-card">
                    <h4>{f.target}</h4>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div className="kv__key">المنهجية · Method</div>
                      <div className="kv__value">{f.method}</div>
                      <div className="kv__key">الحالة · Status</div>
                      <div className="kv__value"><StatusBadge status={f.status} /></div>
                      <div className="kv__key">القيمة · Estimate</div>
                      <div className="kv__value">{f.point_estimate ?? "—"}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        />
      )}

      {tab === "publishing" && (
        <SimpleSection
          title="النشر"
          titleEn="Publishing Studio"
          fetchUrl="/publishing/publications?limit=20"
          render={(data: any) => (
            <div>
              {data.length === 0 ? (
                <div className="warning-box">
                  لا توجد منشورات بعد. أنشئ تحقيقاً بأدلة، ثم استخدم Workspace
                  لإنشاء تقارير وستوري بورد.
                </div>
              ) : (
                data.map((p: any) => (
                  <div key={p.id} className="capability-card">
                    <h4>{p.title}</h4>
                    <div className="capability-card__id">{p.id}</div>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div className="kv__key">النوع · Type</div>
                      <div className="kv__value">{p.output_type}</div>
                      <div className="kv__key">بوابة الجودة · Quality Gate</div>
                      <div className="kv__value">
                        <StatusBadge status={p.quality_gate_passed ? "approved" : "rejected"} />
                      </div>
                      <div className="kv__key">قابل للتنزيل · Downloadable</div>
                      <div className="kv__value">{p.downloadable ? "✓" : "✗"}</div>
                    </div>
                    {p.downloadable && (
                      <div style={{ marginTop: 8, display: "flex", gap: 4 }}>
                        <a href={`/publishing/publications/${p.id}/download?format=markdown`} className="action-btn" style={{ textDecoration: "none", fontSize: 11 }}>
                          ↓ Markdown
                        </a>
                        <a href={`/publishing/publications/${p.id}/download?format=json`} className="action-btn" style={{ textDecoration: "none", fontSize: 11 }}>
                          ↓ JSON
                        </a>
                        <a href={`/publishing/publications/${p.id}/download?format=text`} className="action-btn" style={{ textDecoration: "none", fontSize: 11 }}>
                          ↓ Text
                        </a>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        />
      )}

      {tab === "approvals" && (
        <SimpleSection
          title="مركز الاعتماد"
          titleEn="Approval Center"
          fetchUrl="/status"
          render={(data: any) => (
            <div>
              <div className="warning-box">
                <strong>الاعتماد البشري مطلوب لـ · Human approval required for:</strong>
                <ul style={{ margin: "6px 0 0", paddingRight: 18 }}>
                  <li>ترقية المصادر والموصلات (G02)</li>
                  <li>ترقية القدرات (G01)</li>
                  <li>ترقية القوالب temporary → reusable (G04)</li>
                  <li>ترقية وصفات الخبراء (G05)</li>
                  <li>نشر التوقعات (G06) — immutable</li>
                  <li>اعتماد المخرجات قبل النشر (G07)</li>
                </ul>
              </div>
              <div style={{ marginTop: 12 }}>
                <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  القدرات المكتملة · Capabilities ({data.capabilities?.length || 0})
                </h5>
              </div>
              <div style={{ marginTop: 8 }}>
                <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  غير مكتمل · Not Implemented ({data.not_implemented?.length || 0})
                </h5>
                <ul className="list" style={{ fontSize: 11 }}>
                  {data.not_implemented?.map((item: string) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        />
      )}

      <footer className="footer">
        <p>
          MANARA G00–G09 · {new Date().getFullYear()} ·
          <a href="https://github.com/mayakilzy/AgentCraft-MANARA" target="_blank" rel="noreferrer"> GitHub</a>
          {" · "}
          <a href="https://github.com/mayakilzy/repo-info/tree/main/AgentCraft-MANARA" target="_blank" rel="noreferrer"> Specs</a>
        </p>
      </footer>
    </div>
  );
}
