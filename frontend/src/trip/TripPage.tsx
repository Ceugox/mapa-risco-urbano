import { APIProvider, Map as GoogleMap, Marker, useMap } from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useState } from "react";
import { getSharedTrip, SharedTrip } from "../api";
import "../styles.css";
import "./trip.css";

const POLL_MS = 15000;

function minutesAgo(iso: string | null): number | null {
  if (!iso) return null;
  const diffMs = Date.now() - new Date(iso).getTime();
  return Math.max(0, Math.round(diffMs / 60000));
}

function statusLabel(trip: SharedTrip | null): { text: string; tone: "live" | "done" | "expired" } {
  if (!trip) return { text: "Link expirado", tone: "expired" };
  if (trip.finished_at) return { text: "Chegou bem", tone: "done" };
  if (!trip.active) return { text: "Link expirado", tone: "expired" };
  return { text: "Em trajeto", tone: "live" };
}

function FitBounds({ trip }: { trip: SharedTrip }) {
  const map = useMap();
  useEffect(() => {
    if (!map) return;
    const bounds = new google.maps.LatLngBounds();
    bounds.extend({ lat: trip.destination.lat, lng: trip.destination.lon });
    if (trip.last_position) {
      bounds.extend({ lat: trip.last_position.lat, lng: trip.last_position.lon });
    }
    map.fitBounds(bounds, 60);
  }, [map, trip]);
  return null;
}

export function TripPage({ token }: { token: string }) {
  const [trip, setTrip] = useState<SharedTrip | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [, setTick] = useState(0);
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const data = await getSharedTrip(token);
        if (!cancelled) {
          setTrip(data);
          setNotFound(false);
        }
      } catch {
        if (!cancelled) setNotFound(true);
      }
    }
    poll();
    const dataTimer = window.setInterval(poll, POLL_MS);
    const clockTimer = window.setInterval(() => setTick((n) => n + 1), 30000);
    return () => {
      cancelled = true;
      window.clearInterval(dataTimer);
      window.clearInterval(clockTimer);
    };
  }, [token]);

  const status = useMemo(() => statusLabel(notFound ? null : trip), [trip, notFound]);
  const ago = trip?.last_position ? minutesAgo(trip.last_position.at) : null;
  const destinationLabel = trip?.destination.label || "destino";

  return (
    <div className="trip-page">
      <header className="trip-header">
        <span className="trip-brand">MapaSP</span>
        <span className={`trip-status trip-status-${status.tone}`}>{status.text}</span>
      </header>

      {!trip && !notFound && <p className="trip-loading">Carregando trajeto…</p>}

      {notFound && (
        <p className="trip-empty">
          Este link não existe mais ou já expirou. Peça para a pessoa compartilhar um novo trajeto.
        </p>
      )}

      {trip && (
        <>
          <p className="trip-summary">
            Acompanhando trajeto até <strong>{destinationLabel}</strong>.
            {ago !== null ? ` Última atualização há ${ago} min.` : " Ainda sem posição enviada."}
          </p>

          {apiKey ? (
            <div className="trip-map-wrap">
              <APIProvider apiKey={apiKey}>
                <GoogleMap
                  defaultCenter={{ lat: trip.destination.lat, lng: trip.destination.lon }}
                  defaultZoom={13}
                  gestureHandling="greedy"
                  disableDefaultUI={false}
                  fullscreenControl={false}
                  mapTypeControl={false}
                  streetViewControl={false}
                >
                  <Marker
                    position={{ lat: trip.destination.lat, lng: trip.destination.lon }}
                    label="Destino"
                  />
                  {trip.last_position && (
                    <Marker
                      position={{ lat: trip.last_position.lat, lng: trip.last_position.lon }}
                      label="●"
                    />
                  )}
                  <FitBounds trip={trip} />
                </GoogleMap>
              </APIProvider>
            </div>
          ) : (
            <div className="trip-fallback">
              <p>
                Destino:{" "}
                <a
                  href={`https://www.google.com/maps?q=${trip.destination.lat},${trip.destination.lon}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {trip.destination.lat.toFixed(5)}, {trip.destination.lon.toFixed(5)}
                </a>
              </p>
              {trip.last_position && (
                <p>
                  Última posição:{" "}
                  <a
                    href={`https://www.google.com/maps?q=${trip.last_position.lat},${trip.last_position.lon}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {trip.last_position.lat.toFixed(5)}, {trip.last_position.lon.toFixed(5)}
                  </a>
                </p>
              )}
            </div>
          )}
        </>
      )}

      <footer className="trip-footer">
        <span className="mono-label">MapaSP · trajeto acompanhado ao vivo</span>
      </footer>
    </div>
  );
}
