import { StatusBanner } from "./components/StatusBanner";
import { DiscoveryView } from "./components/DiscoveryView";

export default function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">
          MANARA · <span className="accent">منارة</span>
        </h1>
        <p className="app__subtitle">
          Adaptive Intelligence Factory · G00 Engineering Foundation
        </p>
      </header>

      <StatusBanner />
      <DiscoveryView />

      <footer className="footer">
        <p>
          MANARA G00 · foundation only · لا يوجد بحث أو تنبؤ حقيقي بعد.
          <br />
          <a
            href="https://github.com/mayakilzy/AgentCraft-MANARA"
            target="_blank"
            rel="noreferrer"
          >
            github.com/mayakilzy/AgentCraft-MANARA
          </a>
          {" · "}
          <a
            href="https://github.com/mayakilzy/repo-info/tree/main/AgentCraft-MANARA"
            target="_blank"
            rel="noreferrer"
          >
            specs
          </a>
        </p>
      </footer>
    </div>
  );
}
