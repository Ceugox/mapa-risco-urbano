import { Feature, FeatureCollection, LayerName, LayerStatus } from "./types";

const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export async function getLayers(): Promise<LayerStatus[]> {
  return (await fetch(`${base}/api/layers`)).json();
}
export async function getLayer(layer: LayerName): Promise<FeatureCollection> {
  return (await fetch(`${base}/api/layers/${layer}`)).json();
}
export async function createReport(report: {
  category: string;
  description: string;
  lat: number;
  lon: number;
}): Promise<Feature> {
  const response = await fetch(`${base}/api/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(report),
  });
  if (!response.ok)
    throw new Error((await response.json()).detail || "Não foi possível enviar o relato");
  return response.json();
}

export async function confirmReport(
  reportId: string,
): Promise<{ id: string; confirmations: number }> {
  const response = await fetch(`${base}/api/reports/${reportId}/confirm`, { method: "POST" });
  if (!response.ok) {
    throw new Error((await response.json()).detail || "Não foi possível confirmar o relato");
  }
  return response.json();
}

export interface RouteResult {
  distance_km: number;
  duration_min: number;
  score: number;
  level: string;
  breakdown: Record<string, number>;
  geometry: { type: "LineString"; coordinates: [number, number][] };
}

export async function getRoute(
  origin: { lat: number; lon: number },
  destination: { lat: number; lon: number },
): Promise<{ routes: RouteResult[]; note: string }> {
  const response = await fetch(`${base}/api/route`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, destination }),
  });
  if (!response.ok)
    throw new Error((await response.json()).detail || "Não foi possível calcular a rota");
  return response.json();
}

export interface SupportPoint {
  nome: string;
  tipo: string;
  lat: number;
  lon: number;
  distancia_m: number;
  aberto_24h: boolean;
  horario: string;
}

export async function getSupportNearby(
  lat: number,
  lon: number,
): Promise<{ points: SupportPoint[] }> {
  const response = await fetch(`${base}/api/support/nearby?lat=${lat}&lon=${lon}`);
  if (!response.ok) throw new Error("Busca de pontos de apoio indisponível");
  return response.json();
}
