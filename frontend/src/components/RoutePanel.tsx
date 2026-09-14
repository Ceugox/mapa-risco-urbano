import { Marker, useMap, useMapsLibrary } from "@vis.gl/react-google-maps";
import { useEffect, useRef, useState } from "react";
import { createTrip, finishTrip, getRoute, RouteResult, sendTripPosition, track } from "../api";

const SP_BOUNDS = { north: -23.3, south: -24.05, east: -46.3, west: -47.0 };
const LEVEL_COLOR: Record<string, string> = {
  baixo: "#22c55e",
  moderado: "#eab308",
  alto: "#f97316",
  crítico: "#ef4444",
};
const LEVEL_LABEL: Record<string, string> = {
  crime: "Crime",
  alagamento: "Alagamento",
  cemaden: "CEMADEN",
  reports: "Relatos",
  inmet: "INMET",
};

type Place = { lat: number; lng: number; label: string };
type SavedRoute = { name: string; origin: Place; destination: Place; uses: number };

const SAVED_KEY = "mapasp_saved_routes";

function loadSaved(): SavedRoute[] {
  try {
    return JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function shortLabel(label: string) {
  return label.split(",")[0].split("—")[0].trim();
}

type ActiveTrip = { id: string; update_token: string; share_token: string };
const TRIP_KEY = "mapasp_active_trip";
const CONTACTS_KEY = "riscosp-contatos";
const TRIP_POSITION_INTERVAL_MS = 20000;

function loadActiveTrip(): ActiveTrip | null {
  try {
    const raw = localStorage.getItem(TRIP_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function shareLink(trip: ActiveTrip) {
  return `${window.location.origin}/t/${trip.share_token}`;
}

export function RoutePanel({ reportMode }: { reportMode: boolean }) {
  const map = useMap();
  const maps = useMapsLibrary("maps");
  const [open, setOpen] = useState(false);
  const [originQ, setOriginQ] = useState("");
  const [destQ, setDestQ] = useState("");
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [suggestions, setSuggestions] = useState<Place[]>([]);
  const [suggestFor, setSuggestFor] = useState<"origin" | "dest" | null>(null);
  const [routes, setRoutes] = useState<RouteResult[]>([]);
  const [selected, setSelected] = useState(0);
  const [status, setStatus] = useState("");
  const [saved, setSaved] = useState<SavedRoute[]>(loadSaved);
  const [activeTrip, setActiveTrip] = useState<ActiveTrip | null>(loadActiveTrip);
  const [tripStatus, setTripStatus] = useState("");
  const linesRef = useRef<google.maps.Polyline[]>([]);
  const placesRef = useRef<google.maps.places.PlacesService | null>(null);
  const watchIdRef = useRef<number | null>(null);
  const lastSentRef = useRef(0);

  function stopWatch() {
    if (watchIdRef.current !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
  }

  function startWatch(trip: ActiveTrip) {
    if (!navigator.geolocation) return;
    stopWatch();
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const now = Date.now();
        if (now - lastSentRef.current < TRIP_POSITION_INTERVAL_MS) return;
        lastSentRef.current = now;
        sendTripPosition(
          trip.id,
          pos.coords.latitude,
          pos.coords.longitude,
          trip.update_token,
        ).catch(() => {});
      },
      () => {},
      { enableHighAccuracy: true, maximumAge: 10000 },
    );
  }

  useEffect(() => {
    if (activeTrip) startWatch(activeTrip);
    return () => stopWatch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function shareTrip() {
    if (!destination) return;
    setTripStatus("Compartilhando…");
    try {
      const created = await createTrip(
        {
          lat: destination.lat,
          lon: destination.lng,
          label: shortLabel(destination.label || destQ),
        },
        route?.duration_min,
      );
      const trip: ActiveTrip = {
        id: created.id,
        update_token: created.update_token,
        share_token: created.share_token,
      };
      localStorage.setItem(TRIP_KEY, JSON.stringify(trip));
      setActiveTrip(trip);
      startWatch(trip);
      track("trip_shared");
      setTripStatus("");
    } catch {
      setTripStatus("Não foi possível compartilhar o trajeto.");
    }
  }

  async function copyTripLink() {
    if (!activeTrip) return;
    try {
      await navigator.clipboard.writeText(shareLink(activeTrip));
      setTripStatus("Link copiado.");
    } catch {
      setTripStatus("Não foi possível copiar — copie manualmente.");
    }
  }

  function shareTripOnWhatsapp() {
    if (!activeTrip) return;
    const text = encodeURIComponent(
      `Estou a caminho, acompanhe meu trajeto: ${shareLink(activeTrip)}`,
    );
    let contacts: { phone: string }[] = [];
    try {
      contacts = JSON.parse(localStorage.getItem(CONTACTS_KEY) || "[]");
    } catch {
      contacts = [];
    }
    if (contacts.length) {
      contacts.forEach((contact, index) =>
        window.setTimeout(
          () => window.open(`https://wa.me/${contact.phone}?text=${text}`, "_blank"),
          index * 300,
        ),
      );
    } else {
      window.open(`https://wa.me/?text=${text}`, "_blank");
    }
  }

  async function arrivedTrip() {
    if (!activeTrip) return;
    stopWatch();
    try {
      await finishTrip(activeTrip.id, activeTrip.update_token);
    } catch {
      // Encerra localmente mesmo se a chamada falhar.
    }
    localStorage.removeItem(TRIP_KEY);
    setActiveTrip(null);
    setTripStatus("Chegada registrada.");
  }

  async function searchPlaces(q: string): Promise<Place[]> {
    const query = q.toLowerCase().includes("paulo") ? q : `${q}, São Paulo`;
    try {
      if (map) {
        const lib = (await google.maps.importLibrary("places")) as google.maps.PlacesLibrary;
        placesRef.current ??= new lib.PlacesService(map);
        const found = await new Promise<google.maps.places.PlaceResult[]>((resolve) => {
          placesRef.current?.textSearch({ query, bounds: SP_BOUNDS }, (results, code) =>
            resolve(code === google.maps.places.PlacesServiceStatus.OK && results ? results : []),
          );
        });
        const out = found.slice(0, 4).flatMap((result) => {
          const loc = result.geometry?.location;
          return loc
            ? [
                {
                  lat: loc.lat(),
                  lng: loc.lng(),
                  label: `${result.name} — ${result.formatted_address}`,
                },
              ]
            : [];
        });
        if (out.length) return out;
      }
    } catch {
      // Places indisponível na chave; cai no Nominatim.
    }
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=4&countrycodes=br&q=${encodeURIComponent(query)}`,
      );
      const arr: { lat: string; lon: string; display_name: string }[] = await res.json();
      return arr.map((item) => ({
        lat: parseFloat(item.lat),
        lng: parseFloat(item.lon),
        label: item.display_name,
      }));
    } catch {
      return [];
    }
  }

  async function suggest(which: "origin" | "dest", q: string) {
    if (q.trim().length < 3) return;
    setSuggestFor(which);
    setStatus("Buscando…");
    const found = await searchPlaces(q);
    setSuggestions(found);
    setStatus(found.length ? "" : "Nada encontrado — tente rua + referência.");
  }

  function choose(place: Place) {
    if (suggestFor === "origin") {
      setOrigin(place);
      setOriginQ(place.label.split(",")[0].split("—")[0].trim());
    } else {
      setDestination(place);
      setDestQ(place.label.split(",")[0].split("—")[0].trim());
    }
    setSuggestions([]);
    setSuggestFor(null);
  }

  function useGps() {
    if (!navigator.geolocation) return;
    setStatus("Localizando…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOrigin({ lat: pos.coords.latitude, lng: pos.coords.longitude, label: "Sua posição" });
        setOriginQ("Minha localização");
        setStatus("");
      },
      () => setStatus("Não foi possível obter sua localização."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  function persist(list: SavedRoute[]) {
    setSaved(list);
    localStorage.setItem(SAVED_KEY, JSON.stringify(list));
  }

  function saveCurrent() {
    if (!origin || !destination) return;
    const name = `${shortLabel(origin.label || originQ)} → ${shortLabel(destination.label || destQ)}`;
    const next = [
      { name, origin, destination, uses: 0 },
      ...saved.filter((item) => item.name !== name),
    ].slice(0, 6);
    persist(next);
    setStatus(`Rota salva: ${name}`);
  }

  function applySaved(item: SavedRoute) {
    setOrigin(item.origin);
    setOriginQ(shortLabel(item.origin.label));
    setDestination(item.destination);
    setDestQ(shortLabel(item.destination.label));
    setSuggestions([]);
    persist(
      saved
        .map((entry) => (entry === item ? { ...entry, uses: entry.uses + 1 } : entry))
        .sort((a, b) => b.uses - a.uses),
    );
    trace(item.origin, item.destination);
  }

  async function trace(from = origin, to = destination) {
    if (!from || !to) {
      setStatus("Informe origem e destino.");
      return;
    }
    setStatus("Calculando rotas…");
    setSuggestions([]);
    try {
      const result = await getRoute({ lat: from.lat, lon: from.lng }, { lat: to.lat, lon: to.lng });
      setRoutes(result.routes);
      setSelected(0);
      setStatus("");
      track("route_calculated", { level: result.routes[0]?.level, n: result.routes.length });
      if (maps && map) {
        const bounds = new google.maps.LatLngBounds();
        result.routes[0].geometry.coordinates.forEach(([lng, lat]) => bounds.extend({ lat, lng }));
        map.fitBounds(bounds, 60);
      }
    } catch {
      setStatus("Não foi possível calcular a rota agora.");
    }
  }

  useEffect(() => {
    if (!map || !maps) return;
    linesRef.current.forEach((line) => line.setMap(null));
    linesRef.current = routes.map((route, index) => {
      const active = index === selected;
      const line = new maps.Polyline({
        path: route.geometry.coordinates.map(([lng, lat]) => ({ lat, lng })),
        map,
        strokeColor: active ? LEVEL_COLOR[route.level] : "#71717a",
        strokeOpacity: active ? 0.95 : 0.5,
        strokeWeight: active ? 5 : 3,
        zIndex: active ? 10 : 1,
        clickable: true,
      });
      line.addListener("click", () => setSelected(index));
      return line;
    });
    return () => {
      linesRef.current.forEach((line) => line.setMap(null));
      linesRef.current = [];
    };
  }, [routes, selected, map, maps]);

  function clear() {
    setRoutes([]);
    setOrigin(null);
    setDestination(null);
    setOriginQ("");
    setDestQ("");
    setSuggestions([]);
  }

  const route = routes[selected];

  return (
    <div className={`route-panel${open ? " open" : ""}`}>
      <button className="route-panel-header" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>⇄ Rota</span>
        {route ? (
          <span className="mono-label" style={{ color: LEVEL_COLOR[route.level] }}>
            risco {route.level} · {route.score}
          </span>
        ) : (
          <span className="mono-label">{open ? "▴" : "▾"}</span>
        )}
      </button>
      {open && (
        <div className="route-body">
          <div className="route-field">
            <input
              value={originQ}
              onChange={(e) => {
                setOriginQ(e.target.value);
                setOrigin(null);
                suggest("origin", e.target.value);
              }}
              onFocus={() => setSuggestFor("origin")}
              placeholder="Origem: rua, lugar ou negócio…"
              aria-label="Origem da rota"
              size={10}
            />
            <button type="button" className="button ghost" onClick={useGps} title="Usar GPS">
              ◎
            </button>
          </div>
          <div className="route-field">
            <input
              value={destQ}
              onChange={(e) => {
                setDestQ(e.target.value);
                setDestination(null);
                suggest("dest", e.target.value);
              }}
              onFocus={() => setSuggestFor("dest")}
              placeholder="Destino: ex. barbeiro, trabalho, casa…"
              aria-label="Destino da rota"
              size={10}
            />
          </div>
          {suggestions.length > 0 && (
            <ul className="route-suggestions" role="listbox">
              {suggestions.map((place, index) => (
                <li key={index}>
                  <button type="button" onClick={() => choose(place)}>
                    {place.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="route-actions">
            <button className="button primary" onClick={() => trace()} type="button">
              Traçar rota
            </button>
            {routes.length > 0 && (
              <>
                <button className="button ghost" onClick={saveCurrent} type="button">
                  Salvar
                </button>
                <button className="button ghost" onClick={clear} type="button">
                  Limpar
                </button>
              </>
            )}
          </div>
          {saved.length > 0 && routes.length === 0 && (
            <ul className="saved-routes" aria-label="Rotas salvas">
              {saved.map((item) => (
                <li key={item.name}>
                  <button
                    type="button"
                    className="saved-route"
                    onClick={() => applySaved(item)}
                    title="Traçar esta rota"
                  >
                    {item.name}
                    {item.uses > 1 && <span className="mono-label"> ×{item.uses}</span>}
                  </button>
                  <button
                    type="button"
                    className="saved-route-del"
                    aria-label={`Remover ${item.name}`}
                    onClick={() => persist(saved.filter((entry) => entry !== item))}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
          {status && <span className="route-status">{status}</span>}
          {routes.length > 0 && (
            <div className="route-results">
              {routes.map((item, index) => (
                <button
                  key={index}
                  className={`route-option${index === selected ? " active" : ""}`}
                  onClick={() => setSelected(index)}
                  type="button"
                >
                  <span className="route-score" style={{ color: LEVEL_COLOR[item.level] }}>
                    {item.score}
                  </span>
                  <span>
                    Rota {index + 1} · {item.distance_km} km · {item.duration_min} min
                  </span>
                  <span className="mono-label">{item.level}</span>
                </button>
              ))}
              {route && (
                <div className="route-breakdown">
                  {Object.entries(route.breakdown)
                    .filter(([, value]) => value > 0)
                    .map(([key, value]) => (
                      <span key={key} className="route-chip">
                        {LEVEL_LABEL[key]} +{value}
                      </span>
                    ))}
                  {Object.values(route.breakdown).every((v) => v === 0) && (
                    <span className="route-chip">sem riscos ativos no trajeto</span>
                  )}
                </div>
              )}
              <div className="trip-share">
                {!activeTrip ? (
                  <button className="button secondary" onClick={shareTrip} type="button">
                    Compartilhar trajeto
                  </button>
                ) : (
                  <>
                    <div className="trip-share-link">
                      <code>{shareLink(activeTrip)}</code>
                      <button className="button ghost" onClick={copyTripLink} type="button">
                        Copiar
                      </button>
                    </div>
                    <div className="route-actions">
                      <button className="button ghost" onClick={shareTripOnWhatsapp} type="button">
                        Enviar no WhatsApp
                      </button>
                      <button className="button primary" onClick={arrivedTrip} type="button">
                        Cheguei
                      </button>
                    </div>
                  </>
                )}
                {tripStatus && <span className="route-status">{tripStatus}</span>}
              </div>
            </div>
          )}
        </div>
      )}
      {origin && (
        <Marker position={{ lat: origin.lat, lng: origin.lng }} label="A" clickable={!reportMode} />
      )}
      {destination && (
        <Marker
          position={{ lat: destination.lat, lng: destination.lng }}
          label="B"
          clickable={!reportMode}
        />
      )}
    </div>
  );
}
