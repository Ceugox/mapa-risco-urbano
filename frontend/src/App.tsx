import { useEffect, useMemo, useState } from "react";
import { getLayer, getLayers, lastLayersFromCache, track } from "./api";
import { labels } from "./components/LayerPanel";
import { MapView } from "./components/Map";
import { EmergencyPanel } from "./components/EmergencyPanel";
import { ReportForm } from "./components/ReportForm";
import { SupportPanel } from "./components/SupportPanel";
import { Feature, FeatureCollection, LayerName, LayerStatus } from "./types";
import "./styles.css";

const layers: LayerName[] = ["alagamento", "cemaden", "inmet", "clima", "crime", "reports"];
const initial = Object.fromEntries(layers.map((layer) => [layer, layer !== "crime"])) as Record<
  LayerName,
  boolean
>;
const sources: Record<LayerName, string> = {
  alagamento: "CGE-SP",
  cemaden: "CEMADEN",
  inmet: "INMET",
  clima: "Open-Meteo",
  crime: "SSP-SP",
  reports: "Comunidade",
};
const frequencies: Record<LayerName, string> = {
  alagamento: "5 min",
  cemaden: "10 min",
  inmet: "10 min",
  clima: "15 min",
  crime: "mensal",
  reports: "contínua",
};
const coverage: Record<LayerName, string> = {
  alagamento: "capital",
  cemaden: "estado SP",
  inmet: "estado SP",
  clima: "5 pontos na capital",
  crime: "capital, H3 r8",
  reports: "capital",
};

function latestTime(statuses: LayerStatus[]) {
  const latest = statuses
    .map((status) => status.fetched_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .slice(-1)[0];
  return latest
    ? new Date(latest).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
    : "--:--";
}

function focusMap() {
  const section = document.getElementById("mapa");
  section?.scrollIntoView({ behavior: "smooth", block: "center" });
  window.setTimeout(() => section?.querySelector<HTMLElement>(".map-wrap")?.focus(), 250);
}

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export default function App() {
  const [statuses, setStatuses] = useState<LayerStatus[]>([]);
  const [data, setData] = useState<Partial<Record<LayerName, FeatureCollection>>>({});
  const [enabled, setEnabled] = useState(initial);
  const [reportMode, setReportMode] = useState(false);
  const [reportPoint, setReportPoint] = useState<{ lat: number; lng: number } | null>(null);
  const [reports, setReports] = useState<Feature[]>([]);
  const [toast, setToast] = useState("");
  const [isOnline, setIsOnline] = useState(
    () => typeof navigator === "undefined" || navigator.onLine,
  );
  const [fromCache, setFromCache] = useState(false);
  const [installPrompt, setInstallPrompt] = useState<InstallPromptEvent | null>(null);

  async function refresh() {
    try {
      const status = await getLayers();
      setFromCache(lastLayersFromCache);
      setStatuses(status);
      const loaded = await Promise.all(
        layers
          .filter((layer) => layer !== "reports")
          .map(async (layer) => [layer, await getLayer(layer)] as const),
      );
      setData(Object.fromEntries(loaded));
      const reportLayer = await getLayer("reports");
      setReports(reportLayer.features);
    } catch {
      // Backend can be starting.
    }
  }

  const closeReport = () => {
    setReportPoint(null);
    setReportMode(false);
  };

  const activateReport = () => {
    setReportMode(true);
    track("report_mode_opened");
    focusMap();
  };

  useEffect(() => {
    refresh();
    track("page_view", { w: window.innerWidth, h: window.innerHeight });
    const timer = window.setInterval(refresh, 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  useEffect(() => {
    const handler = (event: Event) => {
      event.preventDefault();
      setInstallPrompt(event as InstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const installApp = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    setInstallPrompt(null);
  };

  const activeSources = statuses.filter((status) => status.ok).length;
  const unavailableCount = statuses.filter((status) => !status.ok).length;
  const metrics = useMemo(() => {
    const flood = statuses.find((status) => status.layer === "alagamento")?.count ?? 0;
    const cemaden = statuses.find((status) => status.layer === "cemaden")?.count ?? 0;
    return `${flood} alagamentos ativos · ${cemaden} alertas CEMADEN · atualizado ${latestTime(
      statuses,
    )}`;
  }, [statuses]);
  const showOfflineBanner = !isOnline || fromCache;

  return (
    <>
      <header className="site-header">
        <nav className="nav container" aria-label="Navegação principal">
          <a className="brand" href="#inicio">
            MAPA<span>SP</span>
          </a>
          <div className="nav-links">
            <a href="#mapa">O mapa</a>
            <a href="#emergencia">Emergência</a>
            <a href="#apoio">Apoio</a>
            <a href="#como-funciona">Como funciona</a>
            <a href="#fontes">Fontes</a>
          </div>
          <div className="nav-actions">
            <a className="sos-link" href="#emergencia">
              SOS
            </a>
            <span className="live-pill">
              <span className="live-dot" aria-hidden="true">
                ●
              </span>{" "}
              AO VIVO · {activeSources} fontes ativas
            </span>
            <button className="button ghost nav-report" onClick={activateReport}>
              Reportar
            </button>
            {installPrompt && (
              <button className="button ghost nav-install" onClick={installApp}>
                Instalar app
              </button>
            )}
          </div>
        </nav>
      </header>

      {showOfflineBanner && (
        <div className="offline-banner" role="status" aria-live="polite">
          Sem conexão, mostrando dados de {latestTime(statuses)}
        </div>
      )}

      <main id="inicio">
        <section className="hero container">
          <div className="hero-copy">
            <p className="eyebrow">INTELIGÊNCIA CÍVICA PARA A CIDADE</p>
            <h1>
              Mapa de Risco Urbano
              <br />
              <span>São Paulo</span>
            </h1>
            <p className="hero-lead">
              Sinais oficiais e relatos locais para entender o que está acontecendo na cidade.
            </p>
            <div className="actions">
              <button className="button primary" onClick={focusMap}>
                Ver o mapa
              </button>
              <button className="button secondary" onClick={activateReport}>
                Reportar ocorrência
              </button>
            </div>
            <p className="metrics">{metrics}</p>
          </div>
          <div className="hero-map" id="mapa">
            <MapView
              statuses={statuses}
              data={data}
              enabled={enabled}
              onToggle={(layer) => setEnabled((state) => ({ ...state, [layer]: !state[layer] }))}
              reportMode={reportMode}
              onToggleReportMode={() => (reportMode ? closeReport() : activateReport())}
              onMapClick={setReportPoint}
              reportFeatures={reports}
              reportPoint={reportPoint}
              unavailableCount={unavailableCount}
            />
          </div>
        </section>

        <section className="status-ticker" aria-live="polite" aria-label="Status das fontes">
          <div className="container ticker-list">
            {layers.map((layer) => {
              const status = statuses.find((item) => item.layer === layer);
              return (
                <span className="ticker-item" key={layer}>
                  {labels[layer]}{" "}
                  <span className={status?.ok ? "ticker-ok" : "ticker-unavailable"}>
                    {status?.ok ? "●" : "○"}{" "}
                    {status?.ok
                      ? status.fetched_at
                        ? `há ${Math.max(
                            0,
                            Math.floor(
                              (Date.now() - new Date(status.fetched_at).getTime()) / 60000,
                            ),
                          )} min`
                        : "aguardando"
                      : "indisponível"}
                  </span>
                </span>
              );
            })}
          </div>
        </section>

        <EmergencyPanel />

        <SupportPanel />

        <section id="como-funciona" className="how section container">
          <div className="section-intro">
            <p className="eyebrow">TRANSPARÊNCIA</p>
            <h2>Como funciona</h2>
          </div>
          <div className="process-grid">
            <article>
              <span className="step">01</span>
              <h3>Fontes oficiais</h3>
              <p>Dados públicos do CGE, CEMADEN, INMET, Open-Meteo e SSP-SP.</p>
            </article>
            <article>
              <span className="step">02</span>
              <h3>Comunidade</h3>
              <p>Relatos locais completam o que os sensores não conseguem ver.</p>
            </article>
            <article>
              <span className="step">03</span>
              <h3>Atualização contínua</h3>
              <p>Disponibilidade e idade dos dados ficam visíveis em cada camada.</p>
            </article>
          </div>
        </section>

        <section id="fontes" className="sources section container">
          <div className="section-intro">
            <p className="eyebrow">DADOS ABERTOS</p>
            <h2>Fontes e método</h2>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Camada</th>
                  <th>Fonte</th>
                  <th>Frequência</th>
                  <th>Cobertura</th>
                  <th>Última atualização</th>
                </tr>
              </thead>
              <tbody>
                {layers.map((layer) => {
                  const status = statuses.find((item) => item.layer === layer);
                  return (
                    <tr key={layer}>
                      <td>{labels[layer]}</td>
                      <td>{sources[layer]}</td>
                      <td>{frequencies[layer]}</td>
                      <td>{coverage[layer]}</td>
                      <td>
                        {status?.fetched_at
                          ? new Date(status.fetched_at).toLocaleString("pt-BR")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="method-note">
            Crime: ocorrências registradas por região, agregadas em células H3 de resolução 8.
            Apenas células com pelo menos 5 ocorrências são exibidas para preservar a privacidade.
          </p>
        </section>
      </main>

      <footer className="footer">
        <div className="container footer-inner">
          <a className="brand" href="#inicio">
            MAPA<span>SP</span>
          </a>
          <p>Dados públicos para uma cidade mais informada.</p>
          <small>
            LGPD: não coletamos dados pessoais. Relatos são anônimos e expiram automaticamente.
          </small>
          <div className="footer-links">
            <a href="#fontes">Código aberto</a>
            <a href="#mapa">API</a>
            <a href="mailto:contato@riscosp.local">Contato</a>
          </div>
        </div>
      </footer>

      {reportPoint && (
        <ReportForm
          point={reportPoint}
          onClose={closeReport}
          onCreated={(feature) => {
            setReports((current) => [feature, ...current]);
            setToast(
              `Relato publicado · expira em ${
                feature.properties.category === "seguranca" ||
                feature.properties.category === "outro"
                  ? "24h"
                  : "6h"
              }`,
            );
            closeReport();
          }}
        />
      )}
      {toast && (
        <div className="toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </>
  );
}
