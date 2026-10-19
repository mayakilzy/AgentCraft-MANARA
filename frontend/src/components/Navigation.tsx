export type Tab = "home" | "workspace" | "registry" | "foundry" | "molds" | "agents" | "foresight" | "publishing" | "approvals";

const TABS: { id: Tab; labelAr: string; labelEn: string }[] = [
  { id: "home", labelAr: "الرئيسية", labelEn: "Home" },
  { id: "workspace", labelAr: "مساحة التحقيق", labelEn: "Workspace" },
  { id: "registry", labelAr: "سجل القدرات", labelEn: "Registry" },
  { id: "foundry", labelAr: "المصنع", labelEn: "Foundry" },
  { id: "molds", labelAr: "القوالب", labelEn: "Molds" },
  { id: "agents", labelAr: "الخبراء", labelEn: "Agents" },
  { id: "foresight", labelAr: "الاستشراف", labelEn: "Foresight" },
  { id: "publishing", labelAr: "النشر", labelEn: "Publishing" },
  { id: "approvals", labelAr: "الاعتماد", labelEn: "Approvals" },
];

export function Navigation({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  return (
    <nav style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 16, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className="action-btn"
          style={{
            background: active === t.id ? "rgba(78, 201, 176, 0.15)" : "var(--panel-2)",
            borderColor: active === t.id ? "var(--accent)" : "var(--border)",
            fontSize: 13,
            padding: "6px 14px",
          }}
        >
          <span>{t.labelAr}</span>
          <span style={{ color: "var(--text-muted)", fontSize: 11, marginRight: 4 }}>· {t.labelEn}</span>
        </button>
      ))}
    </nav>
  );
}

// Tab type is exported above
