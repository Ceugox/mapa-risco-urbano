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

export type Contact = { name: string; phone: string };

async function authRequest(path: string, body?: object, token?: string, method = "POST") {
  const response = await fetch(`${base}/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Erro na conta");
  return data;
}

export function register(
  email: string,
  password: string,
): Promise<{ token: string; email: string }> {
  return authRequest("/auth/register", { email, password });
}

export function login(email: string, password: string): Promise<{ token: string; email: string }> {
  return authRequest("/auth/login", { email, password });
}

export function getContacts(token: string): Promise<{ contacts: Contact[]; email: string }> {
  return authRequest("/contacts", undefined, token, "GET");
}

export function saveContacts(token: string, contacts: Contact[]): Promise<{ contacts: Contact[] }> {
  return authRequest("/contacts", { contacts }, token, "PUT");
}

export function track(name: string, meta: Record<string, unknown> = {}) {
  try {
    const body = JSON.stringify({ name, meta: { ...meta, referrer: document.referrer } });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(`${base}/api/events`, new Blob([body], { type: "application/json" }));
    } else {
      fetch(`${base}/api/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => undefined);
    }
  } catch {
    // Telemetria nunca pode quebrar a UI.
  }
}

export interface AdminStats {
  range: string;
  generated_at: string;
  kpi: {
    page_views: number;
    visitors: number;
    api_calls: number;
    errors: number;
    error_rate: number;
    p95_ms: number;
    routes: number;
    reports: number;
    bots: number;
    users_total: number;
    reports_total: number;
  };
  series: {
    bucket: string;
    requests: number;
    page_views: number;
    visitors: number;
    errors: number;
  }[];
  devices: Record<string, number>;
  browsers: Record<string, number>;
  referers: { name: string; count: number }[];
  top_paths: { path: string; count: number }[];
  events: { name: string; count: number }[];
  recent_errors: { ts: string; method: string; path: string; status: number }[];
}

export function adminLogin(password: string): Promise<{ token: string }> {
  return authRequest("/admin/login", { password });
}

export async function adminStats(token: string, range: string): Promise<AdminStats> {
  const response = await fetch(`${base}/api/admin/stats?range=${range}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("Falha ao carregar estatísticas");
  return response.json();
}

export interface RiskItem {
  layer: string;
  count: number;
  label: string;
  nearest_m: number | null;
}

export interface RiskHereResult {
  level: "baixo" | "moderado" | "alto";
  score: number;
  items: RiskItem[];
  updated_at: string;
}

export async function getRiskHere(lat: number, lon: number): Promise<RiskHereResult> {
  const response = await fetch(`${base}/api/risk/here?lat=${lat}&lon=${lon}`);
  if (!response.ok)
    throw new Error((await response.json()).detail || "Não foi possível avaliar o risco aqui");
  return response.json();
}
