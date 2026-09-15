import { Marker, useMap, useMapsLibrary } from "@vis.gl/react-google-maps";
import { FormEvent, KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { Place, useSuggestions } from "../places";

const SP_BOUNDS = { north: -23.3, south: -24.05, east: -46.3, west: -47.0 };

type Picked = { lat: number; lng: number; label: string; kind: "gps" | "search" };

export function LocationTools({ reportMode }: { reportMode: boolean }) {
  const map = useMap();
  const geocoding = useMapsLibrary("geocoding");
  const [query, setQuery] = useState("");
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [following, setFollowing] = useState(false);
  const [status, setStatus] = useState("");
  const {
    suggestions,
    searching,
    query: querySuggestions,
    clear: clearSuggestions,
  } = useSuggestions();
  const watchRef = useRef<number | null>(null);
  const geocoderRef = useRef<google.maps.Geocoder | null>(null);
  const statusTimer = useRef<number>(0);
  const suggestionListId = useId();

  function flash(message: string) {
    setStatus(message);
    window.clearTimeout(statusTimer.current);
    statusTimer.current = window.setTimeout(() => setStatus(""), 4000);
  }

  function chooseSuggestion(place: Place) {
    setQuery(place.label.split(",")[0]);
    setActiveSuggestion(-1);
    clearSuggestions();
    pick(place.lat, place.lng, place.label, "search");
  }

  function pick(lat: number, lng: number, label: string, kind: Picked["kind"]) {
    setPicked({ lat, lng, label, kind });
    map?.panTo({ lat, lng });
    map?.setZoom(15);
    setStatus("");
  }

  function stopWatch() {
    if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current);
    watchRef.current = null;
    setFollowing(false);
  }

  function locate() {
    if (!navigator.geolocation) {
      flash("Geolocalização não disponível neste aparelho.");
      return;
    }
    setStatus("Localizando…");
    navigator.geolocation.getCurrentPosition(
      (pos) => pick(pos.coords.latitude, pos.coords.longitude, "Você está aqui", "gps"),
      () => flash("Não foi possível obter sua localização."),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  function toggleFollow() {
    if (following) {
      stopWatch();
      return;
    }
    if (!navigator.geolocation) {
      flash("Geolocalização não disponível neste aparelho.");
      return;
    }
    setStatus("Acompanhando sua posição…");
    watchRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setPicked({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          label: "Você está aqui",
          kind: "gps",
        });
        map?.panTo({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      () => {
        stopWatch();
        flash("Acompanhamento interrompido.");
      },
      { enableHighAccuracy: true, maximumAge: 5000 },
    );
    setFollowing(true);
    setStatus("");
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    // Enter com a lista aberta escolhe a primeira, como no Maps.
    if (suggestions.length > 0) {
      chooseSuggestion(suggestions[activeSuggestion >= 0 ? activeSuggestion : 0]);
      return;
    }
    setStatus("Buscando endereço…");
    const full = q.toLowerCase().includes("paulo") ? q : `${q}, São Paulo, SP`;
    try {
      if (!geocoderRef.current && geocoding) geocoderRef.current = new geocoding.Geocoder();
      if (geocoderRef.current) {
        const { results } = await geocoderRef.current.geocode({
          address: full,
          bounds: SP_BOUNDS,
          region: "br",
        });
        if (results[0]) {
          const loc = results[0].geometry.location;
          pick(loc.lat(), loc.lng(), results[0].formatted_address, "search");
          return;
        }
      }
    } catch {
      // Geocoding API pode não estar habilitada; cai no Nominatim.
    }
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=br&q=${encodeURIComponent(full)}`,
      );
      const arr: { lat: string; lon: string; display_name: string }[] = await res.json();
      if (arr[0])
        pick(parseFloat(arr[0].lat), parseFloat(arr[0].lon), arr[0].display_name, "search");
      else flash("Endereço não encontrado. Tente com número ou referência.");
    } catch {
      flash("Busca de endereço indisponível.");
    }
  }

  function navigateSuggestions(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      clearSuggestions();
      setActiveSuggestion(-1);
      return;
    }
    if (suggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveSuggestion((current) => Math.min(current + 1, suggestions.length - 1));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSuggestion((current) => Math.max(current - 1, 0));
    }
  }

  useEffect(
    () => () => {
      stopWatch();
      window.clearTimeout(statusTimer.current);
    },
    [],
  );

  return (
    <>
      <div className="locate-bar">
        <form className="locate-search" onSubmit={search} role="search">
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveSuggestion(-1);
              querySuggestions(event.target.value);
            }}
            onKeyDown={navigateSuggestions}
            placeholder="Rua, avenida ou referência…"
            aria-label="Buscar rua ou endereço em São Paulo"
            role="combobox"
            aria-autocomplete="list"
            aria-controls={suggestionListId}
            aria-expanded={suggestions.length > 0}
            aria-activedescendant={
              activeSuggestion >= 0 ? `${suggestionListId}-option-${activeSuggestion}` : undefined
            }
            autoComplete="off"
          />
          <button type="submit" className="button secondary" aria-label="Buscar">
            ⌕
          </button>
        </form>
        {suggestions.length > 0 && (
          <ul className="locate-suggestions" id={suggestionListId} role="listbox">
            {suggestions.map((place, index) => (
              <li key={`${place.label}-${place.lat}-${place.lng}`} role="presentation">
                <button
                  id={`${suggestionListId}-option-${index}`}
                  type="button"
                  role="option"
                  aria-selected={activeSuggestion === index}
                  onMouseEnter={() => setActiveSuggestion(index)}
                  onClick={() => chooseSuggestion(place)}
                >
                  {place.label}
                </button>
              </li>
            ))}
          </ul>
        )}
        {searching && suggestions.length === 0 && (
          <span className="locate-status">Buscando endereços…</span>
        )}
        <div className="locate-actions">
          <button
            className={`button secondary locate-btn${following ? " active" : ""}`}
            onClick={locate}
            type="button"
          >
            ◎ Minha localização
          </button>
          <button
            className={`button secondary locate-btn${following ? " active" : ""}`}
            onClick={toggleFollow}
            type="button"
          >
            {following ? "■ Parar" : "▸ Acompanhar"}
          </button>
        </div>
        {status && <span className="locate-status">{status}</span>}
      </div>
      {picked && (
        <Marker
          position={{ lat: picked.lat, lng: picked.lng }}
          title={picked.label}
          clickable={!reportMode}
          icon={{
            path: 0,
            scale: 9,
            strokeColor: "#ffffff",
            strokeWeight: 2,
            fillColor: picked.kind === "gps" ? "#22c55e" : "#c8f04c",
            fillOpacity: 1,
          }}
        />
      )}
    </>
  );
}
