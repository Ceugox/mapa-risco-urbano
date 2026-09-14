export type LayerName =
  "alagamento" | "alagamento_hist" | "cemaden" | "inmet" | "clima" | "crime" | "reports";
export type PointCoordinates = [number, number];
export type PolygonCoordinates = [PointCoordinates[]];
export type FeatureProperties = {
  [key: string]: string | number | string[] | null | undefined;
  via?: string;
  municipio?: string;
  nome?: string;
  name?: string;
  descricao?: string;
  evento?: string;
  description?: string;
  total?: number;
  severidade?: number;
  temperature_2m?: number;
  category?: string;
  confirmations?: number;
  created_at?: string;
  expires_at?: string;
  id?: string;
  episodes?: number;
  last_seen?: string;
  days?: number;
};
export type Feature = {
  type: "Feature";
  id?: string;
  geometry:
    | { type: "Point"; coordinates: PointCoordinates }
    | { type: "Polygon"; coordinates: PolygonCoordinates };
  properties: FeatureProperties;
};
export type FeatureCollection = {
  type: "FeatureCollection";
  features: Feature[];
  _metadata?: LayerStatus;
};
export type LayerStatus = {
  layer: LayerName;
  fetched_at: string | null;
  source_updated_at: string | null;
  ok: boolean;
  error: string | null;
  count: number;
};
