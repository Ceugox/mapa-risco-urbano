import { useState } from "react";
import { getSupportNearby, SupportPoint } from "../api";

const TYPE_ORDER = [
  "Delegacia da Mulher (DDM)",
  "Delegacia",
  "Polícia Militar",
  "UPA / Emergência",
  "GCM",
  "CRAS",
  "UBS",
  "Conselho Tutelar",
  "Comércio",
];

function typeClass(tipo: string) {
  if (tipo.includes("Mulher")) return "support-badge ddm";
  if (["Delegacia", "Polícia Militar", "GCM", "Delegacia (DHPP)"].includes(tipo))
    return "support-badge security";
  if (["UPA / Emergência", "UBS"].includes(tipo)) return "support-badge health";
  return "support-badge";
}

export function SupportPanel() {
  const [points, setPoints] = useState<SupportPoint[]>([]);
  const [status, setStatus] = useState("");
  const [asked, setAsked] = useState(false);

  function find() {
    if (!navigator.geolocation) {
      setStatus("Geolocalização não disponível neste aparelho.");
      return;
    }
    setStatus("Buscando pontos de apoio perto de você…");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const result = await getSupportNearby(pos.coords.latitude, pos.coords.longitude);
          setPoints(result.points);
          setAsked(true);
          setStatus(
            result.points.length ? "" : "Nenhum ponto oficial encontrado num raio próximo.",
          );
        } catch {
          setStatus("Busca indisponível agora. Ligue 190 em emergência.");
        }
      },
      () => setStatus("Permita o acesso à localização para ver os pontos mais próximos."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <section id="apoio" className="support section container">
      <div className="section-intro">
        <p className="eyebrow">PROTEÇÃO IMEDIATA</p>
        <h2>Pontos de apoio</h2>
        <p>
          Se você estiver em risco — mulheres, idosos, adolescentes e qualquer pessoa vulnerável —
          procure o local seguro mais próximo. Delegacias, UPAs 24h e unidades da GCM e da PM
          funcionam de madrugada.
        </p>
      </div>
      <div className="support-actions">
        <button className="button primary" onClick={find} type="button">
          Encontrar o mais próximo de mim
        </button>
        <a className="button secondary" href="tel:180">
          180 · Central da Mulher
        </a>
        <a className="button secondary" href="tel:190">
          190 · Polícia Militar
        </a>
      </div>
      {status && <p className="support-status">{status}</p>}
      {asked && points.length > 0 && (
        <ul className="support-list">
          {points.map((point, index) => (
            <li key={index} className="support-item">
              <div className="support-item-main">
                <span className={typeClass(point.tipo)}>{point.tipo}</span>
                <strong>{point.nome}</strong>
                <span className="support-meta">
                  {point.distancia_m < 1000
                    ? `${point.distancia_m} m`
                    : `${(point.distancia_m / 1000).toFixed(1)} km`}
                  {" · "}
                  {point.horario}
                </span>
              </div>
              <a
                className="button ghost"
                href={`https://www.google.com/maps/dir/?api=1&destination=${point.lat},${point.lon}`}
                target="_blank"
                rel="noreferrer"
              >
                Como chegar
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="method-note">
        Dados oficiais da Prefeitura de São Paulo (GeoSampa): delegacias — incluindo DDMs —, Polícia
        Militar, GCM, UPAs, UBS, CRAS e Conselhos Tutelares.
      </p>
    </section>
  );
}
