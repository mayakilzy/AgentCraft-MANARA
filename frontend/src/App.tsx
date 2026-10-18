import { StatusBanner } from "./components/StatusBanner";
import { DiscoveryView } from "./components/DiscoveryView";
import { RegistryBrowser } from "./components/RegistryBrowser";

export default function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">
          MANARA · <span className="accent">منارة</span>
        </h1>
        <p className="app__subtitle">
          Adaptive Intelligence Factory · G00 Foundation + G01 Capability Registry
        </p>
      </header>

      <StatusBanner />
      <DiscoveryView />
      <RegistryBrowser />

      <footer className="footer">
        <p>
          MANARA G00+G01 · لا يوجد بحث أو تنبؤ حقيقي بعد (G02+).
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
