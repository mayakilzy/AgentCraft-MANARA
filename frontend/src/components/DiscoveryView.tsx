import { useEffect, useState } from "react";
import { manaraApi, type SyntheticDiscoveryView } from "../api/client";

export function DiscoveryView() {
  const [view, setView] = useState<SyntheticDiscoveryView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    manaraApi
      .discovery()
      .then(setView)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <section className="panel">
      <h3 className="panel__title">
        <span className="badge badge--synthetic">SYNTHETIC</span>
        عرض الاكتشاف · Discovery View
      </h3>

      <div className="warning-box">
        {view?.warning ??
          "هذا عرض اصطناعي (synthetic) لأغراض التحقّق من العقد فقط. لا يوجد استدعاء فعلي لأي مصدر."}
      </div>

      {error && <div className="error">تعذّر تحميل /discovery — {error}</div>}

      {!view && !error && <div className="loading">جارٍ التحميل…</div>}

      {view && (
        <>
          <div className="kv">
            <div className="kv__key">label</div>
            <div className="kv__value">
              <span className="badge badge--synthetic">{view.label}</span>
            </div>
            <div className="kv__key">data_origin</div>
            <div className="kv__value">{view.data_origin}</div>
            <div className="kv__key">generated_at</div>
            <div className="kv__value">
              {new Date(view.generated_at).toLocaleString("ar")}
            </div>
          </div>

          <div className="capability-card">
            <h4>{view.capability.display_name}</h4>
            <div className="capability-card__id">{view.capability.id}</div>
            <p style={{ margin: "8px 0 0", color: "var(--text-muted)", fontSize: 13 }}>
              {view.capability.description_long}
            </p>

            <div className="kv" style={{ marginTop: 16 }}>
              <div className="kv__key">status</div>
              <div className="kv__value">
                <span className="badge badge--danger">{view.capability.status}</span>
              </div>
              <div className="kv__key">connector_ids</div>
              <div className="kv__value">
                {view.capability.connector_ids.length === 0
                  ? "(فارغ — لا يوجد connector حقيقي بعد)"
                  : view.capability.connector_ids.join(", ")}
              </div>
              <div className="kv__key">source_license</div>
              <div className="kv__value">{view.capability.source_license}</div>
              <div className="kv__key">tags</div>
              <div className="kv__value">{view.capability.tags.join(", ")}</div>
            </div>

            <div className="examples">
              <div className="pos">
                <h5>أمثلة صحيحة · positive_examples</h5>
                <ul>
                  {view.capability.positive_examples.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
              <div className="neg">
                <h5>استخدامات خاطئة · negative_examples</h5>
                <ul>
                  {view.capability.negative_examples.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
