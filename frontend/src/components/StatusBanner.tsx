import { useEffect, useState } from "react";
import { manaraApi, type StatusResponse } from "../api/client";

export function StatusBanner() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    manaraApi
      .status()
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) {
    return (
      <section className="panel">
        <h3 className="panel__title">حالة الخدمة · Service Status</h3>
        <div className="error">تعذّر الوصول إلى /status — {error}</div>
        <div className="warning-box">
          تأكد من تشغيل الـ backend: <code>cd backend && uvicorn manara.app:create_app --factory --reload</code>
        </div>
      </section>
    );
  }

  if (!status) {
    return (
      <section className="panel">
        <h3 className="panel__title">حالة الخدمة · Service Status</h3>
        <div className="loading">جارٍ التحميل…</div>
      </section>
    );
  }

  return (
    <section className="panel">
      <h3 className="panel__title">
        <span className="badge badge--ok">G00</span>
        حالة الخدمة · Service Status
      </h3>
      <div className="kv">
        <div className="kv__key">app</div>
        <div className="kv__value">{status.app}</div>
        <div className="kv__key">version</div>
        <div className="kv__value">{status.version}</div>
        <div className="kv__key">env</div>
        <div className="kv__value">{status.env}</div>
        <div className="kv__key">discovery_mode</div>
        <div className="kv__value">
          <span className="badge badge--synthetic">{status.discovery_mode}</span>
        </div>
        <div className="kv__key">database</div>
        <div className="kv__value">{status.database_url_kind}</div>
        <div className="kv__key">timestamp</div>
        <div className="kv__value">{new Date(status.timestamp_utc).toLocaleString("ar")}</div>
        <div className="kv__key">code_repo</div>
        <div className="kv__value">
          <a href={status.build.code_repository} target="_blank" rel="noreferrer">
            {status.build.code_repository}
          </a>
        </div>
      </div>

      <div className="list-grid">
        <div>
          <h5 style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 6px" }}>
            ما الذي يوفّره G00 · capabilities
          </h5>
          <ul className="list">
            {status.capabilities.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
        <div>
          <h5 style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 6px" }}>
            ما الذي لم يُنفَّذ بعد · not_implemented
          </h5>
          <ul className="list">
            {status.not_implemented.slice(0, 8).map((c) => (
              <li key={c}>{c}</li>
            ))}
            {status.not_implemented.length > 8 && (
              <li>… و {status.not_implemented.length - 8} إضافية</li>
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
