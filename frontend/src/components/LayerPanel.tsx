import { useState } from "react";
import { LayerName, LayerStatus } from "../types";

export const layerNames: LayerName[] = [
  "alagamento",
  "alagamento_hist",
  "cemaden",
  "inmet",
  "clima",
  "crime",
  "reports",
];
export const labels: Record<LayerName, string> = {
  alagamento: "Alagamentos",
  alagamento_hist: "Alagamentos recorrentes",
  cemaden: "CEMADEN",
  inmet: "Alertas INMET",
  clima: "Clima",
  crime: "Crime agregado",
  reports: "Relatos da comunidade",
};
export const layerColors: Record<LayerName, string> = {
  alagamento: "#3b82f6",
  alagamento_hist: "rgba(59, 130, 246, 0.45)",
  cemaden: "#f97316",
  inmet: "#ef4444",
  clima: "#0f172a",
  crime: "#dc2626",
  reports: "#a855f7",
};

function age(value: string | null) {
  if (!value) return "aguardando";
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
  return `há ${minutes} min`;
}

const crimeColors = ["#fef3c7", "#fdba74", "#f97316", "#dc2626", "#7f1d1d"];

export function LayerPanel({
  statuses,
  enabled,
  onToggle,
}: {
  statuses: LayerStatus[];
  enabled: Record<LayerName, boolean>;
  onToggle: (layer: LayerName) => void;
}) {
  const [open, setOpen] = useState(() => !window.matchMedia("(max-width: 767px)").matches);
  const activeCount = Object.values(enabled).filter(Boolean).length;
  const downCount = statuses.filter((status) => !status.ok).length;

  return (
    <aside className={`layer-panel${open ? " open" : ""}`} aria-label="Camadas do mapa">
      <button
        className="layer-panel-header"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="layer-list"
      >
        <h2>Camadas</h2>
        <span className="mono-label">
          {activeCount} ativas{downCount ? ` · ${downCount} indispon.` : ""} {open ? "▴" : "▾"}
        </span>
      </button>
      <div className="layer-list" id="layer-list" hidden={!open}>
        {layerNames.map((layer) => {
          const item = statuses.find((status) => status.layer === layer);
          const available = item?.ok ?? false;
          return (
            <label
              className={`layer-row${available ? "" : " unavailable"}`}
              key={layer}
              title={available ? "" : "Fonte não respondeu; mostrando últimos dados válidos"}
            >
              <input
                type="checkbox"
                role="switch"
                checked={enabled[layer]}
                onChange={() => onToggle(layer)}
                aria-label={`${labels[layer]} ${enabled[layer] ? "ativada" : "desativada"}`}
              />
              <span
                className={`layer-swatch${layer === "alagamento_hist" ? " layer-swatch-dashed" : ""}`}
                style={available ? { backgroundColor: layerColors[layer] } : undefined}
                aria-hidden="true"
              />
              <span className="layer-name">{labels[layer]}</span>
              <span className="layer-data">
                <small>{age(item?.fetched_at ?? null)}</small>
                <small>{item?.count ?? 0}</small>
              </span>
            </label>
          );
        })}
      </div>
      {enabled.crime && (
        <div className="crime-legend" aria-label="Legenda de ocorrências criminais">
          <div className="crime-swatches">
            {crimeColors.map((color) => (
              <span key={color} style={{ backgroundColor: color }} />
            ))}
          </div>
          <small>menos → mais ocorrências</small>
          <small>jan–jul/2026 · células ≥5</small>
        </div>
      )}
    </aside>
  );
}
