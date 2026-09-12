import {
  APIProvider,
  InfoWindow,
  Map as GoogleMap,
  Marker,
  Polygon,
  useMap,
  useMapsLibrary,
} from "@vis.gl/react-google-maps";
import { Fragment, useEffect, useMemo, useState } from "react";
import { confirmReport } from "../api";
import { Feature, FeatureCollection, LayerName, LayerStatus } from "../types";
import { labels, layerColors, LayerPanel } from "./LayerPanel";
import { LocationTools } from "./LocationTools";

const center = { lat: -23.55, lng: -46.63 };
const crimeColors = ["#fef3c7", "#fdba74", "#f97316", "#dc2626", "#7f1d1d"];
const sources: Record<LayerName, string> = {
  alagamento: "CGE-SP",
  cemaden: "CEMADEN",
  inmet: "INMET",
  clima: "Open-Meteo",
  crime: "SSP-SP",
  reports: "Comunidade",
};
const mapStyles = [
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "landscape", elementType: "geometry", stylers: [{ saturation: -100 }] },
  { featureType: "road", elementType: "geometry", stylers: [{ saturation: -100 }] },
  { featureType: "all", elementType: "labels.text.fill", stylers: [{ color: "#6b6b73" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#d9dde3" }] },
];

type SelectedFeature = { feature: Feature; layer: LayerName };

function pointPosition(feature: Feature) {
  if (feature.geometry.type !== "Point") return null;
  const [lng, lat] = feature.geometry.coordinates;
  return { lat, lng };
}

function numberProperty(feature: Feature, key: string, fallback = 0) {
  const value = feature.properties[key];
  return typeof value === "number" ? value : fallback;
}

function textProperty(feature: Feature, key: string, fallback: string) {
  const value = feature.properties[key];
  return typeof value === "string" ? value : fallback;
}

function crimeClass(total: number, breaks: number[]) {
  const index = breaks.findIndex((breakpoint) => total <= breakpoint);
  return index === -1 ? crimeColors.length - 1 : index;
}

function Traffic() {
  const map = useMap();
  const maps = useMapsLibrary("maps");

  useEffect(() => {
    if (!map || !maps) return;
    const traffic = new maps.TrafficLayer();
    traffic.setMap(map);
    return () => traffic.setMap(null);
  }, [map, maps]);

  return null;
}

function MapMarkers({
  data,
  enabled,
  reportFeatures,
  reportPoint,
  reportMode,
  onSelect,
}: {
  data: Partial<Record<LayerName, FeatureCollection>>;
  reportMode: boolean;
  enabled: Record<LayerName, boolean>;
  reportFeatures: Feature[];
  reportPoint: { lat: number; lng: number } | null;
  onSelect: (feature: Feature, layer: LayerName) => void;
}) {
  const maps = useMapsLibrary("maps");
  const crimeFeatures = data.crime?.features ?? [];
  const crimeBreaks = useMemo(() => {
    const totals = crimeFeatures
      .map((feature) => numberProperty(feature, "total"))
      .sort((left, right) => left - right);
    if (!totals.length) return [];
    return [0.2, 0.4, 0.6, 0.8, 1].map(
      (quantile) => totals[Math.ceil(quantile * totals.length) - 1],
    );
  }, [crimeFeatures]);

  if (!maps) return null;
  const icon = (fillColor: string, scale: number, strokeColor = "#ffffff"): google.maps.Symbol => ({
    path: 0,
    scale,
    strokeColor,
    strokeWeight: 1.5,
    fillColor,
    fillOpacity: 0.9,
  });

  return (
    <>
      {enabled.alagamento &&
        (data.alagamento?.features ?? []).map((feature, index) => {
          const position = pointPosition(feature);
          return position ? (
            <Marker
              key={`a${index}`}
              position={position}
              icon={icon(
                layerColors.alagamento,
                numberProperty(feature, "severidade") >= 4 ? 11 : 8,
              )}
              clickable={!reportMode}
              onClick={() => onSelect(feature, "alagamento")}
            />
          ) : null;
        })}
      {enabled.cemaden &&
        (data.cemaden?.features ?? []).map((feature, index) => {
          const position = pointPosition(feature);
          return position ? (
            <Marker
              key={`c${index}`}
              position={position}
              icon={icon(layerColors.cemaden, 9)}
              clickable={!reportMode}
              onClick={() => onSelect(feature, "cemaden")}
            />
          ) : null;
        })}
      {enabled.clima &&
        (data.clima?.features ?? []).map((feature, index) => {
          const position = pointPosition(feature);
          return position ? (
            <Marker
              key={`m${index}`}
              position={position}
              icon={icon(layerColors.clima, 8)}
              label={{
                text: `${Math.round(numberProperty(feature, "temperature_2m"))}°`,
                color: "#ffffff",
                fontSize: "10px",
                fontWeight: "700",
              }}
              clickable={!reportMode}
              onClick={() => onSelect(feature, "clima")}
            />
          ) : null;
        })}
      {enabled.reports &&
        reportFeatures.map((feature) => {
          const position = pointPosition(feature);
          if (!position) return null;
          const confirmed = numberProperty(feature, "confirmations") >= 3;
          return (
            <Fragment key={feature.id}>
              {confirmed && (
                <Marker
                  position={position}
                  icon={icon("#ffffff", 13, layerColors.reports)}
                  clickable={!reportMode}
                  onClick={() => onSelect(feature, "reports")}
                />
              )}
              <Marker
                position={position}
                icon={icon(layerColors.reports, 9)}
                clickable={!reportMode}
                onClick={() => onSelect(feature, "reports")}
              />
            </Fragment>
          );
        })}
      {reportPoint && <Marker position={reportPoint} icon={icon(layerColors.reports, 11)} />}
      {enabled.inmet &&
        (data.inmet?.features ?? []).map((feature, index) =>
          feature.geometry.type === "Polygon" ? (
            <Polygon
              key={`i${index}`}
              paths={feature.geometry.coordinates[0].map(([lng, lat]) => ({ lat, lng }))}
              fillColor={layerColors.inmet}
              fillOpacity={0.12}
              strokeColor={layerColors.inmet}
              strokeWeight={1}
              clickable={!reportMode}
              onClick={() => onSelect(feature, "inmet")}
            />
          ) : null,
        )}
      {enabled.crime &&
        crimeFeatures.map((feature, index) =>
          feature.geometry.type === "Polygon" ? (
            <Polygon
              key={`h${index}`}
              paths={feature.geometry.coordinates[0].map(([lng, lat]) => ({ lat, lng }))}
              fillColor={crimeColors[crimeClass(numberProperty(feature, "total"), crimeBreaks)]}
              fillOpacity={0.35}
              strokeWeight={0}
              clickable={!reportMode}
              onClick={() => onSelect(feature, "crime")}
            />
          ) : null,
        )}
    </>
  );
}

function formatTimestamp(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("pt-BR") : "aguardando";
}

export function MapView({
  statuses,
  data,
  enabled,
  onToggle,
  reportMode,
  onToggleReportMode,
  onMapClick,
  reportFeatures,
  reportPoint,
  unavailableCount,
}: {
  statuses: LayerStatus[];
  data: Partial<Record<LayerName, FeatureCollection>>;
  enabled: Record<LayerName, boolean>;
  onToggle: (layer: LayerName) => void;
  reportMode: boolean;
  onToggleReportMode: () => void;
  onMapClick: (point: { lat: number; lng: number }) => void;
  reportFeatures: Feature[];
  reportPoint: { lat: number; lng: number } | null;
  unavailableCount: number;
}) {
  const [selected, setSelected] = useState<SelectedFeature | null>(null);
  const [confirming, setConfirming] = useState(false);
  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";
  const selectedStatus = selected
    ? statuses.find((status) => status.layer === selected.layer)
    : undefined;
  const selectedReportId = selected?.feature.id ?? selected?.feature.properties.id ?? "";
  const selectedTimestamp =
    selected?.layer === "reports"
      ? textProperty(selected.feature, "created_at", selectedStatus?.fetched_at ?? "aguardando")
      : selectedStatus?.fetched_at;

  async function handleConfirm() {
    if (!selectedReportId || confirming) return;
    setConfirming(true);
    try {
      const result = await confirmReport(selectedReportId);
      if (selected) {
        setSelected({
          ...selected,
          feature: {
            ...selected.feature,
            properties: { ...selected.feature.properties, confirmations: result.confirmations },
          },
        });
      }
    } finally {
      setConfirming(false);
    }
  }

  return (
    <APIProvider apiKey={key}>
      <div className={`map-wrap${reportMode ? " report-mode" : ""}`} tabIndex={-1} data-map-surface>
        {unavailableCount > 0 && (
          <div className="map-alert" role="status">
            {`${unavailableCount} ${unavailableCount === 1 ? "fonte indisponível" : "fontes indisponíveis"} — mostrando últimos dados válidos`}
          </div>
        )}
        <LayerPanel statuses={statuses} enabled={enabled} onToggle={onToggle} />
        <div className="map-toolbar">
          <button className="button secondary report-toggle" onClick={onToggleReportMode}>
            {reportMode ? "Clique no local · Esc cancela" : "Reportar ocorrência"}
          </button>
        </div>
        {reportMode && <span className="report-hint">Clique no local · Esc cancela</span>}
        <GoogleMap
          defaultCenter={center}
          defaultZoom={11}
          gestureHandling="greedy"
          disableDefaultUI={false}
          fullscreenControl={false}
          mapTypeControl={false}
          streetViewControl={false}
          styles={mapStyles}
          onClick={(event) => {
            if (reportMode && event.detail.latLng) {
              onMapClick({ lat: event.detail.latLng.lat, lng: event.detail.latLng.lng });
            }
          }}
        >
          <MapMarkers
            data={data}
            enabled={enabled}
            reportFeatures={reportFeatures}
            reportPoint={reportPoint}
            reportMode={reportMode}
            onSelect={(feature, layer) => setSelected({ feature, layer })}
          />
          {selected?.feature.geometry.type === "Point" && (
            <InfoWindow
              position={{
                lat: selected.feature.geometry.coordinates[1],
                lng: selected.feature.geometry.coordinates[0],
              }}
              onCloseClick={() => setSelected(null)}
            >
              <div className="info-card">
                <div className="info-meta">
                  <span className="info-badge">{sources[selected.layer]}</span>
                  <span>{formatTimestamp(selectedTimestamp)}</span>
                </div>
                <strong>
                  {textProperty(
                    selected.feature,
                    "municipio",
                    textProperty(
                      selected.feature,
                      "via",
                      textProperty(selected.feature, "nome", labels[selected.layer]),
                    ),
                  )}
                </strong>
                <p>
                  {textProperty(
                    selected.feature,
                    "descricao",
                    textProperty(
                      selected.feature,
                      "evento",
                      textProperty(
                        selected.feature,
                        "description",
                        `${numberProperty(selected.feature, "total") || ""} registros agregados`,
                      ),
                    ),
                  )}
                </p>
                {selected.layer === "reports" && (
                  <button className="button ghost confirm-button" onClick={handleConfirm}>
                    {confirming
                      ? "Confirmando…"
                      : `Confirmar (${numberProperty(selected.feature, "confirmations")})`}
                  </button>
                )}
                <small>Fonte: {sources[selected.layer]} ↗</small>
              </div>
            </InfoWindow>
          )}
          {selected?.feature.geometry.type === "Polygon" && (
            <InfoWindow
              position={{
                lat: selected.feature.geometry.coordinates[0][0][1],
                lng: selected.feature.geometry.coordinates[0][0][0],
              }}
              onCloseClick={() => setSelected(null)}
            >
              <div className="info-card">
                <div className="info-meta">
                  <span className="info-badge">{sources[selected.layer]}</span>
                  <span>{formatTimestamp(selectedStatus?.fetched_at)}</span>
                </div>
                <strong>{labels[selected.layer]}</strong>
                <p>{numberProperty(selected.feature, "total")} registros nesta célula</p>
                <small>Fonte: {sources[selected.layer]} ↗</small>
              </div>
            </InfoWindow>
          )}
          <Traffic />
          <LocationTools reportMode={reportMode} />
        </GoogleMap>
      </div>
    </APIProvider>
  );
}
