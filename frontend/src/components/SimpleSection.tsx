import { useEffect, useState } from "react";

export function SimpleSection({
  title,
  titleEn,
  fetchUrl,
  render,
}: {
  title: string;
  titleEn: string;
  fetchUrl: string;
  render: (data: any) => React.ReactNode;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(fetchUrl)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [fetchUrl]);

  return (
    <section className="panel">
      <h3 className="panel__title">
        {title} · {titleEn}
      </h3>
      {loading && <div className="loading">جارٍ التحميل…</div>}
      {error && <div className="error">{error}</div>}
      {data && render(data)}
    </section>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    discovered: "var(--text-muted)", assessed: "var(--text-muted)",
    candidate: "var(--accent-warm)", sandbox_tested: "var(--accent-warm)",
    review_pending: "var(--accent-warm)", approved: "var(--accent)",
    rejected: "var(--danger)", quarantined: "var(--danger)",
    degraded: "var(--danger)", retired: "var(--text-muted)",
    on_demand: "var(--text-muted)", recipe_saved: "var(--accent-warm)",
    tested: "var(--accent)", maintained: "var(--accent)",
    temporary: "var(--accent-warm)", reusable: "var(--accent)",
    draft: "var(--text-muted)", published: "var(--accent)",
    superseded: "var(--text-muted)", archived: "var(--text-muted)",
    instantiated: "var(--accent-warm)", running: "var(--accent-warm)",
    completed: "var(--accent)", failed: "var(--danger)",
    terminated: "var(--text-muted)", none: "var(--danger)",
    catalog: "var(--accent-warm)", operational: "var(--accent)",
    verified: "var(--accent)", insufficient_evidence: "var(--danger)",
  };
  const color = colors[status] || "var(--text-muted)";
  return (
    <span className="badge" style={{ background: "transparent", border: `1px solid ${color}`, color, fontSize: 10 }}>
      {status}
    </span>
  );
}
