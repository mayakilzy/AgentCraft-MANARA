import { useState } from "react";
import { Navigation } from "./components/Navigation";
import type { Tab } from "./components/Navigation";
import { StatusBanner } from "./components/StatusBanner";
import { DiscoveryView } from "./components/DiscoveryView";
import { RegistryBrowser } from "./components/RegistryBrowser";
import { InvestigationHome } from "./components/InvestigationHome";
import { SimpleSection, StatusBadge } from "./components/SimpleSection";

export default function App() {
  const [tab, setTab] = useState<Tab>("home");

  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">
          MANARA · <span className="accent">منارة</span>
        </h1>
        <p className="app__subtitle">
          Adaptive Intelligence Factory · G00–G08 Full Integration
        </p>
      </header>

      <Navigation active={tab} onChange={setTab} />

      {tab === "home" && (
        <>
          <StatusBanner />
          <InvestigationHome onSubmitted={() => setTab("workspace")} />
          <DiscoveryView />
        </>
      )}

      {tab === "workspace" && (
        <SimpleSection
          title="مساحة التحقيق"
          titleEn="Investigation Workspace"
          fetchUrl="/registry/capabilities?limit=5"
          render={(data: any) => (
            <div>
              <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
                هذه المساحة تعرض حالة التحقيقات النشطة. حالياً لا توجد تحقيقات
                نشطة في قاعدة البيانات — ابدأ بحثاً جديداً من القسم الرئيسي.
              </p>
              <div className="warning-box">
                <strong>حالة التكامل:</strong> واجهة التحقيق الكاملة تتطلب
                تكاملاً إضافياً مع workflow state machine (G04). هذه واجهة
                أولية تعرض القدرات المتاحة.
              </div>
              {data.capabilities?.map((c: any) => (
                <div key={c.id} className="capability-card">
                  <h4>{c.display_name}</h4>
                  <div className="capability-card__id">{c.id}</div>
                  <StatusBadge status={c.status} />
                </div>
              ))}
            </div>
          )}
        />
      )}

      {tab === "registry" && (
        <>
          <RegistryBrowser />
          <SimpleSection
            title="بحث دلالي"
            titleEn="Semantic Search"
            fetchUrl="/registry/capabilities?limit=3"
            render={() => (
              <div className="warning-box">
                استخدم قسم سجل القدرات أعلاه للبحث الدلالي والفلترة.
              </div>
            )}
          />
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
                    <div className="kv__key">الترخيص</div>
                    <div className="kv__value">{c.license}</div>
                    <div className="kv__key">يتطلب مفتاح API</div>
                    <div className="kv__value">{c.auth_required ? "نعم" : "لا"}</div>
                    <div className="kv__key">المضيفون المسموحون</div>
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
                  لا توجد قوالب محفوظة بعد. ابدأ بحثاً جديداً من القسم الرئيسي
                  لإنشاء قالب مؤقت.
                </div>
              ) : (
                data.map((m: any) => (
                  <div key={m.id} className="capability-card">
                    <h4>{m.display_name}</h4>
                    <div className="capability-card__id">{m.id}</div>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div className="kv__key">الحالة</div>
                      <div className="kv__value"><StatusBadge status={m.state} /></div>
                      <div className="kv__key">المجال</div>
                      <div className="kv__value">{m.domain}</div>
                      <div className="kv__key">القدرات</div>
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
                      <div className="kv__key">الحالة</div>
                      <div className="kv__value"><StatusBadge status={a.state} /></div>
                      <div className="kv__key">الدور</div>
                      <div className="kv__value">{a.role}</div>
                      <div className="kv__key">الأدوات</div>
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
                      <div className="kv__key">المنهجية</div>
                      <div className="kv__value">{f.method}</div>
                      <div className="kv__key">الحالة</div>
                      <div className="kv__value"><StatusBadge status={f.status} /></div>
                      <div className="kv__key">القيمة المتوقعة</div>
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
                  لا توجد منشورات بعد. أنشئ تحقيقاً بأدلة، ثم استخدم Publishing API
                  لإنشاء تقارير وستوري بورد.
                </div>
              ) : (
                data.map((p: any) => (
                  <div key={p.id} className="capability-card">
                    <h4>{p.title}</h4>
                    <div className="capability-card__id">{p.id}</div>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div className="kv__key">النوع</div>
                      <div className="kv__value">{p.output_type}</div>
                      <div className="kv__key">الحالة</div>
                      <div className="kv__value"><StatusBadge status={p.status} /></div>
                      <div className="kv__key">بوابة الجودة</div>
                      <div className="kv__value">
                        <StatusBadge status={p.quality_gate_passed ? "approved" : "rejected"} />
                      </div>
                      <div className="kv__key">قابل للتنزيل</div>
                      <div className="kv__value">{p.downloadable ? "✓" : "✗"}</div>
                    </div>
                    {p.downloadable && (
                      <div style={{ marginTop: 8, display: "flex", gap: 4 }}>
                        <a href={`/publishing/publications/${p.id}/download?format=markdown`} className="action-btn" style={{ textDecoration: "none", fontSize: 12 }}>
                          ↓ Markdown
                        </a>
                        <a href={`/publishing/publications/${p.id}/download?format=json`} className="action-btn" style={{ textDecoration: "none", fontSize: 12 }}>
                          ↓ JSON
                        </a>
                        <a href={`/publishing/publications/${p.id}/download?format=text`} className="action-btn" style={{ textDecoration: "none", fontSize: 12 }}>
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
                <strong>الاعتماد البشري مطلوب لـ:</strong>
                <ul style={{ margin: "6px 0 0", paddingRight: 18 }}>
                  <li>ترقية المصادر والموصلات من candidate → approved (G02)</li>
                  <li>ترقية القدرات من candidate → approved (G01)</li>
                  <li>ترقية القوالب من temporary → reusable (G04)</li>
                  <li>ترقية وصفات الخبراء من on_demand → recipe_saved (G05)</li>
                  <li>نشر التوقعات (G06) — غير قابلة للتعديل بعد النشر</li>
                  <li>اعتماد المخرجات قبل النشر النهائي (G07)</li>
                </ul>
              </div>
              <div style={{ marginTop: 12 }}>
                <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  القدرات المكتملة ({data.capabilities?.length || 0})
                </h5>
                <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  {data.capabilities?.filter((c: string) => c.includes("approved")).length || 0} معتمدة
                  · {data.capabilities?.filter((c: string) => c.includes("candidate")).length || 0} مرشحة
                </p>
              </div>
              <div style={{ marginTop: 8 }}>
                <h5 style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  غير مكتمل ({data.not_implemented?.length || 0})
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
          MANARA G00–G08 · {new Date().getFullYear()} ·
          <a href="https://github.com/mayakilzy/AgentCraft-MANARA" target="_blank" rel="noreferrer"> GitHub</a>
          {" · "}
          <a href="https://github.com/mayakilzy/repo-info/tree/main/AgentCraft-MANARA" target="_blank" rel="noreferrer"> Specs</a>
        </p>
      </footer>
    </div>
  );
}
