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
